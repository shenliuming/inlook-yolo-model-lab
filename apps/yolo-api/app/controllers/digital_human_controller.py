from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile

from app.common.result import success
from app.dto.digital_human_dto import DigitalHumanGenerateRequestDTO
from app.services.digital_human.task_service import queue_video_task, read_video_task, read_video_tasks, run_video_task
from app.services.digital_human.template_service import (
    complete_template_import,
    create_template_import,
    read_templates,
    sync_remote_templates,
)

router = APIRouter(prefix="/api/v1/digital-human", tags=["digital-human"])


@router.get("/templates")
def list_digital_human_templates():
    return success(read_templates())


@router.post("/templates/import")
async def import_digital_human_template(
    file: UploadFile = File(...),
    name: str = Form(...),
    trainingType: str = Form("full"),
    resolution: str = Form("1080p"),
):
    payload = create_template_import(
        filename=file.filename or "template.mp4",
        content=await file.read(),
        name=name,
        training_type=trainingType,
        resolution_label=resolution,
    )
    return success(complete_template_import(payload["templateId"]))


@router.post("/templates/sync")
def sync_digital_human_templates():
    return success(sync_remote_templates())


@router.get("/tasks")
def list_digital_human_video_tasks(projectId: str | None = None):
    return success(read_video_tasks(project_id=projectId))


@router.get("/tasks/{task_id}")
def get_digital_human_video_task(task_id: str):
    return success(read_video_task(task_id))


@router.post("/generate")
def generate_digital_human_video(request: DigitalHumanGenerateRequestDTO, background_tasks: BackgroundTasks):
    task = queue_video_task(request)
    background_tasks.add_task(run_video_task, task["taskId"])
    return success(
        {
            "taskId": task["taskId"],
            "status": task["status"],
            "progress": task["progress"],
        }
    )
