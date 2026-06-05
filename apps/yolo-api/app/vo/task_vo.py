from __future__ import annotations

from pydantic import BaseModel


class TaskVO(BaseModel):
    task_id: str
    status: str
    message: str

