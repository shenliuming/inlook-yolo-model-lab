from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from fastapi import HTTPException

from app.config.paths import STUDIO_DIGITAL_HUMAN_TASKS_DIR
from app.dto.digital_human_dto import DigitalHumanGenerateRequestDTO
from app.services.project_runtime_service import (
    now,
    project_tts_synthesis_dir,
    read_project,
    read_project_file,
)

from .providers.local_provider import LocalDigitalHumanProvider
from .providers.remote_provider import RemoteDigitalHumanProvider
from .task_repository import get_video_task, list_video_tasks, save_video_task
from .template_repository import get_template, list_templates
from .workflow_adapter import sync_workflow_task

_LOCAL_PROVIDER = LocalDigitalHumanProvider()
_REMOTE_PROVIDER = RemoteDigitalHumanProvider()
_PROJECT_FILE_URL_MARKER = "/api/v1/studio/projects/"


def _task_dir(task_id: str) -> Path:
    return STUDIO_DIGITAL_HUMAN_TASKS_DIR / task_id


def _append_log(log_path: Path, message: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as file:
        file.write(message.rstrip() + "\n")


def _copy_output(source: str, destination: Path) -> str:
    source_path = Path(str(source or "")).expanduser()
    if not source_path.exists() or not source_path.is_file():
        return ""
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, destination)
    return str(destination)


def _normalize_task(task: dict[str, Any]) -> dict[str, Any]:
    voice_mode = str(((task.get("provider_payload") or {}).get("voiceMode")) or "")
    return {
        "taskId": str(task.get("task_id") or ""),
        "templateId": str(task.get("template_id") or ""),
        "templateName": str(task.get("template_name") or ""),
        "workflowId": str(task.get("workflow_id") or ""),
        "projectId": str(task.get("project_id") or ""),
        "providerCode": str(task.get("provider_code") or ""),
        "voiceMode": voice_mode or ("provider_auto" if not str(task.get("audio_task_id") or task.get("audio_path") or task.get("audio_url") or "").strip() else "inlook_tts"),
        "status": str(task.get("status") or "queued"),
        "progress": int(task.get("progress") or 0),
        "script": str(task.get("script") or ""),
        "audioTaskId": str(task.get("audio_task_id") or ""),
        "audioUrl": str(task.get("audio_url") or ""),
        "videoUrl": str(task.get("output_url") or ""),
        "coverUrl": str(task.get("cover_url") or ""),
        "errorMessage": str(task.get("error_message") or ""),
        "downloads": task.get("downloads") or {},
        "runLogPath": str(task.get("run_log_path") or ""),
        "createdAt": str(task.get("created_at") or ""),
        "updatedAt": str(task.get("updated_at") or ""),
    }


def read_video_tasks(*, project_id: str | None = None) -> list[dict[str, Any]]:
    return [_normalize_task(item) for item in list_video_tasks(project_id=project_id)]


def read_video_task(task_id: str) -> dict[str, Any]:
    task = get_video_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="数字人任务不存在")
    return _normalize_task(task)


def _project_audio_relative_path(project_id: str, audio_url: str) -> str:
    value = str(audio_url or "").strip()
    if not value:
        return ""
    parsed = urlparse(value)
    path = parsed.path if parsed.scheme else value
    prefix = f"{_PROJECT_FILE_URL_MARKER}{project_id}/files/"
    if prefix not in path:
        return ""
    return unquote(path.split(prefix, 1)[1])


def _resolve_audio_path(request: DigitalHumanGenerateRequestDTO) -> Path | None:
    if request.audioPath:
        candidate = Path(str(request.audioPath)).expanduser()
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    if request.projectId and request.audioUrl:
        relative_path = _project_audio_relative_path(request.projectId, request.audioUrl)
        if relative_path:
            return read_project_file(request.projectId, relative_path)
    if request.projectId and request.audioTaskId:
        candidate = project_tts_synthesis_dir(request.projectId, request.audioTaskId) / "outputs" / "voice.wav"
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
        project = read_project(request.projectId)
        artifact = ((project.get("artifacts") or {}).get("tts") or {}) if isinstance(project.get("artifacts"), dict) else {}
        artifact_audio_url = str(artifact.get("audioUrl") or "")
        relative_path = _project_audio_relative_path(request.projectId, artifact_audio_url)
        if relative_path:
            return read_project_file(request.projectId, relative_path)
    if request.audioUrl:
        candidate = Path(str(request.audioUrl)).expanduser()
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    return None


