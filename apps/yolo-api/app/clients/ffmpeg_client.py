from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from app.common import error_code
from app.common.exceptions import AppException


class FfmpegClient:
    def _ensure_binaries(self) -> None:
        if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
            raise AppException(
                error_code.INTERNAL_ERROR,
                "未检测到 ffmpeg/ffprobe，请先安装并配置环境变量。",
                status_code=500,
            )

    def probe_video(self, video_path: Path) -> dict:
        self._ensure_binaries()
        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size:stream=index,codec_type,codec_name,width,height",
            "-of",
            "json",
            str(video_path),
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise AppException(error_code.INTERNAL_ERROR, f"ffprobe 读取失败：{result.stderr.strip()}", status_code=500)

        payload = json.loads(result.stdout or "{}")
        streams = payload.get("streams") or []
        video_stream = next((item for item in streams if item.get("codec_type") == "video"), {})
        format_payload = payload.get("format") or {}
        try:
            duration = float(format_payload.get("duration") or 0.0)
        except (TypeError, ValueError):
            duration = 0.0
        try:
            file_size = int(format_payload.get("size") or video_path.stat().st_size)
        except (TypeError, ValueError, FileNotFoundError):
            file_size = video_path.stat().st_size

        return {
            "duration": round(duration, 3),
            "width": int(video_stream.get("width") or 0),
            "height": int(video_stream.get("height") or 0),
            "codec": str(video_stream.get("codec_name") or ""),
            "fileSize": file_size,
        }

    def generate_cover(self, video_path: Path, cover_path: Path) -> Path:
        self._ensure_binaries()
        cover_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(cover_path),
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0 or not cover_path.exists():
            raise AppException(error_code.INTERNAL_ERROR, f"封面截图生成失败：{result.stderr.strip()}", status_code=500)
        return cover_path


ffmpeg_client = FfmpegClient()
