from __future__ import annotations

import json
import logging
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, HTTPException, UploadFile

from app.clients.moss_tts_client import moss_tts_client
from app.config.paths import CONTENT_LAB_TTS_RUNTIME_DIR
from app.config.settings import (
    get_tts_engine,
    get_moss_tts_execution_provider,
    get_moss_tts_output_filename,
)
from app.services.tts_engines.cosyvoice_engine import cosyvoice_engine
from app.utils.file_utils import safe_filename
from app.utils.subprocess_utils import run_command

RUNTIME_ROOT = CONTENT_LAB_TTS_RUNTIME_DIR
RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)

MAX_PROMPT_AUDIO_MB = 20
MAX_PROMPT_AUDIO_BYTES = MAX_PROMPT_AUDIO_MB * 1024 * 1024
MAX_TEXT_FILE_BYTES = 512 * 1024
_task_lock = threading.Lock()
logger = logging.getLogger("inlook.yolo_api")

DEFAULT_VOICE_BY_LANGUAGE = {
    "zh": "Junhao",
    "en": "Ava",
    "jp": "Yuriko",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_task_id() -> str:
    return f"tts_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"


def task_dir(task_id: str) -> Path:
    return RUNTIME_ROOT / task_id


def task_inputs_dir(task_id: str) -> Path:
    return task_dir(task_id) / "inputs"


def task_outputs_dir(task_id: str) -> Path:
    return task_dir(task_id) / "outputs"


def task_json_path(task_id: str) -> Path:
    return task_dir(task_id) / "task.json"


def task_status_path(task_id: str) -> Path:
    return task_outputs_dir(task_id) / "status.json"


def task_metadata_path(task_id: str) -> Path:
    return task_outputs_dir(task_id) / "metadata.json"


def run_log_path(task_id: str) -> Path:
    return task_dir(task_id) / "run.log"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def append_log(task_id: str, text: str) -> None:
    path = run_log_path(task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", errors="ignore") as file:
        file.write(text)
        if not text.endswith("\n"):
            file.write("\n")


def read_log_tail(task_id: str, max_chars: int = 8000) -> str:
    path = run_log_path(task_id)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")[-max_chars:]


def write_task(task_id: str, payload: dict[str, Any]) -> None:
    with _task_lock:
        payload["updated_at"] = now()
        write_json(task_json_path(task_id), payload)


def read_task(task_id: str) -> dict[str, Any]:
    path = task_json_path(task_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="TTS 任务不存在")
    payload = read_json(path)
    payload["log_tail"] = read_log_tail(task_id)
    return payload


def download_url(task_id: str, filename: str) -> str:
    return f"/api/v1/content-lab/tts/tasks/{task_id}/files/{filename}"


def allowed_download_files(task_id: str) -> dict[str, Path]:
    outputs = task_outputs_dir(task_id)
    return {
        "voice.wav": outputs / "voice.wav",
        "final.wav": outputs / "final.wav",
        "metadata.json": outputs / "metadata.json",
        "status.json": outputs / "status.json",
        "tts_request.json": outputs / "tts_request.json",
        "run.log": run_log_path(task_id),
    }


def build_downloads(task_id: str) -> dict[str, str]:
    return {
        filename: download_url(task_id, filename)
        for filename, path in allowed_download_files(task_id).items()
        if path.exists()
    }


def create_status_payload(task_id: str, payload: dict[str, Any]) -> None:
    write_json(task_status_path(task_id), payload)


def get_tts_health() -> dict[str, Any]:
    runtime_root = RUNTIME_ROOT
    payload = moss_tts_client.health()
    payload["configured_engine"] = get_tts_engine()
    payload["cosyvoice"] = cosyvoice_engine.health()
    payload["runtime_root"] = str(runtime_root)
    payload["runtime_root_exists"] = runtime_root.exists()
    return payload


def choose_builtin_voice(language: str) -> str:
    normalized = (language or "zh").strip().lower()
    return DEFAULT_VOICE_BY_LANGUAGE.get(normalized, "Junhao")


def save_upload(upload: UploadFile, destination: Path, *, max_bytes: int) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with destination.open("wb") as file:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise HTTPException(status_code=413, detail="上传文件过大")
            file.write(chunk)
    return destination


def save_text_file(upload: UploadFile, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    content = bytearray()
    while True:
        chunk = upload.file.read(1024 * 64)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_TEXT_FILE_BYTES:
            raise HTTPException(status_code=413, detail="文本文件过大")
        content.extend(chunk)
    destination.write_text(content.decode("utf-8", errors="ignore"), encoding="utf-8")
    return destination


def normalize_prompt_audio(source_path: Path, destination_path: Path) -> Path:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_path),
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(destination_path),
    ]
    result = run_command(command)
    if result.returncode != 0 or not destination_path.exists():
        raise RuntimeError(f"参考音频转 WAV 失败：{result.stdout.strip()}")
    return destination_path


def resolve_text_content(text: str, text_file_path: Path | None) -> str:
    inline_text = (text or "").strip()
    if inline_text:
        return inline_text
    if text_file_path and text_file_path.exists():
        file_text = text_file_path.read_text(encoding="utf-8", errors="ignore").strip()
        if file_text:
            return file_text
    raise HTTPException(status_code=400, detail="请提供要合成的文本内容")


def resolve_prompt_audio_path(task_id: str, uploaded_prompt_audio_path: Path | None, prompt_audio_path: str) -> Path | None:
    if uploaded_prompt_audio_path and uploaded_prompt_audio_path.exists():
        normalized_path = task_inputs_dir(task_id) / "prompt_audio.wav"
        return normalize_prompt_audio(uploaded_prompt_audio_path, normalized_path)

    path_text = (prompt_audio_path or "").strip()
    if not path_text:
        return None

    candidate = Path(path_text).expanduser()
    if not candidate.is_absolute():
        candidate = candidate.resolve()
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=400, detail="promptAudioPath 对应的文件不存在")

    normalized_path = task_inputs_dir(task_id) / "prompt_audio.wav"
    return normalize_prompt_audio(candidate, normalized_path)


