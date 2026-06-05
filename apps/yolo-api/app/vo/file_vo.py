from __future__ import annotations

from pydantic import BaseModel


class FileVO(BaseModel):
    name: str
    url: str

