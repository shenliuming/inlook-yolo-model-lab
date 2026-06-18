from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.config.paths import STUDIO_DIGITAL_HUMAN_TASKS_DIR
from app.services.material_intake_service import get_material_file
from app.services.transcriptions_service import get_transcription_file
from app.services.studio_tts_service import get_tts_training_file
from app.services.tts_service import get_tts_file

router = APIRouter(prefix="/api/v1/files", tags=["studio-files"])


@router.get("/materials/{material_id}/{filename}")
def download_material_file(material_id: str, filename: str):
    path = get_material_file(material_id, filename)
    return FileResponse(path, filename=path.name)


@router.get("/transcriptions/{transcription_id}/{filename}")
def download_transcription_file(transcription_id: str, filename: str):
    path = get_transcription_file(transcription_id, filename)
    return FileResponse(path, filename=path.name)


@router.get("/subtitles/{subtitle_id}/{filename}")
def download_subtitle_file(subtitle_id: str, filename: str):
    path = get_transcription_file(subtitle_id, filename)
    return FileResponse(path, filename=path.name)


@router.get("/tts-trainings/{training_id}/{filename}")
def download_training_file(training_id: str, filename: str):
    path = get_tts_training_file(training_id, filename)
    return FileResponse(path, filename=path.name)


@router.get("/tts-synthesis/{synthesis_id}/{filename}")
def download_synthesis_file(synthesis_id: str, filename: str):
    path = get_tts_file(synthesis_id, filename)
    return FileResponse(path, filename=path.name)


@router.get("/digital-human/{task_id}/{filename}")
def download_digital_human_file(task_id: str, filename: str):
    allowed = {
        "digital_human.mp4": "digital_human.mp4",
        "cover.jpg": "cover.jpg",
        "metadata.json": "metadata.json",
        "run.log": "run.log",
    }
    if filename not in allowed:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="文件不存在")
    path = (STUDIO_DIGITAL_HUMAN_TASKS_DIR / task_id / allowed[filename]).resolve()
    root = (STUDIO_DIGITAL_HUMAN_TASKS_DIR / task_id).resolve()
    if root not in path.parents or not path.exists() or not path.is_file():
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path, filename=path.name)