def create_task_payload(
    *,
    task_id: str,
    text_preview: str,
    voice_mode: str,
    language: str,
    engine: str,
    backend: str,
    execution_provider: str,
    prompt_audio_name: str | None,
    builtin_voice: str | None,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "status": "queued",
        "message": "TTS 任务已创建",
        "created_at": now(),
        "updated_at": now(),
        "text_preview": text_preview[:120],
        "voice_mode": voice_mode,
        "language": language,
        "engine": engine,
        "backend": backend,
        "execution_provider": execution_provider,
        "builtin_voice": builtin_voice,
        "prompt_audio_name": prompt_audio_name,
        "downloads": {},
    }


def process_tts_task(
    task_id: str,
    *,
    text_path: Path,
    voice_mode: str,
    language: str,
    backend: str,
    execution_provider: str,
    prompt_audio_path: Path | None,
    builtin_voice: str | None,
) -> None:
    task = read_json(task_json_path(task_id))
    output_path = task_outputs_dir(task_id) / get_moss_tts_output_filename()
    final_output_path = task_outputs_dir(task_id) / "voice.wav"
    try:
        task.update({"status": "running", "message": "正在生成语音"})
        write_task(task_id, task)
        append_log(task_id, f"[INFO] engine=moss-tts-nano backend={backend} executionProvider={execution_provider}")

        voice = (builtin_voice or "").strip() or choose_builtin_voice(language)
        if voice_mode == "clone" and prompt_audio_path is None:
            raise RuntimeError("克隆模式需要上传参考音频，或填写 promptAudioPath")

        result = moss_tts_client.generate(
            text_path=text_path,
            output_path=output_path,
            prompt_audio_path=prompt_audio_path,
            execution_provider=execution_provider,
            voice=voice,
            model_dir=None,
            on_log=lambda line: append_log(task_id, line),
        )

        if not output_path.exists():
            raise RuntimeError("TTS 已执行，但未找到输出音频")

        if output_path != final_output_path:
            shutil.move(str(output_path), str(final_output_path))
        append_log(task_id, f"[INFO] output_path={final_output_path}")
        logger.info("studio tts synthesis output taskId=%s outputPath=%s", task_id, final_output_path)

        metadata = {
            "task_id": task_id,
            "engine": "moss-tts-nano",
            "backend": backend,
            "execution_provider": execution_provider,
            "language": language,
            "voice_mode": voice_mode,
            "voice": voice,
            "runner": result.get("runner"),
            "prompt_audio_used": str(prompt_audio_path) if prompt_audio_path else None,
            "text_path": str(text_path),
            "output_path": str(final_output_path),
            "created_at": now(),
        }
        write_json(task_metadata_path(task_id), metadata)
        create_status_payload(
            task_id,
            {
                "ok": True,
                "stage": "done",
                "message": "TTS 生成完成",
                "output_path": str(final_output_path),
                "created_at": now(),
            },
        )

        task.update(
            {
                "status": "success",
                "message": "TTS 生成完成",
                "downloads": build_downloads(task_id),
                "audio_url": download_url(task_id, "voice.wav"),
            }
        )
        append_log(task_id, "[DONE] TTS 生成完成")
    except Exception as exc:
        create_status_payload(
            task_id,
            {
                "ok": False,
                "stage": "failed",
                "message": str(exc),
                "created_at": now(),
            },
        )
        task.update(
            {
                "status": "failed",
                "message": f"TTS 生成失败：{exc}",
                "downloads": build_downloads(task_id),
            }
        )
        append_log(task_id, f"[ERROR] {exc}")
    finally:
        write_task(task_id, task)


