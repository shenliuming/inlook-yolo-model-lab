from __future__ import annotations

from pydantic import BaseModel, Field

from app.config.settings import (
    get_whisper_beam_size,
    get_whisper_compute_type,
    get_whisper_device,
    get_whisper_language,
    get_whisper_model,
)


class StudioProjectCreateRequestDTO(BaseModel):
    name: str = Field(default="", max_length=120)


class StudioProjectTranscriptionRequestDTO(BaseModel):
    materialId: str = Field(default="", max_length=120)
    model: str = Field(default_factory=get_whisper_model)
    language: str = Field(default_factory=get_whisper_language)
    device: str = Field(default_factory=get_whisper_device)
    computeType: str = Field(default_factory=get_whisper_compute_type)
    beamSize: int = Field(default_factory=get_whisper_beam_size, ge=1, le=10)

