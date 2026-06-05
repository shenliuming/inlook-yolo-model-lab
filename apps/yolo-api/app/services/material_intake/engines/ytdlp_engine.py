#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from .base import DownloadEngine, DownloadResult


class YtDlpEngine(DownloadEngine):
    name = "yt-dlp"

    def can_handle(self, source: str, platform: str) -> bool:
        return shutil.which("yt-dlp") is not None and platform not in {"local", "wechat_channels"}

    def download(self, source: str, work_dir: Path, platform: str) -> DownloadResult:
        if shutil.which("yt-dlp") is None:
            return DownloadResult(False, self.name, platform, source_url=source, error="yt-dlp not found")

        work_dir.mkdir(parents=True, exist_ok=True)
        out_template = str(work_dir / "source.%(ext)s")
        cmd = [
            "yt-dlp",
            "--no-playlist",
            "--write-info-json",
            "--merge-output-format", "mp4",
            "-f", "bv*+ba/best",
            "-o", out_template,
            source,
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            err = (exc.stderr or exc.stdout or str(exc))[-1200:]
            return DownloadResult(
                ok=False,
                engine=self.name,
                platform=platform,
                source_url=source,
                error=err,
                next_action="当前链接 yt-dlp 解析失败，将尝试下一个引擎。",
            )

        video_path = self._find_video(work_dir)
        if video_path is None:
            return DownloadResult(False, self.name, platform, source_url=source, error="no video file found")

        title = ""
        duration = 0.0
        for info in work_dir.glob("source*.info.json"):
            try:
                data = json.loads(info.read_text(encoding="utf-8"))
                title = data.get("title") or ""
                duration = float(data.get("duration") or 0.0)
                break
            except Exception:
                pass

        return DownloadResult(
            ok=True,
            engine=self.name,
            platform=platform,
            source_url=source,
            output_path=str(video_path),
            title=title,
            duration=duration,
            next_action="可以继续进行标准化转码。",
        )

    @staticmethod
    def _find_video(work_dir: Path) -> Path | None:
        candidates: list[Path] = []
        for ext in ("mp4", "mkv", "webm", "mov", "m4v", "flv"):
            candidates.extend(work_dir.glob(f"source.{ext}"))
        if not candidates:
            return None
        return max(candidates, key=lambda p: p.stat().st_size)
