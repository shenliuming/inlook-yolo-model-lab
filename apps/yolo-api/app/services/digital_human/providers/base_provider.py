from __future__ import annotations

from pathlib import Path
from typing import Any


class BaseDigitalHumanProvider:
    code = "base_provider"

    def import_template(
        self,
        *,
        template_id: str,
        file_path: Path,
        name: str,
        training_type: str,
        resolution_label: str,
        log_path: Path,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def sync_templates(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def generate_video(
        self,
        *,
        task_id: str,
        template: dict[str, Any],
        script: str,
        audio_path: Path | None,
        log_path: Path,
    ) -> dict[str, Any]:
        raise NotImplementedError
