from __future__ import annotations

from pydantic import BaseModel


class TtsTaskRequestDTO(BaseModel):
    text: str
    voice: str = "default"

