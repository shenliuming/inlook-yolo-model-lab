from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import UploadFile

from app.clients.ffmpeg_client import ffmpeg_client
from app.tasks.task_store import material_inputs_dir, material_outputs_dir


class LocalMaterialProvider:
    source_type = "local"

    def save(self, material_id: str, upload: UploadFile) -> dict:
        source_path = material_inputs_dir(material_id) / "source.mp4"
        with source_path.open("wb") as file:
            shutil.copyfileobj(upload.file, file)

        metadata = ffmpeg_client.probe_video(source_path)
        cover_path = ffmpeg_client.generate_cover(source_path, material_outputs_dir(material_id) / "cover.jpg")
        return {
            "sourceType": "local",
            "sourceUrl": "",
            "title": upload.filename or source_path.name,
            "description": "",
            "tags": [],
            "sourcePath": source_path,
            "coverPath": cover_path,
            **metadata,
        }
