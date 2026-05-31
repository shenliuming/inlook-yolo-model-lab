from __future__ import annotations

import json
import shutil
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from ultralytics import YOLO
import os

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
MODELS_DIR = BACKEND_DIR / "models"
UPLOADS_DIR = BACKEND_DIR / "uploads"
OUTPUTS_DIR = BACKEND_DIR / "outputs"
REPORTS_DIR = BACKEND_DIR / "reports"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png"}
VIDEO_EXTENSIONS = {".mp4"}
VIDEO_CONTENT_TYPES = {"video/mp4"}
MAX_IMAGE_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_VIDEO_UPLOAD_BYTES = 200 * 1024 * 1024
MAX_REALTIME_FRAME_BYTES = 4 * 1024 * 1024
ARTIFACT_MAX_AGE_HOURS = 24
API_KEY = os.getenv("INLOOK_API_KEY", "").strip()
YOLO_CONFIG_DIR = Path(os.getenv("YOLO_CONFIG_DIR", "/tmp/Ultralytics"))
YOLO_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("YOLO_CONFIG_DIR", str(YOLO_CONFIG_DIR))

for directory in (UPLOADS_DIR, OUTPUTS_DIR, REPORTS_DIR):
    directory.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="沈柳名的AI 实验室 Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/outputs", StaticFiles(directory=OUTPUTS_DIR), name="outputs")
app.mount("/reports", StaticFiles(directory=REPORTS_DIR), name="reports")


class HealthResponse(BaseModel):
    status: str
    device: str
    message: str


class ModelInfo(BaseModel):
    id: str
    name: str
    type: str
    version: str
    description: str
    tag: str


class ModelsResponse(BaseModel):
    models: list[ModelInfo]


class DetectResponse(BaseModel):
    job_id: str
    status: str
    type: str
    result_url: str
    report_url: str
    report: dict[str, Any]


class RealtimeBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    class_id: int
    class_name: str
    confidence: float


class RealtimeDetectResponse(BaseModel):
    status: str
    model_id: str
    boxes: list[RealtimeBox]
    inference_time: float
    image_width: int
    image_height: int


RATE_LIMIT_RULES = {
    "health": (60, 60),
    "models": (60, 60),
    "image": (12, 60),
    "video": (6, 60),
    "realtime": (90, 60),
}
RATE_LIMIT_BUCKETS: dict[str, deque[float]] = defaultdict(deque)
RATE_LIMIT_LOCK = Lock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def runtime_device_label() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"


def runtime_device_arg() -> int | str:
    return 0 if torch.cuda.is_available() else "cpu"


def make_job_id() -> str:
    return f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def enforce_rate_limit(request: Request, scope: str) -> None:
    limit, window_seconds = RATE_LIMIT_RULES[scope]
    now = monotonic()
    client_ip = get_client_ip(request)
    bucket_key = f"{scope}:{client_ip}"

    with RATE_LIMIT_LOCK:
        bucket = RATE_LIMIT_BUCKETS[bucket_key]
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
        bucket.append(now)


def require_api_key(x_inlook_key: str | None) -> None:
    if not API_KEY:
        return
    if x_inlook_key != API_KEY:
        raise HTTPException(status_code=401, detail="内测口令无效")


def model_display_name(model_type: str, file_name: str) -> str:
    if model_type == "inlook" and file_name == "best.pt":
        return "INLOOK 三角洲模型"
    if model_type == "official" and file_name == "yolo26n.pt":
        return "官方轻快模型 YOLO26n"
    if model_type == "official" and file_name == "yolo26s.pt":
        return "官方高精度模型 YOLO26s"
    if model_type == "official" and file_name == "yolo11n.pt":
        return "官方通用模型 YOLO11n"
    if model_type == "official" and file_name == "yolo11s.pt":
        return "官方通用模型 YOLO11s"
    if model_type == "official" and file_name == "yolov8n.pt":
        return "官方基线模型 YOLOv8n"
    if model_type == "official":
        return f"官方模型 {Path(file_name).stem}"
    return f"{model_type.upper()} 模型 {Path(file_name).stem}"


