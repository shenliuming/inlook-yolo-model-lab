from __future__ import annotations

import copy
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, HTTPException, UploadFile

from app.dto.ai_dto import CopyRewriteRequestDTO
from app.dto.digital_human_dto import DigitalHumanGenerateRequestDTO
from app.dto.material_dto import MaterialExtractRequestDTO
from app.dto.studio_dto import TtsSynthesisCreateRequestDTO
from app.dto.studio_project_dto import StudioProjectTranscriptionRequestDTO
from app.services.copy_rewrite_service import rewrite_copy
from app.services.digital_human.task_service import queue_video_task, read_video_task, run_video_task
from app.services.material_service import (
    extract_material,
    material_json_path,
    upload_material,
)
from app.config.paths import STUDIO_TRANSCRIPTION_RUNTIME_DIR
from app.services.project_runtime_service import (
    copy_file,
    copy_tree,
    create_project,
    now,
    project_copywriting_dir,
    project_current_material_dir,
    project_file_url,
    project_subtitles_dir,
    project_transcription_dir,
    project_tts_synthesis_dir,
    read_project,
    update_project,
    write_json,
    write_project_task,
    project_dir,
    list_project_tasks,
)
from app.services.studio_tts_service import create_tts_synthesis, get_tts_synthesis
from app.services.transcriptions_service import create_transcription_task
from app.services.tts_service import task_dir as tts_task_dir
from app.tasks.studio_task_service import list_tasks as list_global_tasks


def _find_project_file_url(project_id: str, destination_root: Path, section_root_name: str, source_url: str) -> str:
    value = str(source_url or "").strip()
    if not value.startswith("/api/"):
        return value
    filename = Path(value.split("?")[0]).name
    matches = [path for path in destination_root.rglob(filename) if path.is_file()]
    if not matches:
        return value
    relative = Path(section_root_name) / matches[0].relative_to(destination_root)
    return project_file_url(project_id, relative)


def _projectize_downloads(project_id: str, destination_root: Path, section_root_name: str, downloads: dict[str, str]) -> dict[str, str]:
    return {
        key: _find_project_file_url(project_id, destination_root, section_root_name, value)
        for key, value in (downloads or {}).items()
    }


def _snapshot_material_to_project(project_id: str, material_payload: dict[str, Any]) -> dict[str, Any]:
    material_id = str(material_payload.get("materialId") or "").strip()
    source_root = material_json_path(material_id).parent
    destination_root = project_current_material_dir(project_id)
    copy_tree(source_root, destination_root)

    payload = copy.deepcopy(material_payload)
    payload["projectId"] = project_id
    payload["localVideoUrl"] = _find_project_file_url(project_id, destination_root, "materials/current", payload.get("localVideoUrl", ""))
    payload["coverUrl"] = _find_project_file_url(project_id, destination_root, "materials/current", payload.get("coverUrl", ""))
    video = dict(payload.get("video") or {})
    video["url"] = _find_project_file_url(project_id, destination_root, "materials/current", video.get("url", ""))
    video["sources"] = [
        {
            **item,
            "url": _find_project_file_url(project_id, destination_root, "materials/current", item.get("url", "")),
        }
        for item in (video.get("sources") or [])
    ]
    payload["video"] = video
    payload["images"] = [
        {
            **item,
            "url": _find_project_file_url(project_id, destination_root, "materials/current", item.get("url", "")),
            "thumbnailUrl": _find_project_file_url(project_id, destination_root, "materials/current", item.get("thumbnailUrl", "")),
        }
        for item in (payload.get("images") or [])
    ]
    payload["musicUrl"] = _find_project_file_url(project_id, destination_root, "materials/current", payload.get("musicUrl", ""))

    update_project(
        project_id,
        {
            "current": {"materialId": material_id},
            "artifacts": {"material": payload},
        },
    )
    write_project_task(
        project_id,
        {
            "taskId": material_id,
            "taskType": "material.fetch",
            "sourceType": payload.get("sourceType") or "",
            "status": "success" if payload.get("status") == "ready" else "pending",
            "stage": "素材读取",
            "progress": 100 if payload.get("status") == "ready" else 50,
            "outputs": {"materialId": material_id},
            "createdAt": payload.get("createdAt") or now(),
            "updatedAt": payload.get("updatedAt") or now(),
        },
    )
    return payload


