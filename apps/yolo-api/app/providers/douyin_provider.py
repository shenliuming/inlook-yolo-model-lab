from __future__ import annotations

from fastapi import BackgroundTasks, HTTPException, UploadFile

from app.providers.material_provider import MaterialProvider
from app.services.material_intake.platform_detector import detect_platform_from_url
from app.services.material_intake_service import create_material_task


class DouyinProvider(MaterialProvider):
    source_type = "douyin"

    def fetch_material(
        self,
        *,
        background_tasks: BackgroundTasks,
        source_url: str = "",
        upload: UploadFile | None = None,
        engine: str = "auto",
    ) -> dict:
        if detect_platform_from_url(source_url) != "douyin":
            raise HTTPException(status_code=400, detail="当前链接不是抖音链接")
        return create_material_task(
            background_tasks=background_tasks,
            mode="url",
            text="",
            url=source_url,
            engine=engine,
            upload=None,
        )

    def get_metadata(self, task: dict) -> dict:
        metadata = dict(task.get("metadata") or {})
        metadata["sourceType"] = "douyin"
        return metadata
