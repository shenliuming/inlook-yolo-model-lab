from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.clients.chanjing_client import ChanjingApiError
from app.config.paths import CHANJING_POC_RUNTIME_DIR
from app.config import settings
from app.services.digital_human_engines.chanjing_engine import ChanjingDigitalHumanEngine, chanjing_engine, estimate_duration_seconds

logger = logging.getLogger("inlook.yolo_api.chanjing")

try:
    from app.db.repositories import (
        get_digital_human_job,
        list_digital_human_jobs,
        list_digital_human_persons,
        upsert_digital_human_job,
        upsert_digital_human_person,
    )
except Exception:  # pragma: no cover - runtime fallback when SQLAlchemy is unavailable
    get_digital_human_job = None
    list_digital_human_jobs = None
    list_digital_human_persons = None
    upsert_digital_human_job = None
    upsert_digital_human_person = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _job_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _append_log(job_id: str, message: str) -> None:
    path = _job_dir(job_id) / "logs.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", errors="ignore") as file:
        file.write(message)
        if not message.endswith("\n"):
            file.write("\n")


def _job_dir(job_id: str) -> Path:
    return CHANJING_POC_RUNTIME_DIR / job_id


def _job_json_path(job_id: str) -> Path:
    return _job_dir(job_id) / "job.json"


