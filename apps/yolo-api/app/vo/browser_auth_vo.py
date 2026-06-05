from __future__ import annotations

from pydantic import BaseModel


class BrowserAuthVO(BaseModel):
    platform: str
    status: str
    profilePath: str
    updatedAt: str
    lastCheckAt: str
    message: str