def model_description(model_type: str, file_name: str) -> str:
    if model_type == "inlook" and file_name == "best.pt":
        return "适合测试三角洲游戏画面中的人物和目标框识别效果。"
    if model_type == "official" and file_name == "yolo26n.pt":
        return "官方轻量通用模型，实时扫一扫更流畅，适合摄像头识别优先使用。"
    if model_type == "official" and file_name == "yolo26s.pt":
        return "官方高精度通用模型，识别更稳，适合作为默认模型优先使用。"
    if model_type == "official" and file_name == "yolo11n.pt":
        return "官方轻量通用模型，启动快，适合图片和短视频的日常体验。"
    if model_type == "official" and file_name == "yolo11s.pt":
        return "官方标准通用模型，精度和速度更均衡，适合作为官方对照组。"
    if model_type == "official" and file_name == "yolov8n.pt":
        return "官方经典轻量基线模型，适合和当前 YOLO11 系列做直观对比。"
    if model_type == "official":
        return "适合识别人、车、动物、常见物体。普通图片或视频体验优先选这个。"
    return "用于本地 YOLO 推理测试。"


def model_version(model_type: str, file_name: str) -> str:
    if model_type == "inlook" and file_name == "best.pt":
        return "Delta v1 · best.pt"
    if model_type == "official" and file_name == "yolo26n.pt":
        return "YOLO26n · COCO"
    if model_type == "official" and file_name == "yolo26s.pt":
        return "YOLO26s · COCO"
    if model_type == "official" and file_name == "yolo11n.pt":
        return "YOLO11n · COCO"
    if model_type == "official" and file_name == "yolo11s.pt":
        return "YOLO11s · COCO"
    if model_type == "official" and file_name == "yolov8n.pt":
        return "YOLOv8n · COCO"
    if model_type == "official":
        return f"YOLO · {file_name}"
    return file_name


def model_tag(model_type: str) -> str:
    return "自研" if model_type == "inlook" else "通用"


def scan_models() -> list[ModelInfo]:
    models: list[ModelInfo] = []
    for model_type in ("official", "inlook"):
        model_dir = MODELS_DIR / model_type
        if not model_dir.exists():
            continue
        for model_path in sorted(model_dir.glob("*.pt")):
            models.append(
                ModelInfo(
                    id=f"{model_type}/{model_path.name}",
                    name=model_display_name(model_type, model_path.name),
                    type=model_type,
                    version=model_version(model_type, model_path.name),
                    description=model_description(model_type, model_path.name),
                    tag=model_tag(model_type),
                )
            )
    return models


def resolve_model_path(model_id: str) -> Path:
    model_map = {
        model.id: MODELS_DIR / model.type / Path(model.id).name
        for model in scan_models()
    }
    model_path = model_map.get(model_id)
    if model_path is None or not model_path.exists():
        raise HTTPException(status_code=404, detail=f"未找到模型：{model_id}")
    return model_path


@lru_cache(maxsize=8)
def load_model(model_path: str) -> YOLO:
    return YOLO(model_path)


def persist_upload(upload_file: UploadFile, target_path: Path, *, max_bytes: int) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    total_bytes = 0
    with target_path.open("wb") as buffer:
        while chunk := upload_file.file.read(1024 * 1024):
            total_bytes += len(chunk)
            if total_bytes > max_bytes:
                raise HTTPException(status_code=413, detail="上传文件过大")
            buffer.write(chunk)


async def read_limited_upload_bytes(upload_file: UploadFile, *, max_bytes: int) -> bytes:
    data = await upload_file.read()
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail="上传文件过大")
    return data