def _project_material_id(project_id: str, requested_material_id: str = "") -> str:
    if requested_material_id.strip():
        return requested_material_id.strip()
    project = read_project(project_id)
    material_id = str((project.get("current") or {}).get("materialId") or "").strip()
    if not material_id:
        raise HTTPException(status_code=400, detail="当前项目还没有可用素材")
    return material_id


def _snapshot_transcription_to_project(project_id: str, task: dict[str, Any]) -> dict[str, Any]:
    transcription_id = str(task.get("transcriptionId") or task.get("taskId") or "").strip()
    material_id = str(task.get("materialId") or "").strip()
    source_root = STUDIO_TRANSCRIPTION_RUNTIME_DIR / transcription_id
    destination_root = project_transcription_dir(project_id, transcription_id)
    copy_tree(source_root, destination_root)

    subtitles_dir = project_subtitles_dir(project_id)
    subtitles_dir.mkdir(parents=True, exist_ok=True)
    copy_file(destination_root / "outputs" / "subtitles.srt", subtitles_dir / "subtitles.srt")
    copy_file(destination_root / "outputs" / "subtitles.vtt", subtitles_dir / "subtitles.vtt")

    payload = copy.deepcopy(task)
    payload["projectId"] = project_id
    payload["files"] = _projectize_downloads(project_id, destination_root, f"transcriptions/{transcription_id}", payload.get("files") or {})
    payload["subtitleFiles"] = {
        "srt": project_file_url(project_id, "subtitles/subtitles.srt") if (subtitles_dir / "subtitles.srt").exists() else "",
        "vtt": project_file_url(project_id, "subtitles/subtitles.vtt") if (subtitles_dir / "subtitles.vtt").exists() else "",
    }

    update_project(
        project_id,
        {
            "current": {"materialId": material_id, "transcriptionId": transcription_id},
            "artifacts": {"transcription": payload},
        },
    )
    write_project_task(
        project_id,
        {
            "taskId": transcription_id,
            "taskType": "transcription.extract",
            "sourceType": "studio_project",
            "status": payload.get("status") or "success",
            "stage": payload.get("stage") or "文案提取",
            "progress": payload.get("progress") or 100,
            "outputs": {
                "materialId": material_id,
                "subtitleFiles": payload.get("subtitleFiles") or {},
            },
            "createdAt": payload.get("createdAt") or now(),
            "updatedAt": payload.get("updatedAt") or now(),
        },
    )
    return payload


def _snapshot_rewrite_to_project(project_id: str, request: CopyRewriteRequestDTO, result: dict[str, Any]) -> dict[str, Any]:
    rewrite_id = f"rw_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    payload = {
        "rewriteId": rewrite_id,
        "request": request.model_dump(),
        "versions": result.get("versions") or [],
        "createdAt": now(),
    }
    copywriting_dir = project_copywriting_dir(project_id)
    write_json(copywriting_dir / f"{rewrite_id}.json", payload)
    write_json(copywriting_dir / "latest.json", payload)

    update_project(
        project_id,
        {
            "current": {"rewriteId": rewrite_id},
            "artifacts": {"copywriting": payload},
        },
    )
    write_project_task(
        project_id,
        {
            "taskId": rewrite_id,
            "taskType": "copy.rewrite",
            "sourceType": request.sourceTextType,
            "status": "success",
            "stage": "文案改写",
            "progress": 100,
            "createdAt": payload["createdAt"],
            "updatedAt": payload["createdAt"],
        },
    )
    return {"rewriteId": rewrite_id, **result}


def _sync_tts_task_to_project(project_id: str, synthesis_id: str) -> Path:
    source_root = tts_task_dir(synthesis_id)
    destination_root = project_tts_synthesis_dir(project_id, synthesis_id)
    copy_tree(source_root, destination_root)
    return destination_root


