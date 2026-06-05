from __future__ import annotations

from pydantic import BaseModel


class ContentLabHealthDTO(BaseModel):
    status: str
    message: str

