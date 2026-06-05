from __future__ import annotations

from fastapi import APIRouter

from app.common.result import success
from app.services.transcriptions_service import get_subtitle_bundle

router = APIRouter(prefix="/api/v1", tags=["studio-subtitles"])


@router.get("/subtitles/{subtitle_id}")
def read_subtitle_bundle(subtitle_id: str):
    return success(get_subtitle_bundle(subtitle_id))
