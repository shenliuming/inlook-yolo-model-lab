from __future__ import annotations

from abc import ABC, abstractmethod

from fastapi import BackgroundTasks, UploadFile


class MaterialProvider(ABC):
    source_type = "unknown"

    def support(self, source_type: str) -> bool:
        return source_type == self.source_type

    @abstractmethod
    def fetch_material(
        self,
        *,
        background_tasks: BackgroundTasks,
        source_url: str = "",
        upload: UploadFile | None = None,
        engine: str = "auto",
    ) -> dict:
        raise NotImplementedError

    @abstractmethod
    def get_metadata(self, task: dict) -> dict:
        raise NotImplementedError
