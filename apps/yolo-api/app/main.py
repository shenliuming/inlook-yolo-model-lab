from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.common.exceptions import register_exception_handlers
from app.common.logging import setup_logging
from app.config.cors import build_cors_config
from app.config.paths import OUTPUTS_DIR, REPORTS_DIR, ensure_runtime_directories
from app.config.settings import get_yolo_config_dir
from app.controllers.ai_controller import router as ai_router
from app.controllers.content_lab_controller import router as content_lab_router
from app.controllers.browser_auth_controller import router as browser_auth_router
from app.controllers.file_controller import router as file_router
from app.controllers.health_controller import router as health_router
from app.controllers.material_controller import router as material_router
from app.controllers.studio_tts_controller import router as studio_tts_router
from app.controllers.subtitle_controller import router as subtitle_router
from app.controllers.task_controller import router as task_router
from app.controllers.tts_controller import router as tts_router
from app.controllers.transcription_controller import router as transcription_router
from app.controllers.vision_controller import router as vision_router

setup_logging()
get_yolo_config_dir()
ensure_runtime_directories()

app = FastAPI(title="INLOOK AI 工作台 Backend")
app.add_middleware(CORSMiddleware, **build_cors_config())
register_exception_handlers(app)

app.mount("/outputs", StaticFiles(directory=OUTPUTS_DIR), name="outputs")
app.mount("/reports", StaticFiles(directory=REPORTS_DIR), name="reports")

app.include_router(health_router)
app.include_router(vision_router)
app.include_router(content_lab_router)
app.include_router(ai_router)
app.include_router(browser_auth_router)
app.include_router(tts_router)
app.include_router(material_router)
app.include_router(transcription_router)
app.include_router(subtitle_router)
app.include_router(studio_tts_router)
app.include_router(task_router)
app.include_router(file_router)