def queue_video_task(request: DigitalHumanGenerateRequestDTO) -> dict[str, Any]:
    template_id = str(request.templateId or "").strip()
    if not template_id:
        provider_template_id = str(request.personId or request.avatarId or "").strip()
        if provider_template_id:
            for item in list_templates():
                if str(item.get("provider_template_id") or "") == provider_template_id:
                    template_id = str(item.get("template_id") or "")
                    break
    template = get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="数字人模板不存在")
    if str(template.get("status") or "") != "ready":
        raise HTTPException(status_code=400, detail="当前模板尚未可用")

    task_id = f"dhv_{uuid.uuid4().hex[:12]}"
    task_dir = _task_dir(task_id)
    task_dir.mkdir(parents=True, exist_ok=True)
    log_path = task_dir / "run.log"
    metadata_path = task_dir / "metadata.json"
    payload = {
        "task_id": task_id,
        "template_id": template_id,
        "workflow_id": str(request.workflowId or request.projectId or ""),
        "project_id": str(request.projectId or ""),
        "provider_code": str(template.get("provider_code") or "local_provider"),
        "provider_task_id": "",
        "mode": str(request.mode or "auto"),
        "status": "queued",
        "progress": 0,
        "script": str(request.script or ""),
        "audio_task_id": str(request.audioTaskId or ""),
        "audio_path": str(request.audioPath or ""),
        "audio_url": str(request.audioUrl or ""),
        "output_path": "",
        "output_url": "",
        "cover_path": "",
        "cover_url": "",
        "run_log_path": str(log_path),
        "error_message": "",
        "downloads": {},
        "provider_payload": {
            "voiceMode": str(request.voiceMode or "provider_auto"),
        },
        "created_at": now(),
        "updated_at": now(),
        "started_at": "",
        "completed_at": "",
    }
    metadata_path.write_text(json.dumps(request.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    saved = save_video_task(payload)
    sync_workflow_task(saved)
    _append_log(log_path, f"[queued] task_id={task_id}")
    return _normalize_task(saved)


def run_video_task(task_id: str) -> dict[str, Any]:
    task = get_video_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="数字人任务不存在")
    template = get_template(str(task.get("template_id") or ""))
    if not template:
        raise HTTPException(status_code=404, detail="数字人模板不存在")
    task_dir = _task_dir(task_id)
    log_path = Path(str(task.get("run_log_path") or task_dir / "run.log"))
    provider = _REMOTE_PROVIDER if str(template.get("provider_code") or "") == _REMOTE_PROVIDER.code else _LOCAL_PROVIDER
    running = save_video_task(
        {
            **task,
            "status": "running",
            "progress": 15,
            "started_at": now(),
            "updated_at": now(),
        }
    )
    sync_workflow_task(running)
    _append_log(log_path, f"[running] provider={provider.code}")
    try:
        voice_mode = str(((task.get("provider_payload") or {}).get("voiceMode")) or "provider_auto").strip() or "provider_auto"
        request = DigitalHumanGenerateRequestDTO(
            templateId=str(task.get("template_id") or ""),
            script=str(task.get("script") or ""),
            voiceMode=voice_mode,
            audioTaskId=str(task.get("audio_task_id") or ""),
            audioPath=str(task.get("audio_path") or ""),
            audioUrl=str(task.get("audio_url") or ""),
            workflowId=str(task.get("workflow_id") or ""),
            projectId=str(task.get("project_id") or ""),
            mode=str(task.get("mode") or "auto"),
        )
        audio_path = _resolve_audio_path(request)
        if voice_mode == "inlook_tts":
            if audio_path is None and not str(request.audioTaskId or "").strip():
                raise HTTPException(status_code=400, detail="当前声音方案缺少配音结果")
        elif voice_mode == "upload_audio":
            if audio_path is None and not str(request.audioUrl or "").strip():
                raise HTTPException(status_code=400, detail="当前声音方案缺少上传音频")
        elif voice_mode == "provider_auto":
            if not str(task.get("script") or "").strip():
                raise HTTPException(status_code=400, detail="缺少文案，无法自动生成数字人视频")
        elif str(task.get("mode") or "auto") == "auto":
            if audio_path is None and not str(task.get("script") or "").strip():
                raise HTTPException(status_code=400, detail="缺少音频或文案，无法生成数字人视频")
        job = provider.generate_video(
            task_id=task_id,
            template=template,
            script=str(task.get("script") or ""),
            audio_path=audio_path,
            log_path=log_path,
        )
        output_path = _copy_output(str(job.get("local_output_path") or ""), task_dir / "digital_human.mp4")
        downloads = {
            "video": f"/api/v1/files/digital-human/{task_id}/digital_human.mp4" if output_path else "",
            "metadata": f"/api/v1/files/digital-human/{task_id}/metadata.json",
            "runLog": f"/api/v1/files/digital-human/{task_id}/run.log",
        }
        cover_url = str(job.get("preview_url") or "")
        if cover_url:
            downloads["cover"] = cover_url
        final = save_video_task(
            {
                **task,
                "provider_code": provider.code,
                "provider_task_id": str(job.get("chanjing_video_id") or job.get("job_id") or ""),
                "status": "success" if str(job.get("status") or "") == "succeeded" else "failed",
                "progress": 100,
                "output_path": output_path,
                "output_url": downloads["video"] if output_path else "",
                "cover_url": cover_url,
                "run_log_path": str(log_path),
                "error_message": str(((job.get("error") or {}).get("message")) or ""),
                "downloads": downloads,
                "provider_payload": {
                    **(task.get("provider_payload") or {}),
                    **job,
                },
                "updated_at": now(),
                "completed_at": now(),
            }
        )
        sync_workflow_task(final)
        return _normalize_task(final)
    except Exception as exc:
        _append_log(log_path, f"[failed] {type(exc).__name__}: {exc}")
        failed = save_video_task(
            {
                **task,
                "status": "failed",
                "progress": 100,
                "run_log_path": str(log_path),
                "error_message": str(exc),
                "downloads": {
                    "metadata": f"/api/v1/files/digital-human/{task_id}/metadata.json",
                    "runLog": f"/api/v1/files/digital-human/{task_id}/run.log",
                },
                "provider_payload": task.get("provider_payload") or {},
                "updated_at": now(),
                "completed_at": now(),
            }
        )
        sync_workflow_task(failed)
        return _normalize_task(failed)
