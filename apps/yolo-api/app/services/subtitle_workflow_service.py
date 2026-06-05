from __future__ import annotations

import importlib.util
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, HTTPException, UploadFile

from app.config.paths import BACKEND_DIR
from app.services.subtitle_tool.burn_subtitles import burn_ass_video, check_ffmpeg_ass
from app.services.subtitle_tool.subtitle_pack import (
    burn_video,
    check_ffmpeg,
    extract_audio,
    transcribe,
    write_ass,
    write_srt,
    write_txt,
)
RUNTIME_ROOT = BACKEND_DIR / "runtime" / "content_workflow" / "subtitle_recognition" / "tasks"
RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)


MAX_VIDEO_UPLOAD_MB = 500
MAX_VIDEO_UPLOAD_BYTES = MAX_VIDEO_UPLOAD_MB * 1024 * 1024
_task_lock = threading.Lock()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_task_id() -> str:
    return f"st_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"


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


def append_log(task_id: str, text: str) -> None:
    log_path = run_log_path(task_id)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8", errors="ignore") as file:
        file.write(text)
        if not text.endswith("\n"):
            file.write("\n")


def read_log_tail(task_id: str, max_chars: int = 6000) -> str:
    log_path = run_log_path(task_id)
    if not log_path.exists():
        return ""
    text = log_path.read_text(encoding="utf-8", errors="ignore")
    return text[-max_chars:]


def write_task(task_id: str, payload: dict[str, Any]) -> None:
    with _task_lock:
        payload["updated_at"] = now()
        write_json(task_json_path(task_id), payload)


def read_task(task_id: str) -> dict[str, Any]:
    path = task_json_path(task_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="字幕任务不存在")
    payload = read_json(path)
    payload["log_tail"] = read_log_tail(task_id)
    return payload


def download_url(task_id: str, filename: str) -> str:
    return f"/api/v1/content-lab/subtitles/tasks/{task_id}/files/{filename}"


def allowed_download_files(task_id: str) -> dict[str, Path]:
    outputs = task_outputs_dir(task_id)
    return {
        "output_subtitled.mp4": outputs / "output_subtitled.mp4",
        "output_subtitled.srt": outputs / "output_subtitled.srt",
        "output_subtitled.ass": outputs / "output_subtitled.ass",
        "output_subtitled.txt": outputs / "output_subtitled.txt",
        "output_fixed.mp4": outputs / "output_fixed.mp4",
        "status.json": outputs / "status.json",
        "run.log": run_log_path(task_id),
    }


def build_downloads(task_id: str) -> dict[str, str]:
    return {
        filename: download_url(task_id, filename)
        for filename, path in allowed_download_files(task_id).items()
        if path.exists()
    }


def save_uploaded_file(upload: UploadFile, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with destination.open("wb") as file:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_VIDEO_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail=f"文件过大，最大允许 {MAX_VIDEO_UPLOAD_MB}MB。")
            file.write(chunk)
    return destination


def subtitle_env_status() -> dict[str, object]:
    status: dict[str, object] = {
        "subtitle_tool": True,
        "faster_whisper": importlib.util.find_spec("faster_whisper") is not None,
        "ffmpeg": "unknown",
    }
    try:
        status["ffmpeg"] = check_ffmpeg()
    except SystemExit as exc:
        status["ffmpeg"] = "missing"
        status["ffmpeg_error"] = str(exc)
    return status


def create_status_payload(task_id: str, payload: dict[str, Any]) -> None:
    write_json(task_outputs_dir(task_id) / "status.json", payload)


