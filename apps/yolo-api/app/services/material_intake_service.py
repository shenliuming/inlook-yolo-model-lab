from __future__ import annotations

import json
import shutil
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import BackgroundTasks, HTTPException, UploadFile

from app.config.paths import BACKEND_DIR
from app.services.material_intake.engines.base import DownloadResult
from app.services.material_intake.engines.local_engine import LocalEngine
from app.services.material_intake.engines.lux_engine import LuxEngine
from app.services.material_intake.engines.ytdlp_engine import YtDlpEngine
from app.services.material_intake.engines.youget_engine import YouGetEngine
from app.services.material_intake.extract_metadata import ffprobe_metadata
from app.services.material_intake.normalize_video import normalize_to_mp4
from app.services.material_intake.platform_detector import detect_platform_from_url, extract_first_url

RUNTIME_ROOT = BACKEND_DIR / "runtime" / "content_workflow" / "material_intake" / "tasks"
RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_MB = 500
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

_task_lock = threading.Lock()

DEFAULT_CONFIG = {
    "engines": {"order": ["yt-dlp", "you-get", "lux"]},
    "platform_rules": {
        "bilibili": {"engines": ["yt-dlp", "you-get", "lux"]},
        "douyin": {"engines": ["yt-dlp", "lux"]},
        "wechat_channels": {"engines": [], "fallback": "manual_import"},
        "youtube": {"engines": ["yt-dlp"]},
        "unknown": {"engines": ["yt-dlp", "you-get", "lux"]},
    },
    "download": {
        "max_duration_seconds": 600,
        "max_file_size_mb": 500,
    },
    "normalize": {
        "video_codec": "libx264",
        "audio_codec": "aac",
        "crf": 20,
        "preset": "veryfast",
    },
}

