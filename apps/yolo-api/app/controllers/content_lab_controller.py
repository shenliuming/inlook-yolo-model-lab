from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, File, Form, Request, UploadFile
from fastapi.responses import FileResponse

from app.clients.yolo_client import enforce_rate_limit
from app.common.result import success
from app.services.material_intake_service import (
    create_material_task,
    get_material_file,
    get_material_task,
    intake_env_status,
)
from app.services.subtitle_workflow_service import (
    create_subtitle_task,
    get_subtitle_file,
    get_subtitle_task,
    reburn_subtitle_task,
    subtitle_env_status,
)

router = APIRouter(tags=["content-lab"])


@router.get("/api/v1/content-lab/health")
def content_lab_health(request: Request):
    enforce_rate_limit(request, "health")
    return success(
        {
            "status": "ok",
            "message": "INLOOK AI 内容工作流 backend is running",
        }
    )


@router.get("/api/v1/content-lab/materials/health")
def material_health():
    return success(
        {
            "status": "ok",
            "engines": intake_env_status(),
            "message": "INLOOK material intake module is running",
        }
    )


@router.post("/api/v1/content-lab/materials/tasks")
async def create_material_task_handler(
    background_tasks: BackgroundTasks,
    mode: Literal["text", "url", "upload"] = Form(...),
    text: str = Form(""),
    url: str = Form(""),
    engine: str = Form("auto"),
    file: UploadFile | None = File(default=None),
):
    return success(
        create_material_task(
            background_tasks=background_tasks,
            mode=mode,
            text=text,
            url=url,
            engine=engine,
            upload=file,
        )
    )


@router.get("/api/v1/content-lab/materials/tasks/{task_id}")
def read_material_task_handler(task_id: str):
    return success(get_material_task(task_id))


@router.get("/api/v1/content-lab/materials/tasks/{task_id}/files/{filename}")
def download_material_task_file_handler(task_id: str, filename: str):
    path = get_material_file(task_id, filename)
    return FileResponse(path, filename=path.name)


@router.get("/api/v1/content-lab/subtitles/health")
def subtitle_health():
    return success(
        {
            "status": "ok",
            "env": subtitle_env_status(),
            "message": "INLOOK subtitle workflow module is running",
        }
    )


@router.post("/api/v1/content-lab/subtitles/tasks")
async def create_subtitle_task_handler(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    audio: UploadFile | None = File(default=None),
    model: str = Form(default="small"),
    language: str = Form(default="zh"),
    device: str = Form(default="cpu"),
    compute_type: str = Form(default="int8"),
    beam_size: int = Form(default=5),
    width: int = Form(default=1080),
    height: int = Form(default=1920),
    font_size: int = Form(default=62),
    margin_v: int = Form(default=250),
    crf: int = Form(default=20),
):
    return success(
        create_subtitle_task(
            background_tasks=background_tasks,
            video=video,
            audio=audio,
            model=model,
            language=language,
            device=device,
            compute_type=compute_type,
            beam_size=beam_size,
            width=width,
            height=height,
            font_size=font_size,
            margin_v=margin_v,
            crf=crf,
        )
    )


@router.get("/api/v1/content-lab/subtitles/tasks/{task_id}")
def read_subtitle_task_handler(task_id: str):
    return success(get_subtitle_task(task_id))


@router.post("/api/v1/content-lab/subtitles/tasks/{task_id}/reburn")
async def reburn_subtitle_task_handler(
    task_id: str,
    ass: UploadFile | None = File(default=None),
    crf: int = Form(default=20),
):
    return success(reburn_subtitle_task(task_id=task_id, ass_upload=ass, crf=crf))


@router.get("/api/v1/content-lab/subtitles/tasks/{task_id}/files/{filename}")
def download_subtitle_task_file_handler(task_id: str, filename: str):
    path = get_subtitle_file(task_id, filename)
    return FileResponse(path, filename=path.name)


@router.get("/api/workflow/health")
def legacy_content_lab_health(request: Request):
    enforce_rate_limit(request, "health")
    return {
        "status": "ok",
        "device": "cpu",
        "message": "INLOOK AI 内容工作流 backend is running",
    }


for legacy_prefix in ("/api/materials", "/api/workflow/materials"):
    @router.get(f"{legacy_prefix}/health")
    def _legacy_material_health():
        return {
            "status": "ok",
            "engines": intake_env_status(),
            "message": "INLOOK material intake module is running",
        }

    @router.post(f"{legacy_prefix}/tasks")
    async def _legacy_create_material_task(
        background_tasks: BackgroundTasks,
        mode: Literal["text", "url", "upload"] = Form(...),
        text: str = Form(""),
        url: str = Form(""),
        engine: str = Form("auto"),
        file: UploadFile | None = File(default=None),
    ):
        return create_material_task(
            background_tasks=background_tasks,
            mode=mode,
            text=text,
            url=url,
            engine=engine,
            upload=file,
        )

    @router.get(f"{legacy_prefix}/tasks/{{task_id}}")
    def _legacy_read_material_task(task_id: str):
        return get_material_task(task_id)

    @router.get(f"{legacy_prefix}/tasks/{{task_id}}/files/{{filename}}")
    def _legacy_download_material_task_file(task_id: str, filename: str):
        path = get_material_file(task_id, filename)
        return FileResponse(path, filename=path.name)


@router.get("/api/workflow/subtitles/health")
def legacy_subtitle_health():
    return {
        "status": "ok",
        "env": subtitle_env_status(),
        "message": "INLOOK subtitle workflow module is running",
    }


@router.post("/api/workflow/subtitles/tasks")
async def legacy_create_subtitle_task(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    audio: UploadFile | None = File(default=None),
    model: str = Form(default="small"),
    language: str = Form(default="zh"),
    device: str = Form(default="cpu"),
    compute_type: str = Form(default="int8"),
    beam_size: int = Form(default=5),
    width: int = Form(default=1080),
    height: int = Form(default=1920),
    font_size: int = Form(default=62),
    margin_v: int = Form(default=250),
    crf: int = Form(default=20),
):
    return create_subtitle_task(
        background_tasks=background_tasks,
        video=video,
        audio=audio,
        model=model,
        language=language,
        device=device,
        compute_type=compute_type,
        beam_size=beam_size,
        width=width,
        height=height,
        font_size=font_size,
        margin_v=margin_v,
        crf=crf,
    )


@router.get("/api/workflow/subtitles/tasks/{task_id}")
def legacy_read_subtitle_task(task_id: str):
    return get_subtitle_task(task_id)


@router.post("/api/workflow/subtitles/tasks/{task_id}/reburn")
async def legacy_reburn_subtitle_task(
    task_id: str,
    ass: UploadFile | None = File(default=None),
    crf: int = Form(default=20),
):
    return reburn_subtitle_task(task_id=task_id, ass_upload=ass, crf=crf)


@router.get("/api/workflow/subtitles/tasks/{task_id}/files/{filename}")
def legacy_download_subtitle_task(task_id: str, filename: str):
    path = get_subtitle_file(task_id, filename)
    return FileResponse(path, filename=path.name)

