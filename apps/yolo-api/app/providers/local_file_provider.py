from __future__ import annotations

from fastapi import BackgroundTasks, HTTPException, UploadFile

from app.providers.material_provider import MaterialProvider
from app.services.material_intake_service import create_material_task


class LocalFileProvider(MaterialProvider):
    source_type = "local"

    def fetch_material(
        self,
        *,
        background_tasks: BackgroundTasks,
        source_url: str = "",
        upload: UploadFile | None = None,
        engine: str = "auto",
    ) -> dict:
        if upload is None:
            raise HTTPException(status_code=400, detail="请上传本地视频文件")
        return create_material_task(
            background_tasks=background_tasks,
            mode="upload",
            text="",
            url="",
            engine=engine,
            upload=upload,
        )

    def get_metadata(self, task: dict) -> dict:
        metadata = dict(task.get("metadata") or {})
        metadata["sourceType"] = "local"
        return metadata
