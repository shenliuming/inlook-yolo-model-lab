from __future__ import annotations

from fastapi import APIRouter

from app.common.result import success
from app.dto.digital_human_dto import DigitalHumanGenerateRequestDTO
from app.services.digital_human_service import create_digital_human_video

router = APIRouter(prefix="/api/v1/digital-human", tags=["digital-human"])


@router.post("/generate")
def generate_digital_human_video(request: DigitalHumanGenerateRequestDTO):
    return success(create_digital_human_video(request))
