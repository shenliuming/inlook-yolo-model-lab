from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = APP_DIR.parent
ROOT_DIR = BACKEND_DIR.parent.parent


def _load_local_env_files() -> None:
    for env_path in (BACKEND_DIR / ".env.local", BACKEND_DIR / ".env"):
        if not env_path.exists() or not env_path.is_file():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not key or key in os.environ:
                continue
            value = value.strip().strip("'\"")
            os.environ[key] = value


_load_local_env_files()


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


# Deprecated: MOSS-TTS is no longer part of the INLOOK Studio TTS main flow.
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


def get_tts_engine() -> str:
    return os.getenv("TTS_ENGINE", "cosyvoice").strip().lower() or "cosyvoice"


def get_cosyvoice_model_dir() -> Path:
    configured = os.getenv("COSYVOICE_MODEL_DIR", "pretrained_models/CosyVoice2-0.5B").strip()
    path = Path(configured or "pretrained_models/CosyVoice2-0.5B").expanduser()
    if path.is_absolute():
        return path.resolve()
    return (ROOT_DIR / path).resolve()


def get_cosyvoice_device() -> str:
    return os.getenv("COSYVOICE_DEVICE", "auto").strip().lower() or "auto"


def get_cosyvoice_sample_rate() -> int:
    raw = os.getenv("COSYVOICE_SAMPLE_RATE", "24000").strip() or "24000"
    try:
        return max(8000, min(48000, int(raw)))
    except ValueError:
        return 24000


def get_cosyvoice_source_dir() -> Path | None:
    configured = os.getenv("COSYVOICE_SOURCE_DIR", "").strip()
    if not configured:
        return None
    return Path(configured).expanduser().resolve()


def get_cosyvoice_matcha_dir() -> Path | None:
    configured = os.getenv("COSYVOICE_MATCHA_DIR", "").strip()
    if not configured:
        source_dir = get_cosyvoice_source_dir()
        if source_dir:
            configured = str(source_dir / "third_party" / "Matcha-TTS")
    if not configured:
        return None
    return Path(configured).expanduser().resolve()


def get_content_lab_runtime_relative_dir() -> Path:
    configured = os.getenv("CONTENT_LAB_RUNTIME_DIR", "runtime/content_lab").strip() or "runtime/content_lab"
    return Path(configured)


def get_chanjing_app_id() -> str:
    return os.getenv("CHANJING_APP_ID", "").strip()


def get_chanjing_secret_key() -> str:
    return os.getenv("CHANJING_SECRET_KEY", "").strip()


def get_chanjing_api_base_url() -> str:
    return os.getenv("CHANJING_API_BASE_URL", "https://open-api.chanjing.cc").strip() or "https://open-api.chanjing.cc"


def get_chanjing_api_base_path() -> str:
    return os.getenv("CHANJING_API_BASE_PATH", "/open/v1").strip() or "/open/v1"


def get_chanjing_access_token_header() -> str:
    return os.getenv("CHANJING_ACCESS_TOKEN_HEADER", "access_token").strip() or "access_token"


def get_chanjing_open_api_base_url() -> str:
    return os.getenv("CHANJING_OPEN_API_BASE_URL", "https://open-api.chanjing.cc").strip() or "https://open-api.chanjing.cc"


def get_chanjing_default_model() -> int:
    raw = os.getenv("CHANJING_DEFAULT_MODEL", "0").strip() or "0"
    try:
        return int(raw)
    except ValueError:
        return 0


def get_chanjing_default_screen_width() -> int:
    raw = os.getenv("CHANJING_DEFAULT_SCREEN_WIDTH", "1080").strip() or "1080"
    try:
        return max(1, int(raw))
    except ValueError:
        return 1080


def get_chanjing_default_screen_height() -> int:
    raw = os.getenv("CHANJING_DEFAULT_SCREEN_HEIGHT", "1920").strip() or "1920"
    try:
        return max(1, int(raw))
    except ValueError:
        return 1920


def get_chanjing_token_expire_margin_seconds() -> int:
    raw = os.getenv("CHANJING_TOKEN_EXPIRE_MARGIN_SECONDS", "300").strip() or "300"
    try:
        return max(0, int(raw))
    except ValueError:
        return 300


def get_chanjing_audio_upload_services() -> list[str]:
    raw = os.getenv("CHANJING_AUDIO_UPLOAD_SERVICES", "audio,video").strip() or "audio,video"
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values or ["audio", "video"]


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


def get_llm_provider() -> str:
    return os.getenv("LLM_PROVIDER", "").strip().lower()


def get_llm_base_url() -> str:
    return os.getenv("LLM_BASE_URL", "").strip()


def get_llm_api_key() -> str:
    return os.getenv("LLM_API_KEY", "").strip()


def get_llm_model() -> str:
    return os.getenv("LLM_MODEL", "").strip()


def get_llm_timeout_seconds() -> int:
    raw = os.getenv("LLM_TIMEOUT_SECONDS", "60").strip() or "60"
    try:
        return max(5, min(300, int(raw)))
    except ValueError:
        return 60
