from __future__ import annotations

from fastapi import APIRouter

from app.common.result import success
from app.tasks.studio_task_service import get_task, list_tasks

router = APIRouter(prefix="/api/v1", tags=["studio-tasks"])


@router.get("/tasks")
def read_task_list(limit: int = 50):
    return success(list_tasks(limit=limit))


@router.get("/tasks/{task_id}")
def read_task(task_id: str):
    return success(get_task(task_id))
