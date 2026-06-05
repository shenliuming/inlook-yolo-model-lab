from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, HTTPException, UploadFile

from app.config.paths import STUDIO_TTS_TRAINING_RUNTIME_DIR
from app.services.tts_service import create_tts_task, get_tts_task
from app.utils.file_utils import safe_filename

RUNTIME_ROOT = STUDIO_TTS_TRAINING_RUNTIME_DIR
RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
MAX_PROMPT_AUDIO_BYTES = 20 * 1024 * 1024
_task_lock = threading.Lock()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_training_id() -> str:
    return f"voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"


def training_dir(training_id: str) -> Path:
    return RUNTIME_ROOT / training_id


def training_json_path(training_id: str) -> Path:
    return training_dir(training_id) / "task.json"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_training(training_id: str, payload: dict[str, Any]) -> None:
    with _task_lock:
        payload["updated_at"] = now()
        write_json(training_json_path(training_id), payload)


def read_training(training_id: str) -> dict[str, Any]:
    path = training_json_path(training_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="音色训练任务不存在")
    return read_json(path)


def _save_upload(upload: UploadFile, destination: Path) -> Path:
    total = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as file:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_PROMPT_AUDIO_BYTES:
                raise HTTPException(status_code=413, detail="参考音频过大")
            file.write(chunk)
    return destination


def _process_training(training_id: str) -> None:
    task = read_training(training_id)
    try:
        task.update(
            {
                "status": "running",
                "stage": "音频预处理",
                "progress": 45,
                "message": "正在准备参考音频",
            }
        )
        write_training(training_id, task)
        prompt_audio = training_dir(training_id) / "inputs" / "reference.wav"
        if not prompt_audio.exists():
            raise RuntimeError("参考音频不存在")

        task.update(
            {
                "status": "success",
                "stage": "完成",
                "progress": 100,
                "message": "音色克隆资源已准备，可用于配音生成",
                "voice_id": training_id,
                "downloads": {
                    "reference": f"/api/v1/files/tts-trainings/{training_id}/reference.wav",
                    "metadata": f"/api/v1/files/tts-trainings/{training_id}/metadata.json",
                },
            }
        )
        write_json(
            training_dir(training_id) / "outputs" / "metadata.json",
            {
                "voiceId": training_id,
                "referenceAudio": str(prompt_audio),
                "createdAt": now(),
            },
        )
        write_training(training_id, task)
    except Exception as exc:
        task.update({"status": "failed", "stage": "失败", "message": str(exc)})
        write_training(training_id, task)


def create_tts_training(
    *,
    background_tasks: BackgroundTasks,
    reference_audio: UploadFile | None,
) -> dict[str, Any]:
    if reference_audio is None or not reference_audio.filename:
        raise HTTPException(status_code=400, detail="请上传参考音频")

    training_id = build_training_id()
    inputs_dir = training_dir(training_id) / "inputs"
    outputs_dir = training_dir(training_id) / "outputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(safe_filename(reference_audio.filename)).suffix or ".wav"
    source_path = _save_upload(reference_audio, inputs_dir / f"reference_source{suffix}")
    normalized_path = inputs_dir / "reference.wav"

    from app.services.tts_service import normalize_prompt_audio

    normalize_prompt_audio(source_path, normalized_path)

    task = {
        "task_id": training_id,
        "task_type": "tts.training",
        "voice_id": training_id,
        "status": "pending",
        "stage": "等待执行",
        "progress": 0,
        "message": "音色训练任务已创建",
        "created_at": now(),
        "updated_at": now(),
    }
    write_training(training_id, task)
    background_tasks.add_task(_process_training, training_id)
    return get_tts_training(training_id)


def get_tts_training(training_id: str) -> dict[str, Any]:
    task = read_training(training_id)
    downloads = task.get("downloads") or {}
    return {
        "trainingId": training_id,
        "voiceId": task.get("voice_id") or training_id,
        "status": task.get("status"),
        "stage": task.get("stage"),
        "progress": task.get("progress", 0),
        "message": task.get("message"),
        "files": downloads,
        "createdAt": task.get("created_at"),
        "updatedAt": task.get("updated_at"),
    }


def get_tts_training_file(training_id: str, filename: str) -> Path:
    file_map = {
        "reference.wav": training_dir(training_id) / "inputs" / "reference.wav",
        "metadata.json": training_dir(training_id) / "outputs" / "metadata.json",
    }
    path = file_map.get(filename)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="音色文件不存在")
    return path


def list_tts_voices() -> list[dict[str, str]]:
    return [
        {"voiceId": "preset-junhao", "name": "磁性男声", "mode": "preset"},
        {"voiceId": "preset-ava", "name": "温柔女声", "mode": "preset"},
        {"voiceId": "preset-teacher", "name": "知识老师", "mode": "preset"},
        {"voiceId": "preset-normal", "name": "普通人口播", "mode": "preset"},
    ]


def create_tts_synthesis(
    *,
    background_tasks: BackgroundTasks,
    text: str,
    language: str,
    training_id: str | None,
    voice_mode: str,
    execution_provider: str,
) -> dict[str, Any]:
    prompt_audio_path = ""
    resolved_voice_mode = voice_mode
    if training_id:
        training = read_training(training_id)
        if training.get("status") != "success":
            raise HTTPException(status_code=400, detail="音色训练尚未完成")
        prompt_audio_path = str(training_dir(training_id) / "inputs" / "reference.wav")
        resolved_voice_mode = "clone"
    elif voice_mode == "clone":
        raise HTTPException(status_code=400, detail="克隆模式需要先创建音色训练")

    task = create_tts_task(
        background_tasks=background_tasks,
        text=text,
        voice_mode=resolved_voice_mode,
        language=language,
        engine="moss-tts-nano",
        backend="onnx",
        execution_provider=execution_provider,
        prompt_audio=None,
        prompt_audio_path=prompt_audio_path,
        text_file=None,
    )
    return {
        "synthesisId": task["task_id"],
        "taskId": task["task_id"],
        "trainingId": training_id,
        "status": task.get("status"),
        "message": task.get("message"),
        "audioUrl": task.get("audio_url"),
        "downloads": task.get("downloads") or {},
        "createdAt": task.get("created_at"),
        "updatedAt": task.get("updated_at"),
    }


def get_tts_synthesis(synthesis_id: str) -> dict[str, Any]:
    task = get_tts_task(synthesis_id)
    return {
        "synthesisId": synthesis_id,
        "taskId": synthesis_id,
        "status": task.get("status"),
        "message": task.get("message"),
        "audioUrl": task.get("audio_url"),
        "downloads": task.get("downloads") or {},
        "createdAt": task.get("created_at"),
        "updatedAt": task.get("updated_at"),
    }