def _projectize_synthesis(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    synthesis_id = str(payload.get("synthesisId") or payload.get("taskId") or "").strip()
    destination_root = _sync_tts_task_to_project(project_id, synthesis_id)
    result = copy.deepcopy(payload)
    result["projectId"] = project_id
    result["audioUrl"] = _find_project_file_url(project_id, destination_root, f"tts/synthesis/{synthesis_id}", result.get("audioUrl", ""))
    result["downloads"] = _projectize_downloads(project_id, destination_root, f"tts/synthesis/{synthesis_id}", result.get("downloads") or {})

    update_project(
        project_id,
        {
            "current": {"synthesisId": synthesis_id},
            "artifacts": {"tts": result},
        },
    )
    write_project_task(
        project_id,
        {
            "taskId": synthesis_id,
            "taskType": "tts.synthesis",
            "sourceType": "studio_project",
            "status": result.get("status") or "pending",
            "stage": "语音合成",
            "progress": 100 if result.get("status") == "success" else 60,
            "outputs": {"downloads": result.get("downloads") or {}},
            "createdAt": result.get("createdAt") or now(),
            "updatedAt": result.get("updatedAt") or now(),
        },
    )
    return result


def create_studio_project(name: str = "") -> dict[str, Any]:
    return create_project(name=name)


def get_studio_project(project_id: str) -> dict[str, Any]:
    return read_project(project_id)


def list_studio_tasks(limit: int = 50) -> list[dict[str, Any]]:
    tasks = list_project_tasks(limit=limit)
    seen = {str(item.get("taskId") or "") for item in tasks}
    for item in list_global_tasks(limit=limit):
        task_id = str(item.get("taskId") or "")
        if task_id and task_id not in seen:
            tasks.append(item)
            seen.add(task_id)
    tasks.sort(key=lambda item: item.get("createdAt") or "", reverse=True)
    return tasks[:limit]


def studio_extract_material(project_id: str, request: MaterialExtractRequestDTO) -> dict[str, Any]:
    payload = extract_material(
        source_type=request.resolved_source_type,
        raw_input=request.raw_input,
        raw_url=request.normalized_url,
    )
    return _snapshot_material_to_project(project_id, payload)


def studio_upload_material(project_id: str, file: UploadFile) -> dict[str, Any]:
    payload = upload_material(file)
    return _snapshot_material_to_project(project_id, payload)


def studio_create_transcription(project_id: str, request: StudioProjectTranscriptionRequestDTO) -> dict[str, Any]:
    material_id = _project_material_id(project_id, request.materialId)
    task = create_transcription_task(
        material_id=material_id,
        model=request.model,
        language=request.language,
        device=request.device,
        compute_type=request.computeType,
        beam_size=request.beamSize,
    )
    return _snapshot_transcription_to_project(project_id, task)


def studio_rewrite_copy(project_id: str, request: CopyRewriteRequestDTO) -> dict[str, Any]:
    result = rewrite_copy(request)
    return _snapshot_rewrite_to_project(project_id, request, result)


def studio_create_synthesis(
    project_id: str,
    background_tasks: BackgroundTasks,
    request: TtsSynthesisCreateRequestDTO,
) -> dict[str, Any]:
    result = create_tts_synthesis(
        background_tasks=background_tasks,
        text=request.text,
        voice_id=request.voiceId or request.voice,
        speed=request.speed,
        emotion=request.emotion,
        volume=request.volume,
        language=request.language,
        training_id=request.trainingId,
        voice_mode=request.voiceMode,
        execution_provider=request.executionProvider,
    )
    return _projectize_synthesis(project_id, result)


def studio_get_synthesis(project_id: str, synthesis_id: str) -> dict[str, Any]:
    result = get_tts_synthesis(synthesis_id)
    return _projectize_synthesis(project_id, result)


def studio_create_digital_human_task(
    project_id: str,
    background_tasks: BackgroundTasks,
    request: DigitalHumanGenerateRequestDTO,
) -> dict[str, Any]:
    payload = request.model_dump()
    payload["projectId"] = project_id
    if not payload.get("workflowId"):
        payload["workflowId"] = project_id
    task = queue_video_task(DigitalHumanGenerateRequestDTO(**payload))
    task_id = str(task.get("taskId") or "").strip()
    if task_id:
        background_tasks.add_task(run_video_task, task_id)
    return {
        "taskId": task_id,
        "status": task.get("status") or "queued",
        "progress": task.get("progress") or 0,
    }


def studio_get_digital_human_task(project_id: str, task_id: str) -> dict[str, Any]:
    task = read_video_task(task_id)
    if project_id and task.get("projectId") and task["projectId"] != project_id:
        raise HTTPException(status_code=404, detail="数字人任务不存在")
    return task
