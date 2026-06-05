from __future__ import annotations

import shutil
from datetime import datetime, timezone

import cv2
import numpy as np
from fastapi import HTTPException, UploadFile

from app.clients.yolo_client import (
    IMAGE_CONTENT_TYPES,
    IMAGE_EXTENSIONS,
    MAX_IMAGE_UPLOAD_BYTES,
    MAX_REALTIME_FRAME_BYTES,
    MAX_VIDEO_UPLOAD_BYTES,
    VIDEO_CONTENT_TYPES,
    VIDEO_EXTENSIONS,
    base_report,
    cleanup_artifacts,
    ensure_allowed_upload,
    load_model,
    locate_generated_video,
    make_job_id,
    persist_upload,
    read_limited_upload_bytes,
    resolve_model_path,
    runtime_device_arg,
    runtime_device_label,
    scan_models,
    serialize_boxes,
    summarize_results,
    update_stats,
    validate_image_file,
    validate_video_file,
    write_report,
)
from app.config.paths import OUTPUTS_DIR, REPORTS_DIR, UPLOADS_DIR
from app.utils.time_utils import now_iso


def get_health_payload(message: str) -> dict[str, str]:
    return {
        "status": "ok",
        "device": runtime_device_label(),
        "message": message,
    }


def list_models() -> list[dict[str, str]]:
    return scan_models()


def select_model(model_id: str) -> dict[str, object]:
    models = scan_models()
    selected = next((model for model in models if model["id"] == model_id), None)
    if selected is None:
        raise HTTPException(status_code=404, detail=f"未找到模型：{model_id}")
    resolve_model_path(model_id)
    return {
        "status": "ok",
        "model": selected,
    }


async def detect_image(file: UploadFile, model_id: str, conf: float, imgsz: int) -> dict[str, object]:
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

    return {
        "job_id": job_id,
        "status": "finished",
        "type": "image",
        "result_url": f"/outputs/{job_id}/result.jpg",
        "report_url": f"/reports/{job_id}.json",
        "report": report,
    }


async def detect_video(file: UploadFile, model_id: str, conf: float, imgsz: int) -> dict[str, object]:
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

    return {
        "job_id": job_id,
        "status": "finished",
        "type": "video",
        "result_url": f"/outputs/{job_id}/result.mp4",
        "report_url": f"/reports/{job_id}.json",
        "report": report,
    }


async def detect_realtime_frame(file: UploadFile, model_id: str, conf: float, imgsz: int) -> dict[str, object]:
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

        return {
            "status": "ok",
            "model_id": model_id,
            "boxes": serialize_boxes(result),
            "inference_time": inference_time,
            "image_width": image_width,
            "image_height": image_height,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"实时识别失败：{exc}") from exc
    finally:
        await file.close()

