from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.config.settings import (
    get_whisper_beam_size,
    get_whisper_compute_type,
    get_whisper_device,
    get_whisper_language,
    get_whisper_model,
)


class MaterialSourceRequestDTO(BaseModel):
    sourceType: Literal["douyin", "bilibili"]
    sourceUrl: str = Field(min_length=1)
    engine: str = Field(default="auto")


class TranscriptionCreateRequestDTO(BaseModel):
    materialId: str = Field(min_length=1)
    model: str = Field(default_factory=get_whisper_model)
    language: str = Field(default_factory=get_whisper_language)
    device: str = Field(default_factory=get_whisper_device)
    computeType: str = Field(default_factory=get_whisper_compute_type)
    beamSize: int = Field(default_factory=get_whisper_beam_size, ge=1, le=10)


class TtsSynthesisCreateRequestDTO(BaseModel):
    text: str = Field(min_length=1)
    voiceId: str | None = Field(default=None, max_length=100)
    voice: str = Field(default="", max_length=100)
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    emotion: str = Field(default="", max_length=100)
    volume: int = Field(default=80, ge=0, le=100)
    language: str = Field(default="zh")
    trainingId: str | None = None
    voiceMode: Literal["preset", "clone"] = "clone"
    executionProvider: str = Field(default="cpu")
