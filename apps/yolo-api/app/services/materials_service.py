from __future__ import annotations

from fastapi import BackgroundTasks, HTTPException, UploadFile

from app.providers.provider_registry import get_material_provider, list_material_source_types
from app.services.material_intake_service import get_material_task


def create_local_material(
    *,
    background_tasks: BackgroundTasks,
    upload: UploadFile | None,
) -> dict:
    provider = get_material_provider("local")
    task = provider.fetch_material(background_tasks=background_tasks, upload=upload)
    return _build_material_response(task)


def create_remote_material(
    *,
    background_tasks: BackgroundTasks,
    source_type: str,
    source_url: str,
    engine: str,
) -> dict:
    provider = get_material_provider(source_type)
    task = provider.fetch_material(background_tasks=background_tasks, source_url=source_url, engine=engine)
    return _build_material_response(task)


def get_material(material_id: str) -> dict:
    task = get_material_task(material_id)
    return _build_material_response(task)


def list_material_sources() -> list[dict[str, str]]:
    return list_material_source_types()


def _build_material_response(task: dict) -> dict:
    metadata = task.get("metadata") or {}
    downloads = task.get("downloads") or {}
    source_type = metadata.get("sourceType") or metadata.get("platform") or metadata.get("source_type") or task.get("mode")
    if not task.get("task_id"):
        raise HTTPException(status_code=500, detail="素材任务缺少 task_id")
    return {
        "materialId": task["task_id"],
        "taskId": task["task_id"],
        "sourceType": source_type,
        "status": task.get("status"),
        "message": task.get("message"),
        "metadata": metadata,
        "files": {
            "video": downloads.get("input.mp4"),
            "metadata": downloads.get("metadata.json"),
            "status": downloads.get("status.json"),
            "log": downloads.get("run.log"),
        },
        "createdAt": task.get("created_at"),
        "updatedAt": task.get("updated_at"),
    }
