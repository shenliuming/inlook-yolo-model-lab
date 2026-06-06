from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AiTestRequestDTO(BaseModel):
    prompt: str = Field(default="你好", min_length=1, max_length=2000)


class CopyRewriteRequestDTO(BaseModel):
    sourceText: str = Field(min_length=1, max_length=20000)
    sourceTextType: Literal["video_transcript", "manual", "platform_description", "empty"] = "manual"
    allowPlatformText: bool = False
    instruction: str = Field(default="", max_length=4000)
    template: str = Field(default="", max_length=100)
