from __future__ import annotations

from pathlib import Path

from app.clients.ffmpeg_client import ffmpeg_client
from app.clients.media_download_client import media_download_client
from app.tasks.task_store import material_inputs_dir, material_outputs_dir


class BilibiliMaterialProvider:
    source_type = "bilibili"

    def extract(self, material_id: str, source_url: str) -> dict:
        payload = media_download_client.download(source_url, material_inputs_dir(material_id))
        video_path = Path(payload["videoPath"])
        cover_candidate = Path(payload["thumbnailPath"]) if payload.get("thumbnailPath") else None
        if cover_candidate and cover_candidate.exists():
            cover_path = cover_candidate
        else:
            cover_path = ffmpeg_client.generate_cover(video_path, material_outputs_dir(material_id) / "cover.jpg")
        metadata = ffmpeg_client.probe_video(video_path)
        return {
            "sourceType": "bilibili",
            "sourceUrl": source_url,
            "title": payload.get("title") or "",
            "description": payload.get("description") or "",
            "tags": payload.get("tags") or [],
            "sourcePath": video_path,
            "coverPath": cover_path,
            **metadata,
        }
