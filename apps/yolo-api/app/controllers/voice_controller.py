from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse

from app.common.result import success
from app.dto.voice_dto import VoiceFromMaterialRequestDTO, VoicePreviewRequestDTO, VoiceUpdateRequestDTO
from app.services.voice_profile_service import (
    create_voice_preview,
    create_voice_profile,
    create_voice_profile_from_material,
    delete_voice_profile,
    get_voice_profile,
    get_voice_file,
    list_voice_profiles,
    update_voice_profile,
)

router = APIRouter(prefix="/api/v1/voices", tags=["voices"])


@router.get("")
def read_voices():
    return success(list_voice_profiles())


@router.get("/{voice_id}")
def read_voice(voice_id: str):
    return success(get_voice_profile(voice_id))


@router.patch("/{voice_id}")
def update_voice(voice_id: str, request: VoiceUpdateRequestDTO):
    return success(update_voice_profile(voice_id=voice_id, name=request.name))


@router.delete("/{voice_id}")
def delete_voice(voice_id: str):
    return success(delete_voice_profile(voice_id))


@router.post("")
async def create_voice(
    name: str = Form(default="我的音色"),
    audio: UploadFile = File(...),
    consent: bool = Form(default=False),
):
    return success(create_voice_profile(name=name, audio=audio, consent=consent))


@router.post("/from-material")
def create_voice_from_material(request: VoiceFromMaterialRequestDTO):
    return success(
        create_voice_profile_from_material(
            material_id=request.materialId,
            name=request.name,
            consent=request.consent,
            force=request.force,
        )
    )


@router.post("/{voice_id}/preview")
def preview_voice(voice_id: str, request: VoicePreviewRequestDTO):
    return success(create_voice_preview(voice_id=voice_id, text=request.text))


@router.get("/{voice_id}/{filename}")
def read_voice_file(voice_id: str, filename: str):
    path = get_voice_file(voice_id, filename)
    return FileResponse(path, media_type="audio/wav", filename=path.name)
