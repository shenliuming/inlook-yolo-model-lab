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


def _row_to_task(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    return {
        "task_id": row["task_id"],
        "template_id": row["template_id"],
        "workflow_id": row["workflow_id"],
        "project_id": row["project_id"],
        "provider_code": row["provider_code"],
        "provider_task_id": row["provider_task_id"],
        "mode": row["mode"],
        "status": row["status"],
        "progress": int(row["progress"] or 0),
        "script": row["script"],
        "audio_task_id": row["audio_task_id"],
        "audio_path": row["audio_path"],
        "audio_url": row["audio_url"],
        "output_path": row["output_path"],
        "output_url": row["output_url"],
        "cover_path": row["cover_path"],
        "cover_url": row["cover_url"],
        "run_log_path": row["run_log_path"],
        "error_message": row["error_message"],
        "downloads": _json_loads(row["downloads_json"], {}),
        "provider_payload": _json_loads(row["provider_payload_json"], {}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
    }


def list_video_tasks(*, project_id: str | None = None) -> list[dict[str, Any]]:
    query = """
        SELECT task.*, template.name AS template_name
        FROM digital_human_video_task AS task
        LEFT JOIN digital_human_template AS template ON template.template_id = task.template_id
    """
    params: list[Any] = []
    if project_id:
        query += " WHERE task.project_id = ?"
        params.append(project_id)
    query += " ORDER BY task.created_at DESC"
    with connection_scope() as connection:
        rows = connection.execute(query, tuple(params)).fetchall()
    result = []
    for row in rows:
        item = _row_to_task(row)
        item["template_name"] = row["template_name"] or ""
        result.append(item)
    return result


def get_video_task(task_id: str) -> dict[str, Any] | None:
    with connection_scope() as connection:
        row = connection.execute(
            """
            SELECT task.*, template.name AS template_name
            FROM digital_human_video_task AS task
            LEFT JOIN digital_human_template AS template ON template.template_id = task.template_id
            WHERE task.task_id = ?
            """,
            (task_id,),
        ).fetchone()
    if row is None:
        return None
    payload = _row_to_task(row)
    payload["template_name"] = row["template_name"] or ""
    return payload


def save_video_task(payload: dict[str, Any]) -> dict[str, Any]:
    timestamp = str(payload.get("updated_at") or _now())
    created_at = str(payload.get("created_at") or timestamp)
    with connection_scope() as connection:
        connection.execute(
            """
            INSERT INTO digital_human_video_task (
                task_id, template_id, workflow_id, project_id, provider_code, provider_task_id,
                mode, status, progress, script, audio_task_id, audio_path, audio_url,
                output_path, output_url, cover_path, cover_url, run_log_path,
                error_message, downloads_json, provider_payload_json, created_at,
                updated_at, started_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                template_id = excluded.template_id,
                workflow_id = excluded.workflow_id,
                project_id = excluded.project_id,
                provider_code = excluded.provider_code,
                provider_task_id = excluded.provider_task_id,
                mode = excluded.mode,
                status = excluded.status,
                progress = excluded.progress,
                script = excluded.script,
                audio_task_id = excluded.audio_task_id,
                audio_path = excluded.audio_path,
                audio_url = excluded.audio_url,
                output_path = excluded.output_path,
                output_url = excluded.output_url,
                cover_path = excluded.cover_path,
                cover_url = excluded.cover_url,
                run_log_path = excluded.run_log_path,
                error_message = excluded.error_message,
                downloads_json = excluded.downloads_json,
                provider_payload_json = excluded.provider_payload_json,
                updated_at = excluded.updated_at,
                started_at = excluded.started_at,
                completed_at = excluded.completed_at
            """,
            (
                str(payload["task_id"]),
                str(payload.get("template_id") or ""),
                str(payload.get("workflow_id") or ""),
                str(payload.get("project_id") or ""),
                str(payload.get("provider_code") or "local_provider"),
                str(payload.get("provider_task_id") or ""),
                str(payload.get("mode") or "auto"),
                str(payload.get("status") or "queued"),
                int(payload.get("progress") or 0),
                str(payload.get("script") or ""),
                str(payload.get("audio_task_id") or ""),
                str(payload.get("audio_path") or ""),
                str(payload.get("audio_url") or ""),
                str(payload.get("output_path") or ""),
                str(payload.get("output_url") or ""),
                str(payload.get("cover_path") or ""),
                str(payload.get("cover_url") or ""),
                str(payload.get("run_log_path") or ""),
                str(payload.get("error_message") or ""),
                _json_dumps(payload.get("downloads") or {}, "{}"),
                _json_dumps(payload.get("provider_payload") or {}, "{}"),
                created_at,
                timestamp,
                str(payload.get("started_at") or ""),
                str(payload.get("completed_at") or ""),
            ),
        )
    return get_video_task(str(payload["task_id"])) or {}


def save_workflow_task(payload: dict[str, Any]) -> dict[str, Any]:
    timestamp = str(payload.get("updated_at") or _now())
    created_at = str(payload.get("created_at") or timestamp)
    with connection_scope() as connection:
        connection.execute(
            """
            INSERT INTO studio_workflow_task (
                task_id, workflow_id, project_id, task_type, stage, source_type,
                status, progress, outputs_json, error_message, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                workflow_id = excluded.workflow_id,
                project_id = excluded.project_id,
                task_type = excluded.task_type,
                stage = excluded.stage,
                source_type = excluded.source_type,
                status = excluded.status,
                progress = excluded.progress,
                outputs_json = excluded.outputs_json,
                error_message = excluded.error_message,
                updated_at = excluded.updated_at
            """,
            (
                str(payload["task_id"]),
                str(payload.get("workflow_id") or ""),
                str(payload.get("project_id") or ""),
                str(payload.get("task_type") or "digital_human.generate"),
                str(payload.get("stage") or "数字人生成"),
                str(payload.get("source_type") or ""),
                str(payload.get("status") or "queued"),
                int(payload.get("progress") or 0),
                _json_dumps(payload.get("outputs") or {}, "{}"),
                str(payload.get("error_message") or ""),
                created_at,
                timestamp,
            ),
        )
        row = connection.execute(
            "SELECT * FROM studio_workflow_task WHERE task_id = ?",
            (str(payload["task_id"]),),
        ).fetchone()
    return dict(row) if row is not None else {}


def list_workflow_tasks(*, task_type: str | None = None) -> list[dict[str, Any]]:
    query = "SELECT * FROM studio_workflow_task"
    params: list[Any] = []
    if task_type:
        query += " WHERE task_type = ?"
        params.append(task_type)
    query += " ORDER BY created_at DESC"
    with connection_scope() as connection:
        rows = connection.execute(query, tuple(params)).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        payload["outputs"] = _json_loads(payload.pop("outputs_json", "{}"), {})
        items.append(payload)
    return items
