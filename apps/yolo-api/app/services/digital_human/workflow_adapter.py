from __future__ import annotations

from typing import Any

from app.services.digital_human.task_repository import save_workflow_task
from app.services.project_runtime_service import now, update_project, write_project_task


def sync_workflow_task(video_task: dict[str, Any]) -> dict[str, Any]:
    outputs = {
        "videoUrl": str(video_task.get("output_url") or ""),
        "downloads": video_task.get("downloads") or {},
        "templateId": str(video_task.get("template_id") or ""),
    }
    payload = {
        "task_id": str(video_task.get("task_id") or ""),
        "workflow_id": str(video_task.get("workflow_id") or ""),
        "project_id": str(video_task.get("project_id") or ""),
        "task_type": "digital_human.generate",
        "stage": "数字人生成",
        "source_type": str(video_task.get("mode") or "auto"),
        "status": str(video_task.get("status") or "queued"),
        "progress": int(video_task.get("progress") or 0),
        "outputs": outputs,
        "error_message": str(video_task.get("error_message") or ""),
        "created_at": str(video_task.get("created_at") or now()),
        "updated_at": str(video_task.get("updated_at") or now()),
    }
    save_workflow_task(payload)

    project_id = str(video_task.get("project_id") or "")
    if project_id:
        artifact = {
            "taskId": payload["task_id"],
            "status": payload["status"],
            "progress": payload["progress"],
            "videoUrl": outputs["videoUrl"],
            "downloads": outputs["downloads"],
            "templateId": outputs["templateId"],
            "errorMessage": payload["error_message"],
            "createdAt": payload["created_at"],
            "updatedAt": payload["updated_at"],
        }
        try:
            update_project(
                project_id,
                {
                    "current": {"digitalHumanTaskId": payload["task_id"]},
                    "artifacts": {"digitalHuman": artifact},
                },
            )
            write_project_task(
                project_id,
                {
                    "taskId": payload["task_id"],
                    "taskType": "digital_human.generate",
                    "sourceType": payload["source_type"],
                    "status": payload["status"],
                    "stage": payload["stage"],
                    "progress": payload["progress"],
                    "outputs": outputs,
                    "errorMessage": payload["error_message"],
                    "createdAt": payload["created_at"],
                    "updatedAt": payload["updated_at"],
                },
            )
        except Exception:
            pass
    return payload