def create_tts_task(
    *,
    background_tasks: BackgroundTasks,
    text: str,
    voice_mode: str,
    language: str,
    engine: str,
    backend: str,
    execution_provider: str,
    prompt_audio: UploadFile | None,
    prompt_audio_path: str,
    text_file: UploadFile | None,
    builtin_voice: str | None = None,
) -> dict[str, Any]:
    task_id = build_task_id()
    inputs = task_inputs_dir(task_id)
    outputs = task_outputs_dir(task_id)
    inputs.mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)

    text_file_path = None
    if text_file and text_file.filename:
        text_file_path = save_text_file(text_file, inputs / "text.txt")

    resolved_text = resolve_text_content(text, text_file_path)
    text_path = inputs / "text.txt"
    text_path.write_text(resolved_text, encoding="utf-8")

    uploaded_prompt_audio_path = None
    prompt_audio_name = None
    if prompt_audio and prompt_audio.filename:
        prompt_audio_name = safe_filename(prompt_audio.filename)
        uploaded_prompt_audio_path = save_upload(
            prompt_audio,
            inputs / f"prompt_audio_upload{Path(prompt_audio_name).suffix or '.wav'}",
            max_bytes=MAX_PROMPT_AUDIO_BYTES,
        )

    normalized_prompt_audio_path = resolve_prompt_audio_path(task_id, uploaded_prompt_audio_path, prompt_audio_path)
    if voice_mode != "clone":
        normalized_prompt_audio_path = None

    task = create_task_payload(
        task_id=task_id,
        text_preview=resolved_text,
        voice_mode=voice_mode,
        language=language,
        engine=engine,
        backend=backend,
        execution_provider=execution_provider,
        prompt_audio_name=prompt_audio_name or (Path(prompt_audio_path).name if prompt_audio_path else None),
        builtin_voice=builtin_voice,
    )
    write_task(task_id, task)
    create_status_payload(
        task_id,
        {
            "ok": True,
            "stage": "queued",
            "message": "任务已进入队列",
            "created_at": now(),
        },
    )
    append_log(task_id, "[INFO] TTS 任务已创建")

    background_tasks.add_task(
        process_tts_task,
        task_id,
        text_path=text_path,
        voice_mode=voice_mode,
        language=language,
        backend=backend or "onnx",
        execution_provider=execution_provider or get_moss_tts_execution_provider(),
        prompt_audio_path=normalized_prompt_audio_path,
        builtin_voice=builtin_voice,
    )
    return read_task(task_id)


def get_tts_task(task_id: str) -> dict[str, Any]:
    return read_task(task_id)


def get_tts_file(task_id: str, filename: str) -> Path:
    allowed = allowed_download_files(task_id)
    target = allowed.get(filename)
    if target is None or not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="TTS 文件不存在")
    return target
