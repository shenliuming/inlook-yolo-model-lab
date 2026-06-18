from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.config.paths import PROJECTS_RUNTIME_DIR

PROJECTS_ROOT = PROJECTS_RUNTIME_DIR
PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_project_id() -> str:
    return f"proj_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"


def project_dir(project_id: str) -> Path:
    return PROJECTS_ROOT / project_id


def project_json_path(project_id: str) -> Path:
    return project_dir(project_id) / "project.json"


def project_tasks_dir(project_id: str) -> Path:
    return project_dir(project_id) / "tasks"


def project_materials_dir(project_id: str) -> Path:
    return project_dir(project_id) / "materials"


def project_current_material_dir(project_id: str) -> Path:
    return project_materials_dir(project_id) / "current"


def project_transcriptions_dir(project_id: str) -> Path:
    return project_dir(project_id) / "transcriptions"


def project_transcription_dir(project_id: str, transcription_id: str) -> Path:
    return project_transcriptions_dir(project_id) / transcription_id


def project_copywriting_dir(project_id: str) -> Path:
    return project_dir(project_id) / "copywriting"


def project_tts_dir(project_id: str) -> Path:
    return project_dir(project_id) / "tts"


def project_tts_synthesis_dir(project_id: str, synthesis_id: str) -> Path:
    return project_tts_dir(project_id) / "synthesis" / synthesis_id


def project_subtitles_dir(project_id: str) -> Path:
    return project_dir(project_id) / "subtitles"


def project_render_dir(project_id: str) -> Path:
    return project_dir(project_id) / "render"


def project_digital_human_dir(project_id: str) -> Path:
    return project_dir(project_id) / "digital_human"


def project_digital_human_task_dir(project_id: str, task_id: str) -> Path:
    return project_digital_human_dir(project_id) / task_id


def init_project_runtime(project_id: str) -> None:
    for directory in (
        project_dir(project_id),
        project_tasks_dir(project_id),
        project_materials_dir(project_id),
        project_current_material_dir(project_id),
        project_transcriptions_dir(project_id),
        project_copywriting_dir(project_id),
        project_tts_dir(project_id),
        project_subtitles_dir(project_id),
        project_render_dir(project_id),
        project_digital_human_dir(project_id),
    ):
        directory.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _default_project_payload(project_id: str, name: str = "") -> dict[str, Any]:
    timestamp = now()
    return {
        "projectId": project_id,
        "name": name or "未命名项目",
        "status": "active",
        "current": {
            "materialId": "",
            "transcriptionId": "",
            "rewriteId": "",
            "synthesisId": "",
            "digitalHumanTaskId": "",
        },
        "artifacts": {
            "material": None,
            "transcription": None,
            "copywriting": None,
            "tts": None,
            "digitalHuman": None,
        },
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }


def create_project(name: str = "") -> dict[str, Any]:
    project_id = build_project_id()
    init_project_runtime(project_id)
    payload = _default_project_payload(project_id, name=name)
    write_project(project_id, payload)
    return payload


def read_project(project_id: str) -> dict[str, Any]:
    path = project_json_path(project_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="项目不存在")
    return read_json(path)


def write_project(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    init_project_runtime(project_id)
    payload["projectId"] = project_id
    payload["updatedAt"] = now()
    if not payload.get("createdAt"):
        payload["createdAt"] = payload["updatedAt"]
    write_json(project_json_path(project_id), payload)
    return payload


def update_project(project_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    current = read_project(project_id)
    merged = {**current, **patch}
    if isinstance(current.get("current"), dict) or isinstance(patch.get("current"), dict):
        merged["current"] = {
            **(current.get("current") or {}),
            **(patch.get("current") or {}),
        }
    if isinstance(current.get("artifacts"), dict) or isinstance(patch.get("artifacts"), dict):
        merged["artifacts"] = {
            **(current.get("artifacts") or {}),
            **(patch.get("artifacts") or {}),
        }
    return write_project(project_id, merged)


def clear_directory(path: Path) -> None:
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        return
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def copy_tree(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    clear_directory(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        target = destination / child.name
        if child.is_dir():
            shutil.copytree(child, target)
        else:
            shutil.copy2(child, target)


def copy_file(source: Path, destination: Path) -> None:
    if not source.exists() or not source.is_file():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def project_file_url(project_id: str, relative_path: str | Path) -> str:
    return f"/api/v1/studio/projects/{project_id}/files/{Path(relative_path).as_posix()}"


def read_project_file(project_id: str, relative_path: str) -> Path:
    root = project_dir(project_id).resolve()
    target = (root / relative_path).resolve()
    if root not in target.parents and target != root:
        raise HTTPException(status_code=404, detail="项目文件不存在")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="项目文件不存在")
    return target


def write_project_task(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    task_id = str(payload.get("taskId") or payload.get("task_id") or "").strip()
    if not task_id:
        raise HTTPException(status_code=500, detail="任务快照缺少 taskId")
    normalized = {**payload, "taskId": task_id, "projectId": project_id, "updatedAt": now()}
    if not normalized.get("createdAt"):
        normalized["createdAt"] = normalized["updatedAt"]
    write_json(project_tasks_dir(project_id) / f"{task_id}.json", normalized)
    return normalized


def list_project_tasks(limit: int = 50) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for path in PROJECTS_ROOT.glob("*/tasks/*.json"):
        try:
            payload = read_json(path)
        except Exception:
            continue
        if isinstance(payload, dict):
            tasks.append(payload)
    tasks.sort(key=lambda item: item.get("createdAt") or "", reverse=True)
    return tasks[:limit]
