from __future__ import annotations

from pydantic import BaseModel, Field


class BrowserAuthPlatformDTO(BaseModel):
    platform: str = Field(min_length=1)
