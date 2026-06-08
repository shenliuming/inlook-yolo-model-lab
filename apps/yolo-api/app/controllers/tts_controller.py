from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, File, Form, Request, UploadFile
from fastapi.responses import FileResponse

from app.clients.yolo_client import enforce_rate_limit
from app.common.result import success
from app.services.tts_service import create_tts_task, get_tts_file, get_tts_health, get_tts_task

router = APIRouter(tags=["tts"])


@router.get("/api/v1/content-lab/tts/health")
def tts_health(request: Request):
    enforce_rate_limit(request, "health")
    return success(get_tts_health())


@router.post("/api/v1/content-lab/tts/tasks")
async def create_tts(
    request: Request,
    background_tasks: BackgroundTasks,
    text: str = Form(default=""),
    voiceMode: str = Form(default="clone"),
    language: str = Form(default="zh"),
    engine: str = Form(default="cosyvoice"),
    backend: str = Form(default="onnx"),
    executionProvider: str = Form(default="cpu"),
    promptAudio: UploadFile | None = File(default=None),
    promptAudioPath: str = Form(default=""),
    textFile: UploadFile | None = File(default=None),
):
    enforce_rate_limit(request, "realtime")
    return success(
        create_tts_task(
            background_tasks=background_tasks,
            text=text,
            voice_mode=voiceMode,
            language=language,
            engine=engine,
            backend=backend,
            execution_provider=executionProvider,
            prompt_audio=promptAudio,
            prompt_audio_path=promptAudioPath,
            text_file=textFile,
        )
    )


@router.get("/api/v1/content-lab/tts/tasks/{task_id}")
def read_tts_task(request: Request, task_id: str):
    enforce_rate_limit(request, "models")
    return success(get_tts_task(task_id))


@router.get("/api/v1/content-lab/tts/tasks/{task_id}/files/{filename}")
def get_tts_task_file(request: Request, task_id: str, filename: str):
    enforce_rate_limit(request, "models")
    path = get_tts_file(task_id, filename)
    return FileResponse(path, filename=path.name)
