from __future__ import annotations

from fastapi import APIRouter

from app.common.result import success
from app.dto.studio_dto import TranscriptionCreateRequestDTO
from app.services.transcriptions_service import create_transcription_task, get_transcription

router = APIRouter(prefix="/api/v1", tags=["studio-transcriptions"])


@router.post("/transcriptions")
async def create_transcription(request: TranscriptionCreateRequestDTO):
    return success(
        create_transcription_task(
            material_id=request.materialId,
            model=request.model,
            language=request.language,
            device=request.device,
            compute_type=request.computeType,
            beam_size=request.beamSize,
        )
    )


@router.get("/transcriptions/{transcription_id}")
def read_transcription(transcription_id: str):
    return success(get_transcription(transcription_id))
