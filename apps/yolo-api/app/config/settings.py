from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = APP_DIR.parent
ROOT_DIR = BACKEND_DIR.parent.parent

def get_api_key() -> str:
    return os.getenv("INLOOK_API_KEY", "").strip()


def get_yolo_config_dir() -> Path:
    config_dir = Path(os.getenv("YOLO_CONFIG_DIR", "/tmp/Ultralytics"))
    config_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("YOLO_CONFIG_DIR", str(config_dir))
    return config_dir


def get_allowed_origins() -> list[str]:
    return [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5180",
        "http://localhost:5180",
    ]


def get_moss_tts_repo_dir() -> Path:
    configured = os.getenv("MOSS_TTS_REPO_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (ROOT_DIR / "third_party" / "MOSS-TTS-Nano").resolve()


def get_moss_tts_model_dir() -> Path:
    configured = os.getenv("MOSS_TTS_MODEL_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return get_moss_tts_repo_dir() / "models"


def get_moss_tts_backend() -> str:
    return os.getenv("MOSS_TTS_BACKEND", "onnx").strip().lower() or "onnx"


def get_moss_tts_execution_provider() -> str:
    provider = os.getenv("MOSS_TTS_EXECUTION_PROVIDER", "cpu").strip().lower() or "cpu"
    return "cuda" if provider == "cuda" else "cpu"


def get_moss_tts_output_filename() -> str:
    return os.getenv("MOSS_TTS_OUTPUT_FILENAME", "voice.wav").strip() or "voice.wav"


def get_content_lab_runtime_relative_dir() -> Path:
    configured = os.getenv("CONTENT_LAB_RUNTIME_DIR", "runtime/content_lab").strip() or "runtime/content_lab"
    return Path(configured)


def get_asr_provider() -> str:
    return os.getenv("ASR_PROVIDER", "faster_whisper").strip().lower() or "faster_whisper"


def get_whisper_model() -> str:
    return os.getenv("WHISPER_MODEL", "medium").strip() or "medium"


def get_whisper_device() -> str:
    return os.getenv("WHISPER_DEVICE", "cpu").strip().lower() or "cpu"


def get_whisper_compute_type() -> str:
    return os.getenv("WHISPER_COMPUTE_TYPE", "int8").strip().lower() or "int8"


def get_whisper_language() -> str:
    return os.getenv("WHISPER_LANGUAGE", "zh").strip().lower() or "zh"


def get_whisper_beam_size() -> int:
    raw = os.getenv("WHISPER_BEAM_SIZE", "5").strip() or "5"
    try:
        return max(1, min(10, int(raw)))
    except ValueError:
        return 5


def get_whisper_vad_filter() -> bool:
    return os.getenv("WHISPER_VAD_FILTER", "true").strip().lower() not in {"0", "false", "no", "off"}


def get_copy_pilot_enabled() -> bool:
    return os.getenv("COPY_PILOT_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}


def get_copy_pilot_api_url() -> str:
    return os.getenv("COPY_PILOT_API_URL", "https://copypilot.cc/api/extract").strip() or "https://copypilot.cc/api/extract"


def get_copy_pilot_timeout() -> int:
    raw = os.getenv("COPY_PILOT_TIMEOUT", "30").strip() or "30"
    try:
        return max(5, min(120, int(raw)))
    except ValueError:
        return 30