def _job_template(job_id: str) -> dict[str, Any]:
    timestamp = _now()
    return {
        "job_id": job_id,
        "engine": "chanjing_custom_person",
        "job_type": "training",
        "status": "created",
        "trace_id": "",
        "local_video_path": "",
        "file_id": "",
        "file_full_path": "",
        "person_name": "",
        "train_type": "both",
        "chanjing_person_id": "",
        "audio_man_id": "",
        "pic_url": "",
        "preview_url": "",
        "person_width": 0,
        "person_height": 0,
        "support_4k": False,
        "audio_type": "audio",
        "wav_url": "",
        "audio_file_id": "",
        "text": "",
        "screen_width": 1080,
        "screen_height": 1920,
        "person_x": 0,
        "person_y": 0,
        "model": 0,
        "resolution_rate": 0,
        "add_compliance_watermark": False,
        "hide_subtitle": False,
        "bg_color": "",
        "estimated_duration_seconds": 0,
        "chanjing_video_id": "",
        "video_url": "",
        "duration": 0,
        "subtitle_data_url": "",
        "local_output_path": "",
        "error": None,
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def _init_job_runtime(job_id: str) -> None:
    for child in (
        _job_dir(job_id),
        _job_dir(job_id) / "input",
        _job_dir(job_id) / "upload",
        _job_dir(job_id) / "training",
        _job_dir(job_id) / "video",
        _job_dir(job_id) / "output",
    ):
        child.mkdir(parents=True, exist_ok=True)


def _save_job(job: dict[str, Any]) -> dict[str, Any]:
    job["updated_at"] = _now()
    path = _job_json_path(str(job["job_id"]))
    _write_json(path, job)
    _sync_job_to_db(job, path)
    return job


def _load_job(job_id: str) -> dict[str, Any]:
    path = _job_json_path(job_id)
    if not path.exists():
        raise FileNotFoundError(f"蝉镜 POC 任务不存在: {job_id}")
    return _read_json(path)


def _set_trace(job: dict[str, Any], body: dict[str, Any] | None) -> None:
    trace_id = str((body or {}).get("trace_id") or "").strip()
    if trace_id:
        job["trace_id"] = trace_id


def _set_error(job: dict[str, Any], exc: Exception, *, status: str = "failed") -> dict[str, Any]:
    trace_id = exc.trace_id if isinstance(exc, ChanjingApiError) else str(job.get("trace_id") or "")
    job["status"] = status
    job["error"] = {
        "type": type(exc).__name__,
        "message": str(exc),
        "trace_id": trace_id,
        "code": exc.code if isinstance(exc, ChanjingApiError) else None,
        "http_status": exc.http_status if isinstance(exc, ChanjingApiError) else None,
        "response_json": exc.response_json if isinstance(exc, ChanjingApiError) else None,
    }
    if trace_id:
        job["trace_id"] = trace_id
    _append_log(str(job["job_id"]), f"[ERROR] {type(exc).__name__}: {exc}")
    return _save_job(job)


def _persist_exchange(job_id: str, relative_path: str, exchange: dict[str, Any]) -> None:
    _write_json(_job_dir(job_id) / relative_path, exchange)


def _persist_transfer(job_id: str, relative_path: str, transfer: dict[str, Any]) -> None:
    _write_json(_job_dir(job_id) / relative_path, transfer)


def _safe_db_call(callback: Any, *args: Any, **kwargs: Any) -> Any:
    if callback is None:
        return None
    try:
        return callback(*args, **kwargs)
    except Exception as exc:
        logger.exception("SQLite sync failed: %s", exc)
        return None


def _sync_job_to_db(job: dict[str, Any], path: Path) -> None:
    error = job.get("error") if isinstance(job.get("error"), dict) else {}
    payload = {
        "job_id": str(job.get("job_id") or ""),
        "engine": "chanjing",
        "job_type": str(job.get("job_type") or "training"),
        "status": str(job.get("status") or "created"),
        "person_id": str(job.get("chanjing_person_id") or ""),
        "person_name": str(job.get("person_name") or ""),
        "audio_man_id": str(job.get("audio_man_id") or ""),
        "local_video_path": str(job.get("local_video_path") or ""),
        "wav_url": str(job.get("wav_url") or ""),
        "text": str(job.get("text") or ""),
        "chanjing_file_id": str(job.get("file_id") or ""),
        "chanjing_video_id": str(job.get("chanjing_video_id") or ""),
        "video_url": str(job.get("video_url") or ""),
        "local_output_path": str(job.get("local_output_path") or ""),
        "trace_id": str(job.get("trace_id") or ""),
        "error_message": str(error.get("message") or ""),
        "raw_job_json_path": str(path),
    }
    _safe_db_call(upsert_digital_human_job, payload)


def _sync_person_to_db(job: dict[str, Any], raw_response_json: dict[str, Any] | None = None, *, source: str = "api") -> None:
    person_id = str(job.get("chanjing_person_id") or "")
    if not person_id:
        return
    status_map = {
        "training": "training",
        "uploaded": "training",
        "training_succeeded": "ready",
        "succeeded": "ready",
        "training_failed": "failed",
        "failed": "failed",
    }
    payload = {
        "engine": "chanjing",
        "person_id": person_id,
        "name": str(job.get("person_name") or ""),
        "status": status_map.get(str(job.get("status") or ""), "training"),
        "audio_man_id": str(job.get("audio_man_id") or ""),
        "pic_url": str(job.get("pic_url") or ""),
        "preview_url": str(job.get("preview_url") or ""),
        "width": int(job.get("person_width") or 0),
        "height": int(job.get("person_height") or 0),
        "support_4k": bool(job.get("support_4k", False)),
        "train_type": str(job.get("train_type") or "both"),
        "source": source,
        "raw_response_json": raw_response_json or {},
    }
    _safe_db_call(upsert_digital_human_person, payload)


def _extract_list_items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        for key in ("list", "items", "records"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def _extract_data(body: dict[str, Any]) -> dict[str, Any]:
    return body.get("data") if isinstance(body.get("data"), dict) else {}


def _safe_read_runtime_job(path_value: str) -> dict[str, Any]:
    path = Path(str(path_value or "")).expanduser()
    if not path.exists() or not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _extract_person_id_from_create_response(body: dict[str, Any]) -> str:
    data = body.get("data")
    if isinstance(data, str):
        return data.strip()
    if isinstance(data, dict):
        return str(data.get("id") or data.get("person_id") or "").strip()
    return ""


def _normalize_training_status(data: dict[str, Any]) -> str:
    status = data.get("status")
    try:
        value = int(status)
    except (TypeError, ValueError):
        return "training_unknown"
    if value == 0:
        return "training"
    if value == 1:
        return "training_succeeded"
    return "training_unknown"


def _normalize_video_status(data: dict[str, Any]) -> str:
    try:
        status = int(data.get("status"))
    except (TypeError, ValueError):
        return "video_unknown"
    if status == 10:
        return "video_processing"
    if status == 30:
        return "succeeded"
    if 40 <= status <= 49:
        return "failed_param"
    if 50 <= status <= 59:
        return "failed_server"
    return "video_unknown"


def _update_person_fields(job: dict[str, Any], data: dict[str, Any]) -> None:
    job["chanjing_person_id"] = str(data.get("id") or data.get("person_id") or job.get("chanjing_person_id") or "")
    job["person_name"] = str(data.get("name") or job.get("person_name") or "")
    job["audio_man_id"] = str(data.get("audio_man_id") or job.get("audio_man_id") or "")
    job["pic_url"] = str(data.get("pic_url") or job.get("pic_url") or "")
    job["preview_url"] = str(data.get("preview_url") or job.get("preview_url") or "")
    job["person_width"] = int(data.get("width") or job.get("person_width") or 0)
    job["person_height"] = int(data.get("height") or job.get("person_height") or 0)
    job["support_4k"] = bool(data.get("support_4k") if data.get("support_4k") is not None else job.get("support_4k"))
    reason = ""
    for key in ("err_reason", "reason", "msg"):
        value = str(data.get(key) or "").strip()
        if value:
            reason = value
            break
    if reason and _normalize_training_status(data) != "training_succeeded":
        job["error"] = {"message": reason, "trace_id": job.get("trace_id") or ""}


def _update_video_fields(job: dict[str, Any], data: dict[str, Any]) -> None:
    job["chanjing_video_id"] = str(data.get("id") or data.get("video_id") or job.get("chanjing_video_id") or "")
    job["preview_url"] = str(data.get("preview_url") or job.get("preview_url") or "")
    job["video_url"] = str(data.get("video_url") or job.get("video_url") or "")
    job["duration"] = float(data.get("duration") or job.get("duration") or 0)
    job["subtitle_data_url"] = str(data.get("subtitle_data_url") or job.get("subtitle_data_url") or "")


def _extract_video_id_from_response(body: dict[str, Any]) -> str:
    data = body.get("data")
    if isinstance(data, str):
        return data.strip()
    if isinstance(data, dict):
        return str(data.get("id") or data.get("video_id") or "").strip()
    return ""


def _create_training_payload(job: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(payload["local_video_path"])).expanduser().resolve()
    return {
        "local_video_path": str(path),
        "name": str(payload["name"]),
        "train_type": str(payload.get("train_type") or "both"),
        "callback": str(payload.get("callback") or ""),
        "error_skip": bool(payload.get("error_skip", False)),
        "resolution_rate": int(payload.get("resolution_rate") or 0),
        "language": str(payload.get("language") or "cn"),
        "version": str(payload.get("version") or "1.0"),
        "auth_text": payload.get("auth_text"),
        "auth_video_file_id": payload.get("auth_video_file_id"),
    }


def _create_video_payload(job: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    text = str(payload.get("text") or "")
    language = str(payload.get("language") or "cn")
    return {
        "person_id": str(payload.get("person_id") or job.get("chanjing_person_id") or ""),
        "audio_type": str(payload.get("audio_type") or job.get("audio_type") or "audio"),
        "text": text,
        "wav_url": str(payload.get("wav_url") or job.get("wav_url") or ""),
        "audio_file_id": str(payload.get("audio_file_id") or job.get("audio_file_id") or ""),
        "audio_man_id": str(payload.get("audio_man_id") or job.get("audio_man_id") or ""),
        "figure_type": payload.get("figure_type"),
        "screen_width": int(payload.get("screen_width") or 1080),
        "screen_height": int(payload.get("screen_height") or 1920),
        "person_x": int(payload.get("person_x") or 0),
        "person_y": int(payload.get("person_y") or 0),
        "person_width": payload.get("person_width"),
        "person_height": payload.get("person_height"),
        "model": int(payload.get("model") or 0),
        "resolution_rate": int(payload.get("resolution_rate") or 0),
        "add_compliance_watermark": bool(payload.get("add_compliance_watermark", False)),
        "hide_subtitle": bool(payload.get("hide_subtitle", False)),
        "bg_color": payload.get("bg_color"),
        "estimated_duration_seconds": estimate_duration_seconds(text, language),
    }


def _run_training_bootstrap(
    job: dict[str, Any],
    payload: dict[str, Any],
    engine: ChanjingDigitalHumanEngine,
) -> dict[str, Any]:
    job_id = str(job["job_id"])
    training_payload = _create_training_payload(job, payload)
    local_video_path = Path(training_payload["local_video_path"])
    job["local_video_path"] = str(local_video_path)
    job["person_name"] = training_payload["name"]
    job["train_type"] = training_payload["train_type"]
    _save_job(job)
    if not local_video_path.exists() or not local_video_path.is_file():
        raise ChanjingApiError(f"local_video_path 不存在: {local_video_path}")
    destination = _job_dir(job_id) / "input" / "template.mp4"
    destination.write_bytes(local_video_path.read_bytes())
    job["status"] = "uploading"
    _append_log(job_id, f"[INFO] 开始上传训练视频: {local_video_path}")
    upload_result = engine.upload_custom_person_video(str(local_video_path))
    _persist_exchange(job_id, "upload/create_upload_url_request.json", engine.client.last_exchange)
    _persist_exchange(job_id, "upload/create_upload_url_response.json", upload_result["response"])
    _persist_transfer(job_id, "upload/upload_signed_url.json", engine.client.last_transfer)
    job["trace_id"] = str(upload_result["response"].get("trace_id") or "")
    job["file_id"] = str(upload_result.get("file_id") or "")
    job["file_full_path"] = str(upload_result.get("sign_url") or "")
    _save_job(job)

    engine.wait_file_ready(job["file_id"])
    detail_body = engine.client.file_detail(job["file_id"])
    _persist_exchange(job_id, "upload/file_detail_response.json", engine.client.last_exchange)
    list_body = engine.client.file_list(service="customised_person", file_id=job["file_id"])
    _persist_exchange(job_id, "upload/file_list_response.json", engine.client.last_exchange)
    _set_trace(job, detail_body)
    _set_trace(job, list_body)
    job["status"] = "uploaded"
    _save_job(job)

    training_request = {
        "name": training_payload["name"],
        "file_id": job["file_id"],
        "train_type": training_payload["train_type"],
        "callback": training_payload["callback"],
        "error_skip": training_payload["error_skip"],
        "resolution_rate": training_payload["resolution_rate"],
        "language": training_payload["language"],
        "version": training_payload["version"],
    }
    if training_payload.get("auth_text"):
        training_request["auth_text"] = training_payload["auth_text"]
    if training_payload.get("auth_video_file_id"):
        training_request["auth_video_file_id"] = training_payload["auth_video_file_id"]
    _write_json(_job_dir(job_id) / "training" / "create_customised_person_request.json", training_request)
    body = engine.create_custom_person_training_job(**training_request)
    _persist_exchange(job_id, "training/create_customised_person_response.json", engine.client.last_exchange)
    _set_trace(job, body)
    job["chanjing_person_id"] = _extract_person_id_from_create_response(body)
    _update_person_fields(job, _extract_data(body))
    if not job["chanjing_person_id"]:
        raise ChanjingApiError("创建训练任务成功但未返回 person_id", trace_id=str(body.get("trace_id") or ""), response_json=body)
    job["status"] = "training"
    job["error"] = None
    _append_log(job_id, f"[INFO] 训练任务已提交 person_id={job['chanjing_person_id']}")
    return _save_job(job)


def create_chanjing_training_poc_job(payload: dict[str, Any], engine: ChanjingDigitalHumanEngine | None = None) -> dict[str, Any]:
    runtime_engine = engine or chanjing_engine
    job_id = _job_id("cj_train")
    _init_job_runtime(job_id)
    job = _job_template(job_id)
    job["job_type"] = "training"
    _write_json(_job_dir(job_id) / "input" / "request.json", payload)
    try:
        return _run_training_bootstrap(job, payload, runtime_engine)
    except Exception as exc:
        return _set_error(job, exc, status="training_failed")


def get_chanjing_training_poc_job(job_id: str) -> dict[str, Any]:
    return _load_job(job_id)


def poll_chanjing_training_poc_job(job_id: str, engine: ChanjingDigitalHumanEngine | None = None) -> dict[str, Any]:
    runtime_engine = engine or chanjing_engine
    job = _load_job(job_id)
    try:
        if not job.get("chanjing_person_id"):
            raise ChanjingApiError("当前训练任务缺少 chanjing_person_id")
        body = runtime_engine.poll_custom_person(str(job["chanjing_person_id"]))
        _persist_exchange(job_id, "training/customised_person_poll_response.json", runtime_engine.client.last_exchange)
        _set_trace(job, body)
        data = _extract_data(body)
        _update_person_fields(job, data)
        normalized = _normalize_training_status(data)
        if normalized == "training_succeeded":
            job["status"] = "training_succeeded"
            job["error"] = None
            _sync_person_to_db(job, body, source="web")
        elif normalized == "training":
            job["status"] = "training"
        else:
            job["status"] = "training_failed"
            reason = ""
            for key in ("err_reason", "reason", "msg"):
                value = str(data.get(key) or "").strip()
                if value:
                    reason = value
                    break
            job["error"] = {"message": reason or "训练状态未知", "trace_id": job.get("trace_id") or ""}
        return _save_job(job)
    except Exception as exc:
        return _set_error(job, exc, status="training_failed")


def create_chanjing_video_poc_job(payload: dict[str, Any], engine: ChanjingDigitalHumanEngine | None = None) -> dict[str, Any]:
    runtime_engine = engine or chanjing_engine
    job_id = _job_id("cj_video")
    _init_job_runtime(job_id)
    job = _job_template(job_id)
    job["job_type"] = "video"
    _write_json(_job_dir(job_id) / "video" / "request.json", payload)
    try:
        video_payload = _create_video_payload(job, payload)
        job["status"] = "video_submitted"
        job["chanjing_person_id"] = video_payload["person_id"]
        job["audio_type"] = video_payload["audio_type"]
        job["wav_url"] = video_payload["wav_url"]
        job["audio_file_id"] = video_payload["audio_file_id"]
        job["text"] = video_payload["text"]
        job["audio_man_id"] = video_payload["audio_man_id"]
        job["screen_width"] = video_payload["screen_width"]
        job["screen_height"] = video_payload["screen_height"]
        job["person_x"] = video_payload["person_x"]
        job["person_y"] = video_payload["person_y"]
        job["person_width"] = video_payload["person_width"] or video_payload["screen_width"]
        job["person_height"] = video_payload["person_height"] or video_payload["screen_height"]
        job["model"] = video_payload["model"]
        job["resolution_rate"] = video_payload["resolution_rate"]
        job["add_compliance_watermark"] = video_payload["add_compliance_watermark"]
        job["hide_subtitle"] = video_payload["hide_subtitle"]
        job["bg_color"] = video_payload["bg_color"] or ""
        job["estimated_duration_seconds"] = video_payload["estimated_duration_seconds"]
        request_payload = {key: value for key, value in video_payload.items() if key != "estimated_duration_seconds"}
        _write_json(_job_dir(job_id) / "video" / "create_video_request.json", request_payload)
        body = runtime_engine.create_video_job(**request_payload)
        _persist_exchange(job_id, "video/create_video_response.json", runtime_engine.client.last_exchange)
        _set_trace(job, body)
        data = _extract_data(body)
        _update_video_fields(job, data)
        if not job["chanjing_video_id"]:
            job["chanjing_video_id"] = _extract_video_id_from_response(body)
        if not job["chanjing_video_id"]:
            raise ChanjingApiError("创建视频任务成功但未返回 video_id", trace_id=str(body.get("trace_id") or ""), response_json=body)
        _append_log(job_id, f"[INFO] 视频任务已提交 video_id={job['chanjing_video_id']}")
        return _save_job(job)
    except Exception as exc:
        return _set_error(job, exc, status="failed")


def get_chanjing_video_poc_job(job_id: str) -> dict[str, Any]:
    return _load_job(job_id)


def poll_chanjing_video_poc_job(job_id: str, engine: ChanjingDigitalHumanEngine | None = None) -> dict[str, Any]:
    runtime_engine = engine or chanjing_engine
    job = _load_job(job_id)
    try:
        if not job.get("chanjing_video_id"):
            raise ChanjingApiError("当前视频任务缺少 chanjing_video_id")
        body = runtime_engine.poll_video(str(job["chanjing_video_id"]))
        _persist_exchange(job_id, "video/video_poll_response.json", runtime_engine.client.last_exchange)
        _set_trace(job, body)
        data = _extract_data(body)
        _update_video_fields(job, data)
        normalized = _normalize_video_status(data)
        if normalized == "succeeded":
            output_path = _job_dir(job_id) / "output" / "output.mp4"
            runtime_engine.download_result(str(job.get("video_url") or ""), str(output_path))
            _persist_transfer(job_id, "video/download_video.json", runtime_engine.client.last_transfer)
            job["local_output_path"] = str(output_path)
            job["status"] = "succeeded"
            job["error"] = None
            _append_log(job_id, f"[DONE] 视频下载完成: {output_path}")
        elif normalized == "video_processing":
            job["status"] = "video_processing"
        else:
            job["status"] = "failed"
            reason = str(data.get("msg") or "").strip() or normalized
            job["error"] = {"message": reason, "trace_id": job.get("trace_id") or ""}
        return _save_job(job)
    except Exception as exc:
        return _set_error(job, exc, status="failed")


def create_chanjing_full_poc_job(payload: dict[str, Any], engine: ChanjingDigitalHumanEngine | None = None) -> dict[str, Any]:
    runtime_engine = engine or chanjing_engine
    job_id = _job_id("cj_full")
    _init_job_runtime(job_id)
    job = _job_template(job_id)
    job["job_type"] = "full_poc"
    _write_json(_job_dir(job_id) / "input" / "request.json", payload)
    try:
        video_payload = _create_video_payload(job, payload)
        job["audio_type"] = video_payload["audio_type"]
        job["wav_url"] = video_payload["wav_url"]
        job["audio_file_id"] = video_payload["audio_file_id"]
        job["text"] = video_payload["text"]
        job["audio_man_id"] = video_payload["audio_man_id"]
        job["screen_width"] = video_payload["screen_width"]
        job["screen_height"] = video_payload["screen_height"]
        job["person_x"] = video_payload["person_x"]
        job["person_y"] = video_payload["person_y"]
        job["person_width"] = video_payload["person_width"] or video_payload["screen_width"]
        job["person_height"] = video_payload["person_height"] or video_payload["screen_height"]
        job["model"] = video_payload["model"]
        job["resolution_rate"] = video_payload["resolution_rate"]
        job["add_compliance_watermark"] = video_payload["add_compliance_watermark"]
        job["hide_subtitle"] = video_payload["hide_subtitle"]
        job["bg_color"] = video_payload["bg_color"] or ""
        job["estimated_duration_seconds"] = video_payload["estimated_duration_seconds"]
        return _run_training_bootstrap(job, payload, runtime_engine)
    except Exception as exc:
        return _set_error(job, exc, status="failed")


def get_chanjing_full_poc_job(job_id: str) -> dict[str, Any]:
    return _load_job(job_id)


def poll_chanjing_full_poc_job(job_id: str, engine: ChanjingDigitalHumanEngine | None = None) -> dict[str, Any]:
    runtime_engine = engine or chanjing_engine
    job = _load_job(job_id)
    try:
        status = str(job.get("status") or "")
        if status in {"created", "uploading", "uploaded", "training"}:
            return poll_chanjing_training_poc_job(job_id, engine=runtime_engine)
        if status == "training_succeeded":
            payload = {
                "person_id": job.get("chanjing_person_id"),
                "audio_type": job.get("audio_type"),
                "wav_url": job.get("wav_url"),
                "audio_file_id": job.get("audio_file_id"),
                "audio_man_id": job.get("audio_man_id"),
                "text": job.get("text"),
                "screen_width": job.get("screen_width") or 1080,
                "screen_height": job.get("screen_height") or 1920,
                "person_x": job.get("person_x") or 0,
                "person_y": job.get("person_y") or 0,
                "person_width": job.get("person_width") or 1080,
                "person_height": job.get("person_height") or 1920,
                "model": job.get("model") or 0,
                "resolution_rate": job.get("resolution_rate") or 0,
                "add_compliance_watermark": bool(job.get("add_compliance_watermark", False)),
                "hide_subtitle": bool(job.get("hide_subtitle", False)),
                "bg_color": job.get("bg_color") or "",
            }
            body = runtime_engine.create_video_job(
                person_id=str(payload["person_id"] or ""),
                audio_type=str(payload["audio_type"] or "audio"),
                wav_url=str(payload["wav_url"] or ""),
                audio_file_id=str(payload["audio_file_id"] or ""),
                audio_man_id=str(payload["audio_man_id"] or ""),
                text=str(payload["text"] or ""),
                screen_width=int(payload["screen_width"] or 1080),
                screen_height=int(payload["screen_height"] or 1920),
                person_x=int(payload["person_x"] or 0),
                person_y=int(payload["person_y"] or 0),
                person_width=int(payload["person_width"] or 1080),
                person_height=int(payload["person_height"] or 1920),
                model=int(payload["model"] or 0),
                resolution_rate=int(payload["resolution_rate"] or 0),
                add_compliance_watermark=bool(payload["add_compliance_watermark"]),
                hide_subtitle=bool(payload["hide_subtitle"]),
                bg_color=str(payload["bg_color"] or "") or None,
            )
            _write_json(_job_dir(job_id) / "video" / "create_video_request.json", payload)
            _persist_exchange(job_id, "video/create_video_response.json", runtime_engine.client.last_exchange)
            _set_trace(job, body)
            _update_video_fields(job, _extract_data(body))
            if not job["chanjing_video_id"]:
                job["chanjing_video_id"] = _extract_video_id_from_response(body)
            job["status"] = "video_submitted"
            return _save_job(job)
        if status in {"video_submitted", "video_processing"}:
            return poll_chanjing_video_poc_job(job_id, engine=runtime_engine)
        return job
    except Exception as exc:
        return _set_error(job, exc, status="failed")


def list_chanjing_common_persons(page: int = 1, size: int = 20, *, engine: ChanjingDigitalHumanEngine | None = None) -> dict[str, Any]:
    runtime_engine = engine or chanjing_engine
    runtime_engine.ensure_access_token()
    return runtime_engine.client.list_common_dp(page=page, size=size)


def list_chanjing_common_audios(page: int = 1, size: int = 20, *, engine: ChanjingDigitalHumanEngine | None = None) -> dict[str, Any]:
    runtime_engine = engine or chanjing_engine
    runtime_engine.ensure_access_token()
    return runtime_engine.client.list_common_audio(page=page, size=size)


def list_chanjing_custom_persons(page: int = 1, page_size: int = 20, *, engine: ChanjingDigitalHumanEngine | None = None) -> dict[str, Any]:
    runtime_engine = engine or chanjing_engine
    runtime_engine.ensure_access_token()
    return runtime_engine.client.list_customised_person(page=page, page_size=page_size)


def get_chanjing_config_status() -> dict[str, Any]:
    return {
        "configured": bool(settings.get_chanjing_app_id() and settings.get_chanjing_secret_key()),
        "has_app_id": bool(settings.get_chanjing_app_id()),
        "has_secret_key": bool(settings.get_chanjing_secret_key()),
        "api_base_url": settings.get_chanjing_api_base_url(),
        "api_base_path": settings.get_chanjing_api_base_path(),
        "default_model": settings.get_chanjing_default_model(),
        "default_screen_width": settings.get_chanjing_default_screen_width(),
        "default_screen_height": settings.get_chanjing_default_screen_height(),
    }


def create_chanjing_training_upload_job(
    *,
    filename: str,
    content: bytes,
    name: str,
    train_type: str = "both",
    resolution_rate: int = 0,
    language: str = "cn",
    error_skip: bool = False,
    engine: ChanjingDigitalHumanEngine | None = None,
) -> dict[str, Any]:
    suffix = Path(filename or "template.mp4").suffix.lower()
    if suffix not in {".mp4", ".webm", ".mov"}:
        raise ChanjingApiError("模板视频格式不支持，仅支持 mp4/webm/mov")
    job_id = _job_id("cj_train")
    _init_job_runtime(job_id)
    local_path = _job_dir(job_id) / "input" / f"template{suffix}"
    local_path.write_bytes(content)
    payload = {
        "local_video_path": str(local_path),
        "name": name,
        "train_type": train_type,
        "resolution_rate": resolution_rate,
        "language": language,
        "error_skip": error_skip,
    }
    _write_json(_job_dir(job_id) / "input" / "request.json", payload)
    job = _job_template(job_id)
    job["job_type"] = "training"
    _save_job(job)
    try:
        return _run_training_bootstrap(job, payload, engine or chanjing_engine)
    except Exception as exc:
        return _set_error(job, exc, status="training_failed")


def get_chanjing_training_job_detail(job_id: str, *, auto_poll: bool = True, engine: ChanjingDigitalHumanEngine | None = None) -> dict[str, Any]:
    job = poll_chanjing_training_poc_job(job_id, engine=engine) if auto_poll else get_chanjing_training_poc_job(job_id)
    db_row = _safe_db_call(get_digital_human_job, job_id)
    return {
        **job,
        "db": db_row,
    }


def list_chanjing_persons(*, source: str = "db", page: int = 1, page_size: int = 20, engine: ChanjingDigitalHumanEngine | None = None) -> dict[str, Any]:
    if source == "api":
        runtime_engine = engine or chanjing_engine
        runtime_engine.ensure_access_token()
        response = runtime_engine.client.list_customised_person(page=page, page_size=page_size)
        items = _extract_list_items(response.get("data"))
        for item in items:
            try:
                remote_status = int(item.get("status") or 0)
            except (TypeError, ValueError):
                remote_status = 0
            _safe_db_call(
                upsert_digital_human_person,
                {
                    "engine": "chanjing",
                    "person_id": str(item.get("id") or item.get("person_id") or ""),
                    "name": str(item.get("name") or ""),
                    "status": "ready" if remote_status in {1, 2} else "training",
                    "audio_man_id": str(item.get("audio_man_id") or ""),
                    "pic_url": str(item.get("pic_url") or ""),
                    "preview_url": str(item.get("preview_url") or ""),
                    "width": int(item.get("width") or 0),
                    "height": int(item.get("height") or 0),
                    "support_4k": bool(item.get("support_4k", False)),
                    "train_type": str(item.get("train_type") or "both"),
                    "source": "api",
                    "raw_response_json": item,
                },
            )
        db_result = _safe_db_call(list_digital_human_persons, engine="chanjing", page=page, page_size=page_size)
        normalized_items = []
        for item in items:
            try:
                remote_status = int(item.get("status") or 0)
            except (TypeError, ValueError):
                remote_status = 0
            normalized_items.append(
                {
                    "engine": "chanjing",
                    "person_id": str(item.get("id") or item.get("person_id") or ""),
                    "name": str(item.get("name") or ""),
                    "status": "ready" if remote_status in {1, 2} else "training",
                    "audio_man_id": str(item.get("audio_man_id") or ""),
                    "pic_url": str(item.get("pic_url") or ""),
                    "preview_url": str(item.get("preview_url") or ""),
                    "width": int(item.get("width") or 0),
                    "height": int(item.get("height") or 0),
                    "support_4k": bool(item.get("support_4k", False)),
                    "train_type": str(item.get("train_type") or "both"),
                    "source": "api",
                }
            )
        return {
            "source": "api",
            "remote": response,
            "items": (db_result or {}).get("items", []) or normalized_items,
            "page": page,
            "page_size": page_size,
            "total": (db_result or {}).get("total", len(items)),
        }
    db_result = _safe_db_call(list_digital_human_persons, engine="chanjing", page=page, page_size=page_size) or {}
    return {
        "source": "db",
        "items": db_result.get("items", []),
        "page": db_result.get("page", page),
        "page_size": db_result.get("page_size", page_size),
        "total": db_result.get("total", 0),
    }


def get_chanjing_video_job_detail(job_id: str, *, auto_poll: bool = True, engine: ChanjingDigitalHumanEngine | None = None) -> dict[str, Any]:
    job = poll_chanjing_video_poc_job(job_id, engine=engine) if auto_poll else get_chanjing_video_poc_job(job_id)
    db_row = _safe_db_call(get_digital_human_job, job_id)
    return {
        **job,
        "db": db_row,
    }


def list_chanjing_job_records(
    *,
    job_type: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    payload = _safe_db_call(
        list_digital_human_jobs,
        engine="chanjing",
        job_type=job_type,
        status=status,
        page=page,
        page_size=page_size,
    ) or {
        "page": page,
        "page_size": page_size,
        "total": 0,
        "items": [],
    }
    enriched_items = []
    for item in payload.get("items", []):
        runtime_job = _safe_read_runtime_job(str(item.get("raw_job_json_path") or ""))
        enriched_items.append(
            {
                **item,
                "preview_url": str(runtime_job.get("preview_url") or ""),
                "duration": runtime_job.get("duration") or 0,
                "person_width": runtime_job.get("person_width") or runtime_job.get("screen_width") or 0,
                "person_height": runtime_job.get("person_height") or runtime_job.get("screen_height") or 0,
            }
        )
    return {
        **payload,
        "items": enriched_items,
    }
