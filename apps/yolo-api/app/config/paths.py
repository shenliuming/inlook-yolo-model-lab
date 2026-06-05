from __future__ import annotations

from pathlib import Path

from app.config.settings import get_content_lab_runtime_relative_dir

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ROOT_DIR = BACKEND_DIR.parent.parent

MODELS_DIR = BACKEND_DIR / "models"
UPLOADS_DIR = BACKEND_DIR / "uploads"
OUTPUTS_DIR = BACKEND_DIR / "outputs"
REPORTS_DIR = BACKEND_DIR / "reports"
RUNTIME_DIR = BACKEND_DIR / "runtime"
CONTENT_LAB_RUNTIME_DIR = BACKEND_DIR / get_content_lab_runtime_relative_dir()
CONTENT_LAB_TTS_RUNTIME_DIR = CONTENT_LAB_RUNTIME_DIR / "tts" / "tasks"
CONTENT_LAB_MATERIAL_CACHE_DIR = CONTENT_LAB_RUNTIME_DIR / "material_cache"
BROWSER_PROFILES_DIR = RUNTIME_DIR / "browser_profiles"
STUDIO_RUNTIME_DIR = RUNTIME_DIR / "studio_alpha"
STUDIO_TRANSCRIPTION_RUNTIME_DIR = STUDIO_RUNTIME_DIR / "transcriptions" / "tasks"
STUDIO_TTS_TRAINING_RUNTIME_DIR = STUDIO_RUNTIME_DIR / "tts" / "trainings"


def ensure_runtime_directories() -> None:
    for directory in (
        MODELS_DIR,
        UPLOADS_DIR,
        OUTPUTS_DIR,
        REPORTS_DIR,
        RUNTIME_DIR,
        CONTENT_LAB_RUNTIME_DIR,
        CONTENT_LAB_TTS_RUNTIME_DIR,
        CONTENT_LAB_MATERIAL_CACHE_DIR,
        BROWSER_PROFILES_DIR,
        BROWSER_PROFILES_DIR / "douyin",
        BROWSER_PROFILES_DIR / "bilibili",
        STUDIO_RUNTIME_DIR,
        STUDIO_TRANSCRIPTION_RUNTIME_DIR,
        STUDIO_TTS_TRAINING_RUNTIME_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