def ensure_allowed_upload(upload_file: UploadFile, *, allowed_extensions: set[str], allowed_content_types: set[str]) -> str:
    suffix = Path(upload_file.filename or "").suffix.lower()
    if suffix not in allowed_extensions:
        raise HTTPException(status_code=400, detail="文件类型不支持")
    if upload_file.content_type not in allowed_content_types:
        raise HTTPException(status_code=400, detail="文件内容类型不支持")
    return suffix


def validate_image_file(image_path: Path) -> None:
    image = cv2.imread(str(image_path))
    if image is None:
        raise HTTPException(status_code=400, detail="图片文件无效或已损坏")


def validate_video_file(video_path: Path) -> None:
    capture = cv2.VideoCapture(str(video_path))
    try:
        if not capture.isOpened():
            raise HTTPException(status_code=400, detail="视频文件无效或无法读取")
        ok, _ = capture.read()
        if not ok:
            raise HTTPException(status_code=400, detail="视频文件无效或没有可读帧")
    finally:
        capture.release()


def cleanup_artifacts() -> None:
    cutoff = datetime.now(timezone.utc).timestamp() - ARTIFACT_MAX_AGE_HOURS * 3600
    for directory in (UPLOADS_DIR, OUTPUTS_DIR):
        for child in directory.iterdir():
            try:
                if child.stat().st_mtime < cutoff:
                    if child.is_dir():
                        shutil.rmtree(child, ignore_errors=True)
                    else:
                        child.unlink(missing_ok=True)
            except FileNotFoundError:
                continue

    for report_file in REPORTS_DIR.glob("*.json"):
        try:
            if report_file.stat().st_mtime < cutoff:
                report_file.unlink(missing_ok=True)
        except FileNotFoundError:
            continue


def update_stats(summary: dict[str, Any], result: Any) -> None:
    boxes = getattr(result, "boxes", None)
    if boxes is None or boxes.conf is None or boxes.cls is None:
        return

    conf_values = [float(value) for value in boxes.conf.tolist()]
    cls_values = [int(value) for value in boxes.cls.tolist()]
    names = result.names or {}

    summary["detected_objects_count"] += len(conf_values)
    summary["confidence_values"].extend(conf_values)
    summary["classes_detected"].update(names.get(index, str(index)) for index in cls_values)


def serialize_boxes(result: Any) -> list[RealtimeBox]:
    boxes = getattr(result, "boxes", None)
    if boxes is None or boxes.xyxy is None or boxes.conf is None or boxes.cls is None:
      return []

    xyxy_values = boxes.xyxy.tolist()
    conf_values = boxes.conf.tolist()
    cls_values = boxes.cls.tolist()
    names = result.names or {}

    payload: list[RealtimeBox] = []
    for coords, conf, cls_index in zip(xyxy_values, conf_values, cls_values, strict=False):
        class_id = int(cls_index)
        payload.append(
            RealtimeBox(
                x1=round(float(coords[0]), 2),
                y1=round(float(coords[1]), 2),
                x2=round(float(coords[2]), 2),
                y2=round(float(coords[3]), 2),
                class_id=class_id,
                class_name=str(names.get(class_id, class_id)),
                confidence=round(float(conf), 4),
            )
        )
    return payload


def summarize_results(results: list[Any] | None = None, summary: dict[str, Any] | None = None) -> dict[str, Any]:
    working = summary or {
        "detected_objects_count": 0,
        "confidence_values": [],
        "classes_detected": set(),
    }
    if results:
        for result in results:
            update_stats(working, result)

    confidence_values = working["confidence_values"]
    avg_confidence = round(sum(confidence_values) / len(confidence_values), 4) if confidence_values else None
    return {
        "detected_objects_count": working["detected_objects_count"],
        "avg_confidence": avg_confidence,
        "classes_detected": sorted(working["classes_detected"]),
    }


