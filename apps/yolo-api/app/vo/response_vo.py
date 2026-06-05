from __future__ import annotations

from pydantic import BaseModel


class ResponseVO(BaseModel):
    code: int
    message: str
    data: object | None = None

