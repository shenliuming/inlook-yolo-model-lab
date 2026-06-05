from __future__ import annotations

from pydantic import BaseModel


class ModelSelectRequestDTO(BaseModel):
    model_id: str