def write_report(report_path: Path, payload: dict[str, Any]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def base_report(
    *,
    job_id: str,
    detect_type: str,
    model_id: str,
    input_path: Path,
    output_path: Path,
    conf: float,
    imgsz: int,
    start_time: str,
    end_time: str,
    elapsed_seconds: float,
    status: str,
    stats: dict[str, Any],
) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "type": detect_type,
        "model_id": model_id,
        "input_path": str(input_path),
        "output_path": str(output_path),
        "conf": conf,
        "imgsz": imgsz,
        "device": runtime_device_label(),
        "start_time": start_time,
        "end_time": end_time,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "status": status,
        **stats,
    }


def locate_generated_video(predict_dir: Path) -> Path:
    candidates = [path for path in predict_dir.rglob("*") if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS]
    if not candidates:
        raise HTTPException(status_code=500, detail="YOLO 未生成结果视频文件")
    return candidates[0]


@app.get("/api/health", response_model=HealthResponse)
def health_check(request: Request) -> HealthResponse:
    enforce_rate_limit(request, "health")
    return HealthResponse(
        status="ok",
        device=runtime_device_label(),
        message="沈柳名的AI 实验室 backend is running",
    )


@app.get("/api/models", response_model=ModelsResponse)
def list_models(request: Request) -> ModelsResponse:
    enforce_rate_limit(request, "models")
    return ModelsResponse(models=scan_models())


@app.post("/api/detect/image", response_model=DetectResponse)
async def detect_image(
    request: Request,
    file: UploadFile = File(...),
    model_id: str = Form(...),
    conf: float = Form(0.25),
    imgsz: int = Form(640),
    x_inlook_key: str | None = Header(default=None, alias="X-INLOOK-Key"),
) -> DetectResponse:
    enforce_rate_limit(request, "image")
    require_api_key(x_inlook_key)
    cleanup_artifacts()
    start_marker = now_iso()
    start_dt = datetime.now(timezone.utc)
    job_id = make_job_id()
    model_path = resolve_model_path(model_id)
    upload_dir = UPLOADS_DIR / job_id
    output_dir = OUTPUTS_DIR / job_id
    report_path = REPORTS_DIR / f"{job_id}.json"

    suffix = ensure_allowed_upload(
        file,
        allowed_extensions=IMAGE_EXTENSIONS,
        allowed_content_types=IMAGE_CONTENT_TYPES,
    )
    input_path = upload_dir / f"input{suffix}"
    persist_upload(file, input_path, max_bytes=MAX_IMAGE_UPLOAD_BYTES)
    validate_image_file(input_path)

    try:
        model = load_model(str(model_path))
        results = model.predict(
            source=str(input_path),
            conf=conf,
            imgsz=imgsz,
            device=runtime_device_arg(),
            verbose=False,
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "result.jpg"
        annotated = results[0].plot()
        cv2.imwrite(str(output_path), annotated)

        end_dt = datetime.now(timezone.utc)
        stats = summarize_results(results=results)
        report = base_report(
            job_id=job_id,
            detect_type="image",
            model_id=model_id,
            input_path=input_path,
            output_path=output_path,
            conf=conf,
            imgsz=imgsz,
            start_time=start_marker,
            end_time=now_iso(),
            elapsed_seconds=(end_dt - start_dt).total_seconds(),
            status="finished",
            stats=stats,
        )
        write_report(report_path, report)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"图片识别失败：{exc}") from exc
    finally:
        await file.close()

    return DetectResponse(
        job_id=job_id,
        status="finished",
        type="image",
        result_url=f"/outputs/{job_id}/result.jpg",
        report_url=f"/reports/{job_id}.json",
        report=report,
    )