ENGINE_MAP = {
    "local": LocalEngine(),
    "yt-dlp": YtDlpEngine(),
    "you-get": YouGetEngine(),
    "lux": LuxEngine(),
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_task_id() -> str:
    return f"mt_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"


def task_dir(task_id: str) -> Path:
    return RUNTIME_ROOT / task_id


def task_inputs_dir(task_id: str) -> Path:
    return task_dir(task_id) / "inputs"


def task_outputs_dir(task_id: str) -> Path:
    return task_dir(task_id) / "outputs"


def task_json_path(task_id: str) -> Path:
    return task_dir(task_id) / "task.json"


def run_log_path(task_id: str) -> Path:
    return task_dir(task_id) / "run.log"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_task(task_id: str) -> dict[str, Any]:
    path = task_json_path(task_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="任务不存在")
    return read_json(path)


def write_task(task_id: str, payload: dict[str, Any]) -> None:
    with _task_lock:
        payload["updated_at"] = now()
        write_json(task_json_path(task_id), payload)


def append_log(task_id: str, text: str) -> None:
    log_path = run_log_path(task_id)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8", errors="ignore") as file:
        file.write(text)
        if not text.endswith("\n"):
            file.write("\n")


def status_download_url(task_id: str, filename: str) -> str:
    return f"/api/v1/content-lab/materials/tasks/{task_id}/files/{filename}"


def allowed_download_files(task_id: str) -> dict[str, Path]:
    return {
        "input.mp4": task_outputs_dir(task_id) / "input.mp4",
        "metadata.json": task_outputs_dir(task_id) / "metadata.json",
        "status.json": task_outputs_dir(task_id) / "status.json",
        "run.log": run_log_path(task_id),
    }


def choose_engines(platform: str, requested_engine: str) -> list[str]:
    if requested_engine and requested_engine != "auto":
        return [requested_engine]

    rule = (DEFAULT_CONFIG.get("platform_rules") or {}).get(platform)
    if rule and isinstance(rule, dict):
        return list(rule.get("engines") or [])

    return list((DEFAULT_CONFIG.get("engines") or {}).get("order") or ["yt-dlp", "you-get", "lux"])


def manual_status(platform: str, tried: list[str], reason: str) -> dict[str, Any]:
    if platform == "wechat_channels":
        next_action = "检测到微信视频号链接。当前版本不直接下载视频号，请手动保存本人或授权视频后再上传。"
    elif platform == "douyin":
        next_action = "抖音链接自动获取失败。请手动保存本人或授权视频后再上传。"
    else:
        next_action = "自动获取失败。请改用本地视频上传，或检查链接是否可公开访问。"

    return {
        "ok": False,
        "platform": platform,
        "tried_engines": tried,
        "stage": "download",
        "reason": reason,
        "next_action": next_action,
        "created_at": now(),
    }


def validate_file_limits(path: Path) -> None:
    max_mb = float(DEFAULT_CONFIG["download"].get("max_file_size_mb") or 500)
    size_mb = path.stat().st_size / 1024 / 1024
    if size_mb > max_mb:
        raise RuntimeError(f"File too large: {size_mb:.1f}MB > {max_mb:.1f}MB")


def save_uploaded_file(upload: UploadFile, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with destination.open("wb") as file:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail=f"文件过大，最大允许 {MAX_UPLOAD_MB}MB。")
            file.write(chunk)
    return destination


def normalize_output(task_id: str, raw_video: Path) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    output_dir = task_outputs_dir(task_id)
    output_path = output_dir / "input.mp4"
    normalize_to_mp4(
        raw_video,
        output_path,
        video_codec=DEFAULT_CONFIG["normalize"].get("video_codec", "libx264"),
        audio_codec=DEFAULT_CONFIG["normalize"].get("audio_codec", "aac"),
        crf=int(DEFAULT_CONFIG["normalize"].get("crf", 20)),
        preset=DEFAULT_CONFIG["normalize"].get("preset", "veryfast"),
    )
    probe = ffprobe_metadata(output_path)
    metadata = {
        "title": raw_video.stem,
        "duration": probe.get("duration", 0.0),
        "width": probe.get("width", 0),
        "height": probe.get("height", 0),
        "fps": probe.get("fps", 0),
        "output_path": str(output_path),
        "created_at": now(),
    }
    status_payload = {
        "ok": True,
        "stage": "done",
        "output_path": str(output_path),
        "metadata_path": str(output_dir / "metadata.json"),
        "next_action": "可以继续进行字幕识别或模型测试。",
        "created_at": now(),
    }
    write_json(output_dir / "metadata.json", metadata)
    write_json(output_dir / "status.json", status_payload)
    return output_path, metadata, status_payload


def process_source(source_type: str, source_value: str, engine_name: str, task_id: str) -> dict[str, Any]:
    tried: list[str] = []
    errors: list[dict[str, str]] = []

    if source_type == "upload":
        local_engine = ENGINE_MAP["local"]
        result = local_engine.download(source_value, task_inputs_dir(task_id) / "local", "local")
        if not result.ok:
            raise RuntimeError(result.error or "本地视频处理失败")
        raw_video = Path(result.output_path)
        output_path, metadata, status_payload = normalize_output(task_id, raw_video)
        metadata.update({
            "source_type": "local",
            "source_path": source_value,
            "engine": "local",
            "platform": "local",
        })
        write_json(task_outputs_dir(task_id) / "metadata.json", metadata)
        status_payload["engine"] = "local"
        status_payload["tried_engines"] = ["local"]
        write_json(task_outputs_dir(task_id) / "status.json", status_payload)
        return {
            "message": "本地视频导入成功。",
            "metadata": metadata,
            "status_payload": status_payload,
            "output_path": output_path,
        }

    if source_type == "text":
        first_url = extract_first_url(source_value)
        if not first_url:
            status_payload = manual_status("unknown", [], "no URL found in text")
            status_payload["next_action"] = "没有从分享文案中识别到链接，请手动粘贴 URL 或改用本地视频上传。"
            write_json(task_outputs_dir(task_id) / "status.json", status_payload)
            raise RuntimeError(status_payload["next_action"])
        source_value = first_url

    platform = detect_platform_from_url(source_value)
    if platform == "wechat_channels" and engine_name == "auto":
        status_payload = manual_status(platform, [], "wechat channels direct download is not supported")
        write_json(task_outputs_dir(task_id) / "status.json", status_payload)
        raise RuntimeError(status_payload["next_action"])

    engine_names = choose_engines(platform, engine_name)
    temp_dir_obj = tempfile.TemporaryDirectory(prefix="inlook_intake_")
    temp_root = Path(temp_dir_obj.name)

    try:
        result: DownloadResult | None = None
        for name in engine_names:
            engine = ENGINE_MAP.get(name)
            if engine is None:
                errors.append({"engine": name, "error": "engine not implemented"})
                continue

            tried.append(name)
            if not engine.can_handle(source_value, platform):
                errors.append({"engine": name, "error": "engine unavailable or cannot handle platform"})
                append_log(task_id, f"[skip] {name}: unavailable or cannot handle {platform}")
                continue

            engine_work_dir = temp_root / name.replace("-", "_")
            append_log(task_id, f"[try] engine={name} platform={platform}")
            attempt = engine.download(source_value, engine_work_dir, platform)
            if attempt.ok:
                result = attempt
                append_log(task_id, f"[ok] engine={name} downloaded: {attempt.output_path}")
                break

            errors.append({"engine": name, "error": attempt.error[-1200:]})
            append_log(task_id, f"[fail] engine={name}: {attempt.error[:200]}")

        if result is None or not result.ok:
            status_payload = manual_status(platform, tried, "all engines failed")
            status_payload["errors"] = errors
            write_json(task_outputs_dir(task_id) / "status.json", status_payload)
            raise RuntimeError(status_payload["next_action"])

        raw_video = Path(result.output_path)
        validate_file_limits(raw_video)
        output_path, metadata, status_payload = normalize_output(task_id, raw_video)
        metadata.update({
            "source_type": "url",
            "source_url": source_value,
            "title": result.title or metadata.get("title", ""),
            "platform": platform,
            "engine": result.engine,
            "duration": metadata.get("duration", result.duration or 0.0),
        })
        write_json(task_outputs_dir(task_id) / "metadata.json", metadata)
        status_payload.update({
            "platform": platform,
            "engine": result.engine,
            "tried_engines": tried,
        })
        write_json(task_outputs_dir(task_id) / "status.json", status_payload)
        return {
            "message": "素材导入成功，可以继续模型测试。",
            "metadata": metadata,
            "status_payload": status_payload,
            "output_path": output_path,
        }
    finally:
        temp_dir_obj.cleanup()


def run_material_task(task_id: str, source_type: str, source_value: str, engine_name: str) -> None:
    task = read_task(task_id)
    task["status"] = "running"
    task["message"] = "正在导入素材，请稍等。"
    task["started_at"] = now()
    write_task(task_id, task)
    append_log(task_id, f"[task] source_type={source_type} engine={engine_name}")

    try:
        result = process_source(source_type, source_value, engine_name, task_id)
        task = read_task(task_id)
        task["status"] = "success"
        task["message"] = result["message"]
        task["metadata"] = result["metadata"]
        task["status_payload"] = result["status_payload"]
        task["finished_at"] = now()
        write_task(task_id, task)
    except Exception as exc:
        append_log(task_id, f"[error] {exc}")
        task = read_task(task_id)
        task["status"] = "failed"
        task["message"] = str(exc)
        task["finished_at"] = now()
        write_task(task_id, task)


def create_material_task(
    *,
    background_tasks: BackgroundTasks,
    mode: Literal["text", "url", "upload"],
    text: str,
    url: str,
    engine: str,
    upload: UploadFile | None,
) -> dict[str, Any]:
    task_id = build_task_id()
    task_inputs_dir(task_id).mkdir(parents=True, exist_ok=True)
    task_outputs_dir(task_id).mkdir(parents=True, exist_ok=True)

    if mode == "upload":
        if upload is None:
            raise HTTPException(status_code=400, detail="请选择本地视频文件。")
        suffix = Path(upload.filename or "upload.mp4").suffix or ".mp4"
        upload_path = task_inputs_dir(task_id) / f"upload{suffix}"
        save_uploaded_file(upload, upload_path)
        source_value = str(upload_path)
    elif mode == "url":
        if not url.strip():
            raise HTTPException(status_code=400, detail="请输入视频链接。")
        source_value = url.strip()
    else:
        if not text.strip():
            raise HTTPException(status_code=400, detail="请输入分享文案。")
        source_value = text.strip()

    task = {
        "task_id": task_id,
        "status": "queued",
        "mode": mode,
        "engine": engine,
        "message": "任务已创建，等待处理。",
        "created_at": now(),
        "updated_at": now(),
        "downloads": {
            "input.mp4": status_download_url(task_id, "input.mp4"),
            "metadata.json": status_download_url(task_id, "metadata.json"),
            "status.json": status_download_url(task_id, "status.json"),
            "run.log": status_download_url(task_id, "run.log"),
        },
    }
    write_task(task_id, task)
    background_tasks.add_task(run_material_task, task_id, mode, source_value, engine)
    return task


def get_material_task(task_id: str) -> dict[str, Any]:
    task = read_task(task_id)
    log_path = run_log_path(task_id)
    task["log_tail"] = log_path.read_text(encoding="utf-8", errors="ignore")[-6000:] if log_path.exists() else ""
    return task


def get_material_file(task_id: str, filename: str) -> Path:
    files = allowed_download_files(task_id)
    target = files.get(filename)
    if target is None:
        raise HTTPException(status_code=403, detail="文件不允许下载")
    if not target.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return target


def intake_env_status() -> dict[str, Any]:
    return {
        "yt_dlp": shutil.which("yt-dlp") is not None,
        "you_get": shutil.which("you-get") is not None,
        "lux": shutil.which("lux") is not None,
    }
