from __future__ import annotations

import json
from typing import Any

from app.services.studio_db import connection_scope


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json_dumps(value: Any, default: str) -> str:
    if value is None:
        return default
    return json.dumps(value, ensure_ascii=False)


def _json_loads(value: str, default: Any) -> Any:
    raw = str(value or "").strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _row_to_template(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    return {
        "template_id": row["template_id"],
        "name": row["name"],
        "source": row["source"],
        "provider_code": row["provider_code"],
        "provider_template_id": row["provider_template_id"],
        "provider_audio_profile_id": row["provider_audio_profile_id"],
        "status": row["status"],
        "training_type": row["training_type"],
        "resolution_label": row["resolution_label"],
        "width": int(row["width"] or 0),
        "height": int(row["height"] or 0),
        "cover_url": row["cover_url"],
        "preview_url": row["preview_url"],
        "local_video_path": row["local_video_path"],
        "local_template_path": row["local_template_path"],
        "output_path": row["output_path"],
        "sync_record_id": row["sync_record_id"],
        "error_message": row["error_message"],
        "tags": _json_loads(row["tags_json"], []),
        "provider_payload": _json_loads(row["provider_payload_json"], {}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_templates() -> list[dict[str, Any]]:
    with connection_scope() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM digital_human_template
            ORDER BY updated_at DESC, created_at DESC
            """
        ).fetchall()
    return [_row_to_template(row) for row in rows]


def get_template(template_id: str) -> dict[str, Any] | None:
    with connection_scope() as connection:
        row = connection.execute(
            "SELECT * FROM digital_human_template WHERE template_id = ?",
            (template_id,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_template(row)


def get_template_by_provider(provider_code: str, provider_template_id: str) -> dict[str, Any] | None:
    with connection_scope() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM digital_human_template
            WHERE provider_code = ? AND provider_template_id = ?
            """,
            (provider_code, provider_template_id),
        ).fetchone()
    if row is None:
        return None
    return _row_to_template(row)


def save_template(payload: dict[str, Any]) -> dict[str, Any]:
    timestamp = str(payload.get("updated_at") or _now())
    created_at = str(payload.get("created_at") or timestamp)
    with connection_scope() as connection:
        connection.execute(
            """
            INSERT INTO digital_human_template (
                template_id, name, source, provider_code, provider_template_id,
                provider_audio_profile_id, status, training_type, resolution_label,
                width, height, cover_url, preview_url, local_video_path,
                local_template_path, output_path, sync_record_id, error_message,
                tags_json, provider_payload_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(template_id) DO UPDATE SET
                name = excluded.name,
                source = excluded.source,
                provider_code = excluded.provider_code,
                provider_template_id = excluded.provider_template_id,
                provider_audio_profile_id = excluded.provider_audio_profile_id,
                status = excluded.status,
                training_type = excluded.training_type,
                resolution_label = excluded.resolution_label,
                width = excluded.width,
                height = excluded.height,
                cover_url = excluded.cover_url,
                preview_url = excluded.preview_url,
                local_video_path = excluded.local_video_path,
                local_template_path = excluded.local_template_path,
                output_path = excluded.output_path,
                sync_record_id = excluded.sync_record_id,
                error_message = excluded.error_message,
                tags_json = excluded.tags_json,
                provider_payload_json = excluded.provider_payload_json,
                updated_at = excluded.updated_at
            """,
            (
                str(payload["template_id"]),
                str(payload.get("name") or ""),
                str(payload.get("source") or "local"),
                str(payload.get("provider_code") or "local_provider"),
                str(payload.get("provider_template_id") or ""),
                str(payload.get("provider_audio_profile_id") or ""),
                str(payload.get("status") or "draft"),
                str(payload.get("training_type") or "full"),
                str(payload.get("resolution_label") or "1080p"),
                int(payload.get("width") or 0),
                int(payload.get("height") or 0),
                str(payload.get("cover_url") or ""),
                str(payload.get("preview_url") or ""),
                str(payload.get("local_video_path") or ""),
                str(payload.get("local_template_path") or ""),
                str(payload.get("output_path") or ""),
                str(payload.get("sync_record_id") or ""),
                str(payload.get("error_message") or ""),
                _json_dumps(payload.get("tags") or [], "[]"),
                _json_dumps(payload.get("provider_payload") or {}, "{}"),
                created_at,
                timestamp,
            ),
        )
    return get_template(str(payload["template_id"])) or {}


def upsert_template_by_provider(
    *,
    provider_code: str,
    provider_template_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    current = get_template_by_provider(provider_code, provider_template_id)
    template_id = str((current or {}).get("template_id") or payload.get("template_id") or "")
    if not template_id:
        raise ValueError("template_id is required")
    merged = {**(current or {}), **payload}
    merged["template_id"] = template_id
    merged["provider_code"] = provider_code
    merged["provider_template_id"] = provider_template_id
    return save_template(merged)


def create_sync_record(payload: dict[str, Any]) -> dict[str, Any]:
    timestamp = str(payload.get("updated_at") or _now())
    created_at = str(payload.get("created_at") or timestamp)
    with connection_scope() as connection:
        connection.execute(
            """
            INSERT INTO digital_human_sync_record (
                sync_id, provider_code, direction, status, summary, raw_response_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sync_id) DO UPDATE SET
                provider_code = excluded.provider_code,
                direction = excluded.direction,
                status = excluded.status,
                summary = excluded.summary,
                raw_response_json = excluded.raw_response_json,
                updated_at = excluded.updated_at
            """,
            (
                str(payload["sync_id"]),
                str(payload.get("provider_code") or "external_provider"),
                str(payload.get("direction") or "pull"),
                str(payload.get("status") or "running"),
                str(payload.get("summary") or ""),
                _json_dumps(payload.get("raw_response") or {}, "{}"),
                created_at,
                timestamp,
            ),
        )
        row = connection.execute(
            "SELECT * FROM digital_human_sync_record WHERE sync_id = ?",
            (str(payload["sync_id"]),),
        ).fetchone()
    return dict(row) if row is not None else {}
