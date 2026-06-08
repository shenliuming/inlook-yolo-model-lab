from __future__ import annotations

from pydantic import BaseModel, Field


class VoicePreviewRequestDTO(BaseModel):
    text: str = Field(default="你好，这是当前音色的一段试听。", max_length=300)


class VoiceUpdateRequestDTO(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class VoiceFromMaterialRequestDTO(BaseModel):
    materialId: str = Field(min_length=1, max_length=120)
    name: str = Field(default="当前视频音色", max_length=100)
    consent: bool = False
    force: bool = False
