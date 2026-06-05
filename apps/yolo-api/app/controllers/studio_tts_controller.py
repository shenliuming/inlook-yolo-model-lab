from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, File, UploadFile

from app.common.result import success
from app.dto.studio_dto import TtsSynthesisCreateRequestDTO
from app.services.studio_tts_service import (
    create_tts_synthesis,
    create_tts_training,
    get_tts_synthesis,
    get_tts_training,
    list_tts_voices,
)

router = APIRouter(prefix="/api/v1/tts", tags=["studio-tts"])


@router.get("/voices")
def read_tts_voices():
    return success(list_tts_voices())


@router.post("/trainings")
async def create_training(background_tasks: BackgroundTasks, referenceAudio: UploadFile = File(...)):
    return success(create_tts_training(background_tasks=background_tasks, reference_audio=referenceAudio))


@router.get("/trainings/{training_id}")
def read_training(training_id: str):
    return success(get_tts_training(training_id))


@router.post("/synthesis")
async def create_synthesis(request: TtsSynthesisCreateRequestDTO, background_tasks: BackgroundTasks):
    return success(
        create_tts_synthesis(
            background_tasks=background_tasks,
            text=request.text,
            language=request.language,
            training_id=request.trainingId,
            voice_mode=request.voiceMode,
            execution_provider=request.executionProvider,
        )
    )


@router.get("/synthesis/{synthesis_id}")
def read_synthesis(synthesis_id: str):
    return success(get_tts_synthesis(synthesis_id))
