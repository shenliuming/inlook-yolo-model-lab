from __future__ import annotations

from fastapi import APIRouter, File, Form, Header, Request, UploadFile
from fastapi.responses import FileResponse

from app.clients.yolo_client import enforce_rate_limit
from app.common.result import success
from app.config.settings import get_api_key
from app.services.task_service import get_vision_task, get_vision_task_file_path
from app.services.vision_service import (
    detect_image,
    detect_realtime_frame,
    detect_video,
    get_health_payload,
    list_models,
    select_model,
)

router = APIRouter(tags=["vision"])


def require_api_key(x_inlook_key: str | None) -> None:
    api_key = get_api_key()
    if not api_key:
        return
    if x_inlook_key != api_key:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="内测口令无效")


@router.get("/api/v1/vision/health")
def vision_health_check(request: Request):
    enforce_rate_limit(request, "health")
    return success(get_health_payload("INLOOK AI 视觉实验室 backend is running"))


@router.get("/api/v1/vision/models")
def list_vision_models(request: Request):
    enforce_rate_limit(request, "models")
    return success({"models": list_models()})


@router.post("/api/v1/vision/models/select")
def select_vision_model(payload: dict, request: Request):
    enforce_rate_limit(request, "models")
    return success(select_model(payload["model_id"]))


@router.post("/api/v1/vision/images/detect")
async def detect_vision_image(
    request: Request,
    file: UploadFile = File(...),
    model_id: str = Form(...),
    conf: float = Form(0.25),
    imgsz: int = Form(640),
    x_inlook_key: str | None = Header(default=None, alias="X-INLOOK-Key"),
):
    enforce_rate_limit(request, "image")
    require_api_key(x_inlook_key)
    return success(await detect_image(file, model_id, conf, imgsz))


@router.post("/api/v1/vision/videos/detect")
async def detect_vision_video(
    request: Request,
    file: UploadFile = File(...),
    model_id: str = Form(...),
    conf: float = Form(0.25),
    imgsz: int = Form(640),
    x_inlook_key: str | None = Header(default=None, alias="X-INLOOK-Key"),
):
    enforce_rate_limit(request, "video")
    require_api_key(x_inlook_key)
    return success(await detect_video(file, model_id, conf, imgsz))


@router.post("/api/v1/vision/realtime/detect")
async def detect_vision_realtime(
    request: Request,
    file: UploadFile = File(...),
    model_id: str = Form(...),
    conf: float = Form(0.25),
    imgsz: int = Form(640),
    x_inlook_key: str | None = Header(default=None, alias="X-INLOOK-Key"),
):
    enforce_rate_limit(request, "realtime")
    require_api_key(x_inlook_key)
    return success(await detect_realtime_frame(file, model_id, conf, imgsz))


@router.get("/api/v1/vision/tasks/{task_id}")
def read_vision_task(task_id: str, request: Request):
    enforce_rate_limit(request, "models")
    return success(get_vision_task(task_id))


@router.get("/api/v1/vision/tasks/{task_id}/files/{filename}")
def download_vision_task_file(task_id: str, filename: str):
    path = get_vision_task_file_path(task_id, filename)
    return FileResponse(path, filename=path.name)


@router.get("/api/vision/health")
def legacy_vision_health_check(request: Request):
    enforce_rate_limit(request, "health")
    return get_health_payload("INLOOK AI 视觉实验室 backend is running")


@router.get("/api/models")
@router.get("/api/vision/models")
def legacy_list_vision_models(request: Request):
    enforce_rate_limit(request, "models")
    return {"models": list_models()}


@router.post("/api/vision/models/select")
def legacy_select_vision_model(payload: dict, request: Request):
    enforce_rate_limit(request, "models")
    return select_model(payload["model_id"])


@router.post("/api/detect/image")
@router.post("/api/vision/image/detect")
async def legacy_detect_vision_image(
    request: Request,
    file: UploadFile = File(...),
    model_id: str = Form(...),
    conf: float = Form(0.25),
    imgsz: int = Form(640),
    x_inlook_key: str | None = Header(default=None, alias="X-INLOOK-Key"),
):
    enforce_rate_limit(request, "image")
    require_api_key(x_inlook_key)
    return await detect_image(file, model_id, conf, imgsz)


@router.post("/api/detect/video")
@router.post("/api/vision/video/detect")
async def legacy_detect_vision_video(
    request: Request,
    file: UploadFile = File(...),
    model_id: str = Form(...),
    conf: float = Form(0.25),
    imgsz: int = Form(640),
    x_inlook_key: str | None = Header(default=None, alias="X-INLOOK-Key"),
):
    enforce_rate_limit(request, "video")
    require_api_key(x_inlook_key)
    return await detect_video(file, model_id, conf, imgsz)


@router.post("/api/realtime/detect")
@router.post("/api/vision/realtime/detect")
async def legacy_detect_vision_realtime(
    request: Request,
    file: UploadFile = File(...),
    model_id: str = Form(...),
    conf: float = Form(0.25),
    imgsz: int = Form(640),
    x_inlook_key: str | None = Header(default=None, alias="X-INLOOK-Key"),
):
    enforce_rate_limit(request, "realtime")
    require_api_key(x_inlook_key)
    return await detect_realtime_frame(file, model_id, conf, imgsz)


@router.get("/api/vision/tasks/{task_id}")
def legacy_read_vision_task(task_id: str, request: Request):
    enforce_rate_limit(request, "models")
    return get_vision_task(task_id)


@router.get("/api/vision/tasks/{task_id}/files/{filename}")
def legacy_download_vision_task_file(task_id: str, filename: str):
    path = get_vision_task_file_path(task_id, filename)
    return FileResponse(path, filename=path.name)

