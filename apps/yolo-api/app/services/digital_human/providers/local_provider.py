from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from app.clients.chanjing_client import ChanjingApiError
from app.services.digital_human_engines.chanjing_engine import chanjing_engine
from app.services.digital_human_poc_service import (
    create_chanjing_training_upload_job,
    create_chanjing_video_poc_job,
    list_chanjing_persons,
    poll_chanjing_training_poc_job,
    poll_chanjing_video_poc_job,
)

from .base_provider import BaseDigitalHumanProvider


class LocalDigitalHumanProvider(BaseDigitalHumanProvider):
    code = "local_provider"

    def _append_log(self, log_path: Path, message: str) -> None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as file:
            file.write(message.rstrip() + "\n")

    def import_template(
        self,
        *,
        template_id: str,
        file_path: Path,
        name: str,
        training_type: str,
        resolution_label: str,
        log_path: Path,
    ) -> dict[str, Any]:
        self._append_log(log_path, f"[template] start import template_id={template_id}")
        job = create_chanjing_training_upload_job(
            filename=file_path.name,
            content=file_path.read_bytes(),
            name=name,
            train_type={"full": "both", "figure": "figure", "voice": "voice"}.get(training_type, "both"),
            resolution_rate=1 if resolution_label == "4K" else 0,
            language="cn",
            error_skip=False,
        )
        job_id = str(job.get("job_id") or "")
        while str(job.get("status") or "") not in {"training_succeeded", "training_failed", "failed"}:
            self._append_log(log_path, f"[template] polling job={job_id} status={job.get('status')}")
            time.sleep(5)
            job = poll_chanjing_training_poc_job(job_id)
        self._append_log(log_path, f"[template] completed job={job_id} status={job.get('status')}")
        return job

    def sync_templates(self) -> list[dict[str, Any]]:
        payload = list_chanjing_persons(source="api", page=1, page_size=100)
        return [item for item in payload.get("items") or [] if isinstance(item, dict)]

    def generate_video(
        self,
        *,
        task_id: str,
        template: dict[str, Any],
        script: str,
        audio_path: Path | None,
        log_path: Path,
    ) -> dict[str, Any]:
        self._append_log(log_path, f"[task] start generate task_id={task_id}")
        if audio_path is not None:
            self._append_log(log_path, f"[task] upload audio path={audio_path}")
            upload_result = chanjing_engine.upload_audio_for_video(str(audio_path))
            audio_file_id = str(upload_result.get("file_id") or "").strip()
            if not audio_file_id:
                raise ChanjingApiError("音频上传成功但未返回 file_id")
            payload = {
                "person_id": str(template.get("provider_template_id") or template.get("template_id") or ""),
                "audio_type": "audio",
                "audio_file_id": audio_file_id,
                "screen_width": int(template.get("width") or 1080),
                "screen_height": int(template.get("height") or 1920),
                "person_x": 0,
                "person_y": 0,
                "person_width": int(template.get("width") or 1080),
                "person_height": int(template.get("height") or 1920),
                "model": 0,
                "resolution_rate": 1 if str(template.get("resolution_label") or "") == "4K" else 0,
                "add_compliance_watermark": False,
                "hide_subtitle": False,
            }
        else:
            audio_profile_id = str(template.get("provider_audio_profile_id") or "").strip()
            if not script.strip():
                raise ChanjingApiError("缺少可用于生成的文案")
            if not audio_profile_id:
                raise ChanjingApiError("当前模板缺少声音配置，无法直接用文本生成")
            payload = {
                "person_id": str(template.get("provider_template_id") or template.get("template_id") or ""),
                "audio_type": "tts",
                "text": script.strip(),
                "audio_man_id": audio_profile_id,
                "screen_width": int(template.get("width") or 1080),
                "screen_height": int(template.get("height") or 1920),
                "person_x": 0,
                "person_y": 0,
                "person_width": int(template.get("width") or 1080),
                "person_height": int(template.get("height") or 1920),
                "model": 0,
                "resolution_rate": 1 if str(template.get("resolution_label") or "") == "4K" else 0,
                "add_compliance_watermark": False,
                "hide_subtitle": False,
            }
        job = create_chanjing_video_poc_job(payload)
        job_id = str(job.get("job_id") or "")
        while str(job.get("status") or "") not in {"succeeded", "failed", "failed_param", "failed_server"}:
            self._append_log(log_path, f"[task] polling job={job_id} status={job.get('status')}")
            time.sleep(5)
            job = poll_chanjing_video_poc_job(job_id)
        self._append_log(log_path, f"[task] completed job={job_id} status={job.get('status')}")
        return job
