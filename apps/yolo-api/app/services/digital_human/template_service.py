from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.config.paths import STUDIO_DIGITAL_HUMAN_TEMPLATES_DIR

from .providers.local_provider import LocalDigitalHumanProvider
from .providers.remote_provider import RemoteDigitalHumanProvider
from .template_repository import create_sync_record, list_templates, save_template, upsert_template_by_provider

_LOCAL_PROVIDER = LocalDigitalHumanProvider()
_REMOTE_PROVIDER = RemoteDigitalHumanProvider()


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _template_dir(template_id: str) -> Path:
    return STUDIO_DIGITAL_HUMAN_TEMPLATES_DIR / template_id


def _normalize_template(item: dict[str, Any]) -> dict[str, Any]:
    source = str(item.get("source") or "local")
    return {
        "templateId": str(item.get("template_id") or ""),
        "name": str(item.get("name") or ""),
        "status": str(item.get("status") or "draft"),
        "source": source,
        "sourceLabel": "远程模板库" if source == "remote_provider" else "本地",
        "providerCode": str(item.get("provider_code") or "local_provider"),
        "trainingType": str(item.get("training_type") or "full"),
        "resolutionLabel": str(item.get("resolution_label") or "1080p"),
        "width": int(item.get("width") or 0),
        "height": int(item.get("height") or 0),
        "coverUrl": str(item.get("cover_url") or ""),
        "previewUrl": str(item.get("preview_url") or item.get("cover_url") or ""),
        "outputPath": str(item.get("output_path") or ""),
        "errorMessage": str(item.get("error_message") or ""),
        "tags": item.get("tags") or ["模板"],
        "createdAt": str(item.get("created_at") or ""),
        "updatedAt": str(item.get("updated_at") or ""),
        "debug": {
            "providerTemplateId": str(item.get("provider_template_id") or ""),
            "providerAudioProfileId": str(item.get("provider_audio_profile_id") or ""),
        },
    }


def read_templates() -> list[dict[str, Any]]:
    return [_normalize_template(item) for item in list_templates()]


def create_template_import(
    *,
    filename: str,
    content: bytes,
    name: str,
    training_type: str,
    resolution_label: str,
) -> dict[str, Any]:
    template_id = f"tpl_{uuid.uuid4().hex[:12]}"
    template_dir = _template_dir(template_id)
    template_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename or "template.mp4").suffix or ".mp4"
    source_path = template_dir / f"source{suffix}"
    log_path = template_dir / "run.log"
    source_path.write_bytes(content)
    saved = save_template(
        {
            "template_id": template_id,
            "name": name.strip() or "未命名模板",
            "source": "local",
            "provider_code": _LOCAL_PROVIDER.code,
            "provider_template_id": "",
            "provider_audio_profile_id": "",
            "status": "training",
            "training_type": training_type,
            "resolution_label": resolution_label,
            "local_video_path": str(source_path),
            "local_template_path": str(source_path),
            "output_path": "",
            "tags": ["模板"],
            "provider_payload": {},
            "created_at": _now(),
            "updated_at": _now(),
        }
    )
    normalized = _normalize_template(saved)
    normalized["debug"]["runLogPath"] = str(log_path)
    return normalized


def complete_template_import(template_id: str) -> dict[str, Any]:
    from .template_repository import get_template

    template = get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    template_dir = _template_dir(template_id)
    log_path = template_dir / "run.log"
    job = _LOCAL_PROVIDER.import_template(
        template_id=template_id,
        file_path=Path(str(template.get("local_template_path") or "")),
        name=str(template.get("name") or ""),
        training_type=str(template.get("training_type") or "full"),
        resolution_label=str(template.get("resolution_label") or "1080p"),
        log_path=log_path,
    )
    status = "ready" if str(job.get("status") or "") == "training_succeeded" else "failed"
    return _normalize_template(
        save_template(
            {
                **template,
                "provider_code": _LOCAL_PROVIDER.code,
                "provider_template_id": str(job.get("chanjing_person_id") or ""),
                "provider_audio_profile_id": str(job.get("audio_man_id") or ""),
                "status": status,
                "width": int(job.get("person_width") or 0),
                "height": int(job.get("person_height") or 0),
                "cover_url": str(job.get("pic_url") or ""),
                "preview_url": str(job.get("preview_url") or ""),
                "output_path": str(job.get("local_output_path") or ""),
                "error_message": str(((job.get("error") or {}).get("message")) or ""),
                "provider_payload": job,
                "updated_at": _now(),
            }
        )
    )


def sync_remote_templates() -> dict[str, Any]:
    sync_id = f"sync_{uuid.uuid4().hex[:12]}"
    create_sync_record(
        {
            "sync_id": sync_id,
            "provider_code": _REMOTE_PROVIDER.code,
            "direction": "pull",
            "status": "running",
            "summary": "同步远程模板库中",
            "raw_response": {},
        }
    )
    items = _REMOTE_PROVIDER.sync_templates()
    count = 0
    for item in items:
        provider_template_id = str(item.get("person_id") or item.get("id") or "").strip()
        if not provider_template_id:
            continue
        try:
            remote_status = str(item.get("status") or "")
            normalized_status = "ready" if remote_status in {"ready", "2", "1", "succeeded"} else "training"
            upsert_template_by_provider(
                provider_code=_REMOTE_PROVIDER.code,
                provider_template_id=provider_template_id,
                payload={
                    "template_id": f"tpl_{provider_template_id.replace('-', '').lower()[:20]}",
                    "name": str(item.get("name") or "未命名模板"),
                    "source": "remote_provider",
                    "provider_audio_profile_id": str(item.get("audio_man_id") or ""),
                    "status": normalized_status,
                    "training_type": "full",
                    "resolution_label": "4K" if bool(item.get("support_4k")) else "1080p",
                    "width": int(item.get("width") or 0),
                    "height": int(item.get("height") or 0),
                    "cover_url": str(item.get("pic_url") or ""),
                    "preview_url": str(item.get("preview_url") or ""),
                    "sync_record_id": sync_id,
                    "tags": ["模板"],
                    "provider_payload": item,
                    "updated_at": _now(),
                    "created_at": _now(),
                },
            )
            count += 1
        except Exception:
            continue
    create_sync_record(
        {
            "sync_id": sync_id,
            "provider_code": _REMOTE_PROVIDER.code,
            "direction": "pull",
            "status": "success",
            "summary": f"已同步 {count} 个模板",
            "raw_response": {"count": count},
            "updated_at": _now(),
        }
    )
    return {
        "syncId": sync_id,
        "count": count,
        "items": read_templates(),
    }