@app.post("/api/detect/video", response_model=DetectResponse)
async def detect_video(
    request: Request,
    file: UploadFile = File(...),
    model_id: str = Form(...),
    conf: float = Form(0.25),
    imgsz: int = Form(640),
    x_inlook_key: str | None = Header(default=None, alias="X-INLOOK-Key"),
) -> DetectResponse:
    enforce_rate_limit(request, "video")
    require_api_key(x_inlook_key)
    cleanup_artifacts()
    start_marker = now_iso()
    start_dt = datetime.now(timezone.utc)
    job_id = make_job_id()
    model_path = resolve_model_path(model_id)
    upload_dir = UPLOADS_DIR / job_id
    output_dir = OUTPUTS_DIR / job_id
    report_path = REPORTS_DIR / f"{job_id}.json"

    ensure_allowed_upload(
        file,
        allowed_extensions=VIDEO_EXTENSIONS,
        allowed_content_types=VIDEO_CONTENT_TYPES,
    )
    input_path = upload_dir / "input.mp4"
    persist_upload(file, input_path, max_bytes=MAX_VIDEO_UPLOAD_BYTES)
    validate_video_file(input_path)

    try:
        model = load_model(str(model_path))
        summary = {
            "detected_objects_count": 0,
            "confidence_values": [],
            "classes_detected": set(),
        }
        result_stream = model.predict(
            source=str(input_path),
            conf=conf,
            imgsz=imgsz,
            device=runtime_device_arg(),
            save=True,
            project=str(output_dir),
            name="predict",
            exist_ok=True,
            stream=True,
            verbose=False,
        )
        for result in result_stream:
            update_stats(summary, result)

        generated_video = locate_generated_video(output_dir / "predict")
        output_path = output_dir / "result.mp4"
        shutil.move(str(generated_video), output_path)
        shutil.rmtree(output_dir / "predict", ignore_errors=True)

        end_dt = datetime.now(timezone.utc)
        stats = summarize_results(summary=summary)
        report = base_report(
            job_id=job_id,
            detect_type="video",
            model_id=model_id,
            input_path=input_path,
            output_path=output_path,
            conf=conf,
            imgsz=imgsz,
            start_time=start_marker,
            end_time=now_iso(),
            elapsed_seconds=(end_dt - start_dt).total_seconds(),
            status="finished",
            stats=stats,
        )
        write_report(report_path, report)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"视频识别失败：{exc}") from exc
    finally:
        await file.close()

    return DetectResponse(
        job_id=job_id,
        status="finished",
        type="video",
        result_url=f"/outputs/{job_id}/result.mp4",
        report_url=f"/reports/{job_id}.json",
        report=report,
    )


@app.post("/api/realtime/detect", response_model=RealtimeDetectResponse)
async def detect_realtime_frame(
    request: Request,
    file: UploadFile = File(...),
    model_id: str = Form(...),
    conf: float = Form(0.25),
    imgsz: int = Form(640),
    x_inlook_key: str | None = Header(default=None, alias="X-INLOOK-Key"),
) -> RealtimeDetectResponse:
    enforce_rate_limit(request, "realtime")
    require_api_key(x_inlook_key)
    model_path = resolve_model_path(model_id)

    try:
        ensure_allowed_upload(
            file,
            allowed_extensions=IMAGE_EXTENSIONS,
            allowed_content_types=IMAGE_CONTENT_TYPES,
        )
        frame_bytes = await read_limited_upload_bytes(file, max_bytes=MAX_REALTIME_FRAME_BYTES)
        image_array = np.frombuffer(frame_bytes, dtype=np.uint8)
        frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if frame is None:
            raise HTTPException(status_code=400, detail="无法解析上传的图片帧")

        model = load_model(str(model_path))
        results = model.predict(
            source=frame,
            conf=conf,
            imgsz=imgsz,
            device=runtime_device_arg(),
            verbose=False,
        )
        result = results[0]
        image_height, image_width = frame.shape[:2]
        speed = getattr(result, "speed", {}) or {}
        inference_time = round(float(speed.get("inference", 0.0)), 2)

        return RealtimeDetectResponse(
            status="ok",
            model_id=model_id,
            boxes=serialize_boxes(result),
            inference_time=inference_time,
            image_width=image_width,
            image_height=image_height,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"实时识别失败：{exc}") from exc
    finally:
        await file.close()
