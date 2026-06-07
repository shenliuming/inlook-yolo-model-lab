from __future__ import annotations

from pydantic import BaseModel, Field


class DigitalHumanGenerateRequestDTO(BaseModel):
    script: str = Field(min_length=1, max_length=10000)
    audioId: str | None = Field(default=None, max_length=160)
    audioUrl: str = Field(min_length=1, max_length=1000)
    avatarId: str = Field(min_length=1, max_length=120)
    mode: str = Field(default="talking_head", max_length=80)
