from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.dto.digital_human_dto import DigitalHumanGenerateRequestDTO
from app.services.digital_human.task_service import queue_video_task, read_video_task, run_video_task


def create_digital_human_video(request: DigitalHumanGenerateRequestDTO) -> dict[str, Any]:
    return queue_video_task(request)


def create_project_digital_human_task(*, project_id: str, request: DigitalHumanGenerateRequestDTO) -> dict[str, Any]:
    payload = request.model_dump()
    payload["projectId"] = project_id
    if not payload.get("workflowId"):
        payload["workflowId"] = project_id
    hydrated = DigitalHumanGenerateRequestDTO(**payload)
    return queue_video_task(hydrated)


def get_project_digital_human_task(project_id: str, task_id: str) -> dict[str, Any]:
    task = read_video_task(task_id)
    if project_id and task.get("projectId") and task["projectId"] != project_id:
        raise HTTPException(status_code=404, detail="数字人任务不存在")
    return task


def complete_project_digital_human_task(project_id: str, task_id: str) -> None:
    task = read_video_task(task_id)
    if project_id and task.get("projectId") and task["projectId"] != project_id:
        raise HTTPException(status_code=404, detail="数字人任务不存在")
    run_video_task(task_id)
