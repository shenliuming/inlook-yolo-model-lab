from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config.paths import CONTENT_LAB_RUNTIME_DIR

MATERIAL_ROOT = CONTENT_LAB_RUNTIME_DIR / "materials"
MATERIAL_ROOT.mkdir(parents=True, exist_ok=True)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def material_dir(material_id: str) -> Path:
    return MATERIAL_ROOT / material_id


def material_inputs_dir(material_id: str) -> Path:
    return material_dir(material_id) / "inputs"


def material_outputs_dir(material_id: str) -> Path:
    return material_dir(material_id) / "outputs"


def material_cache_dir(material_id: str) -> Path:
    return material_dir(material_id) / "cache"


def material_json_path(material_id: str) -> Path:
    return material_dir(material_id) / "material.json"


def material_raw_extract_response_path(material_id: str) -> Path:
    return material_cache_dir(material_id) / "raw_extract_response.json"


def material_log_path(material_id: str) -> Path:
    return material_dir(material_id) / "run.log"


def init_material_runtime(material_id: str) -> None:
    material_inputs_dir(material_id).mkdir(parents=True, exist_ok=True)
    material_outputs_dir(material_id).mkdir(parents=True, exist_ok=True)
    material_cache_dir(material_id).mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_material(material_id: str, payload: dict[str, Any]) -> None:
    payload["updatedAt"] = now()
    write_json(material_json_path(material_id), payload)


def read_material(material_id: str) -> dict[str, Any]:
    return read_json(material_json_path(material_id))


def append_log(material_id: str, message: str) -> None:
    path = material_log_path(material_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", errors="ignore") as file:
        file.write(message)
        if not message.endswith("\n"):
            file.write("\n")
