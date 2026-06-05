from __future__ import annotations

from pydantic import BaseModel


class IdPathDTO(BaseModel):
    task_id: str

