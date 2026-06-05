from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.config.paths import CONTENT_LAB_TTS_RUNTIME_DIR, STUDIO_TRANSCRIPTION_RUNTIME_DIR, STUDIO_TTS_TRAINING_RUNTIME_DIR

LEGACY_MATERIAL_ROOT = Path(__file__).resolve().parent.parent.parent / "runtime" / "content_workflow" / "material_intake" / "tasks"


def _safe_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_status(status: str) -> str:
    mapping = {
        "queued": "pending",
        "pending": "pending",
        "running": "running",
        "success": "success",
        "failed": "failed",
        "cancelled": "cancelled",
    }
    return mapping.get((status or "").lower(), "pending")


def _infer_stage(task_type: str, task: dict[str, Any]) -> str:
    if task_type == "material.fetch":
        return "素材获取"
    if task_type == "transcription.extract":
        return str(task.get("stage") or "文案提取")
    if task_type == "tts.training":
        return str(task.get("stage") or "音色准备")
    if task_type == "tts.synthesis":
        return "语音合成"
    return "处理中"


def _material_task_from_dir(task_id: str, task_dir: Path) -> dict[str, Any] | None:
    task = _safe_json(task_dir / "task.json")
    if not task:
        return None
    status = _normalize_status(task.get("status", "pending"))
    metadata = task.get("metadata") or {}
    return {
        "taskId": task_id,
        "taskType": "material.fetch",
        "sourceType": metadata.get("platform") or metadata.get("source_type") or task.get("mode") or "unknown",
        "status": status,
        "stage": _infer_stage("material.fetch", task),
        "progress": 100 if status == "success" else (60 if status == "running" else 0),
        "input": {
            "mode": task.get("mode"),
            "engine": task.get("engine"),
        },
        "outputs": {
            "metadata": metadata,
            "downloads": task.get("downloads") or {},
        },
        "errorMessage": task.get("message") if status == "failed" else "",
        "createdAt": task.get("created_at"),
        "updatedAt": task.get("updated_at"),
    }


def _generic_task_from_dir(task_dir: Path, task_type: str, source_type: str = "") -> dict[str, Any] | None:
    task = _safe_json(task_dir / "task.json")
    if not task:
        return None
    status = _normalize_status(task.get("status", "pending"))
    return {
        "taskId": task.get("task_id") or task_dir.name,
        "taskType": task_type,
        "sourceType": source_type or task.get("source_type") or "",
        "status": status,
        "stage": _infer_stage(task_type, task),
        "progress": int(task.get("progress") or (100 if status == "success" else (65 if status == "running" else 0))),
        "input": task.get("input") or {},
        "outputs": {
            "downloads": task.get("downloads") or {},
            "materialId": task.get("material_id"),
            "voiceId": task.get("voice_id"),
            "subtitleFiles": task.get("subtitle_files") or {},
        },
        "errorMessage": task.get("message") if status == "failed" else "",
        "createdAt": task.get("created_at"),
        "updatedAt": task.get("updated_at"),
    }


def list_tasks(limit: int = 50) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []

    for task_dir in sorted(LEGACY_MATERIAL_ROOT.glob("*"), reverse=True):
        if task_dir.is_dir():
            task = _material_task_from_dir(task_dir.name, task_dir)
            if task:
                tasks.append(task)

    for task_dir in sorted(STUDIO_TRANSCRIPTION_RUNTIME_DIR.glob("*"), reverse=True):
        if task_dir.is_dir():
            task = _generic_task_from_dir(task_dir, "transcription.extract")
            if task:
                tasks.append(task)

    for task_dir in sorted(STUDIO_TTS_TRAINING_RUNTIME_DIR.glob("*"), reverse=True):
        if task_dir.is_dir():
            task = _generic_task_from_dir(task_dir, "tts.training")
            if task:
                tasks.append(task)

    for task_dir in sorted(CONTENT_LAB_TTS_RUNTIME_DIR.glob("*"), reverse=True):
        if task_dir.is_dir():
            task = _generic_task_from_dir(task_dir, "tts.synthesis")
            if task:
                tasks.append(task)

    tasks.sort(key=lambda item: item.get("createdAt") or "", reverse=True)
    return tasks[:limit]


def get_task(task_id: str) -> dict[str, Any]:
    for task in list_tasks(limit=500):
        if task["taskId"] == task_id:
            return task
    raise HTTPException(status_code=404, detail="任务不存在")
