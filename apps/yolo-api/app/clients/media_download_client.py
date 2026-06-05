from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from app.common import error_code
from app.common.exceptions import AppException


class MediaDownloadClient:
    def _ensure_ytdlp(self) -> None:
        if shutil.which("yt-dlp") is None:
            raise AppException(error_code.INTERNAL_ERROR, "未检测到 yt-dlp，请先安装后再提取抖音/B站素材。", status_code=500)

    def _read_metadata(self, source_url: str) -> dict:
        self._ensure_ytdlp()
        command = ["yt-dlp", "--dump-single-json", "--no-playlist", source_url]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            self._raise_download_error(result.stderr or result.stdout or "未知错误")
        return json.loads(result.stdout or "{}")

    def _raise_download_error(self, message: str) -> None:
        lowered = (message or "").lower()
        if "login" in lowered or "cookie" in lowered:
            raise AppException(error_code.INTERNAL_ERROR, "需要登录 Cookie 或该视频不可访问。", status_code=500)
        if "unsupported url" in lowered:
            raise AppException(error_code.BAD_REQUEST, "下载器暂不支持该链接格式。", status_code=400)
        raise AppException(error_code.INTERNAL_ERROR, message.strip(), status_code=500)

    def download(self, source_url: str, output_dir: Path) -> dict:
        metadata = self._read_metadata(source_url)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_template = output_dir / "source.%(ext)s"
        command = [
            "yt-dlp",
            "--no-playlist",
            "--write-thumbnail",
            "-o",
            str(output_template),
            source_url,
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            self._raise_download_error(result.stderr or result.stdout or "未知错误")

        video_path = next(
            (
                path
                for path in output_dir.iterdir()
                if path.is_file() and path.suffix.lower() not in {".json", ".jpg", ".jpeg", ".png", ".webp", ".part"}
            ),
            None,
        )
        if video_path is None:
            raise AppException(error_code.INTERNAL_ERROR, "素材获取失败：下载完成但未找到视频文件。", status_code=500)

        thumbnail_path = next(
            (
                path
                for path in output_dir.iterdir()
                if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
            ),
            None,
        )
        return {
            "title": metadata.get("title") or "",
            "description": metadata.get("description") or "",
            "tags": list(metadata.get("tags") or []),
            "thumbnailPath": str(thumbnail_path) if thumbnail_path else "",
            "sourceUrl": source_url,
            "videoPath": str(video_path),
        }


media_download_client = MediaDownloadClient()