def process_subtitle_task(
    task_id: str,
    video_path: Path,
    audio_path: Path | None,
    model: str,
    language: str,
    device: str,
    compute_type: str,
    beam_size: int,
    width: int,
    height: int,
    font_size: int,
    margin_v: int,
    crf: int,
) -> None:
    task = read_json(task_json_path(task_id))
    try:
        append_log(task_id, "[INFO] 检查 ffmpeg 字幕滤镜")
        subtitle_filter_name = check_ffmpeg()

        outputs = task_outputs_dir(task_id)
        output_path = outputs / "output_subtitled.mp4"
        srt_path = outputs / "output_subtitled.srt"
        ass_path = outputs / "output_subtitled.ass"
        txt_path = outputs / "output_subtitled.txt"

        from tempfile import TemporaryDirectory

        with TemporaryDirectory(prefix="inlook_subtitle_workflow_") as temp_dir:
            wav_path = Path(temp_dir) / "asr.wav"
            asr_source = audio_path if audio_path else video_path

            append_log(task_id, "[INFO] 提取音频")
            extract_audio(asr_source, wav_path)

            append_log(task_id, f"[INFO] Whisper 识别：model={model}, device={device}, compute_type={compute_type}")
            segments = transcribe(
                wav_path,
                model_name=model,
                language=language,
                device=device,
                compute_type=compute_type,
                beam_size=beam_size,
                vad_filter=True,
            )
            if not segments:
                raise RuntimeError("没有识别到有效语音")

            append_log(task_id, f"[INFO] 写入字幕文件：{len(segments)} 段")
            write_srt(segments, srt_path)
            write_ass(segments, ass_path, width, height, font_size, margin_v)
            write_txt(segments, txt_path)

            append_log(task_id, "[INFO] 烧录字幕到视频")
            burn_video(
                video=video_path,
                audio=audio_path,
                ass_file=ass_path,
                output=output_path,
                width=width,
                height=height,
                crf=crf,
                keep_original_audio=True,
                subtitle_filter_name=subtitle_filter_name,
            )

        create_status_payload(task_id, {
            "ok": True,
            "stage": "done",
            "output_path": str(output_path),
            "created_at": now(),
        })
        task.update({
            "status": "success",
            "message": "字幕识别完成",
            "downloads": build_downloads(task_id),
        })
        append_log(task_id, "[DONE] 字幕识别完成")
    except SystemExit as exc:
        task.update({"status": "failed", "message": str(exc), "downloads": build_downloads(task_id)})
        create_status_payload(task_id, {"ok": False, "stage": "failed", "reason": str(exc), "created_at": now()})
        append_log(task_id, f"[ERROR] {exc}")
    except Exception as exc:
        task.update({"status": "failed", "message": f"处理失败：{exc}", "downloads": build_downloads(task_id)})
        create_status_payload(task_id, {"ok": False, "stage": "failed", "reason": str(exc), "created_at": now()})
        append_log(task_id, f"[ERROR] {exc}")
    finally:
        write_task(task_id, task)


def create_subtitle_task(
    background_tasks: BackgroundTasks,
    video: UploadFile,
    audio: UploadFile | None,
    model: str,
    language: str,
    device: str,
    compute_type: str,
    beam_size: int,
    width: int,
    height: int,
    font_size: int,
    margin_v: int,
    crf: int,
) -> dict[str, Any]:
    if not video.filename:
        raise HTTPException(status_code=400, detail="请上传视频文件")

    task_id = build_task_id()
    inputs = task_inputs_dir(task_id)
    outputs = task_outputs_dir(task_id)
    inputs.mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)

    video_suffix = Path(video.filename).suffix or ".mp4"
    video_path = save_uploaded_file(video, inputs / f"input{video_suffix}")

    audio_path = None
    if audio and audio.filename:
        audio_suffix = Path(audio.filename).suffix or ".m4a"
        audio_path = save_uploaded_file(audio, inputs / f"voice{audio_suffix}")

    task = {
        "task_id": task_id,
        "status": "queued",
        "message": "字幕任务已创建",
        "created_at": now(),
        "updated_at": now(),
        "video_name": video.filename,
        "audio_name": audio.filename if audio and audio.filename else None,
        "downloads": {},
    }
    write_task(task_id, task)
    append_log(task_id, "[INFO] 字幕任务已创建")

    background_tasks.add_task(
        process_subtitle_task,
        task_id,
        video_path,
        audio_path,
        model,
        language,
        device,
        compute_type,
        beam_size,
        width,
        height,
        font_size,
        margin_v,
        crf,
    )
    return read_task(task_id)


def reburn_subtitle_task(task_id: str, ass_upload: UploadFile | None, crf: int) -> dict[str, Any]:
    task = read_json(task_json_path(task_id))
    inputs = task_inputs_dir(task_id)
    outputs = task_outputs_dir(task_id)
    video_candidates = sorted(inputs.glob("input.*"))
    if not video_candidates:
        raise HTTPException(status_code=404, detail="未找到原始视频")

    source_ass = outputs / "output_subtitled.ass"
    if ass_upload and ass_upload.filename:
        source_ass = save_uploaded_file(ass_upload, outputs / "output_subtitled.ass")

    if not source_ass.exists():
        raise HTTPException(status_code=404, detail="未找到 ASS 字幕文件")

    output_path = outputs / "output_fixed.mp4"
    try:
        append_log(task_id, "[INFO] 重新烧录 ASS 字幕")
        check_ffmpeg_ass()
        burn_ass_video(
            video=video_candidates[0],
            ass_file=source_ass,
            output=output_path,
            crf=crf,
            keep_original_audio=True,
        )
        append_log(task_id, "[DONE] 重新导出完成")
        task.update({
            "status": "success",
            "message": "重新导出完成",
            "downloads": build_downloads(task_id),
        })
    except SystemExit as exc:
        append_log(task_id, f"[ERROR] {exc}")
        task.update({"status": "failed", "message": str(exc), "downloads": build_downloads(task_id)})
    except Exception as exc:
        append_log(task_id, f"[ERROR] {exc}")
        task.update({"status": "failed", "message": f"重新导出失败：{exc}", "downloads": build_downloads(task_id)})

    write_task(task_id, task)
    return read_task(task_id)


def get_subtitle_task(task_id: str) -> dict[str, Any]:
    return read_task(task_id)


def get_subtitle_file(task_id: str, filename: str) -> Path:
    files = allowed_download_files(task_id)
    path = files.get(filename)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return path
