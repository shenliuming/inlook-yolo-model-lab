from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse

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
