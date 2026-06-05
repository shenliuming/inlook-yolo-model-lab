#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .base import DownloadEngine, DownloadResult


class YouGetEngine(DownloadEngine):
    name = "you-get"

    def can_handle(self, source: str, platform: str) -> bool:
        return shutil.which("you-get") is not None and platform not in {"local", "wechat_channels"}

    def download(self, source: str, work_dir: Path, platform: str) -> DownloadResult:
        if shutil.which("you-get") is None:
            return DownloadResult(False, self.name, platform, source_url=source, error="you-get not found")

        work_dir.mkdir(parents=True, exist_ok=True)
        before = {p.resolve() for p in work_dir.glob("*")}

        cmd = [
            "you-get",
            "-o", str(work_dir),
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
                next_action="当前链接 you-get 解析失败，将尝试下一个引擎。",
            )

        after = [p for p in work_dir.glob("*") if p.resolve() not in before and p.is_file()]
        videos = [p for p in after if p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov", ".flv"}]
        if not videos:
            videos = [p for p in work_dir.glob("*") if p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov", ".flv"}]
        if not videos:
            return DownloadResult(False, self.name, platform, source_url=source, error="no video file found")

        video_path = max(videos, key=lambda p: p.stat().st_size)
        return DownloadResult(
            ok=True,
            engine=self.name,
            platform=platform,
            source_url=source,
            output_path=str(video_path),
            title=video_path.stem,
            next_action="可以继续进行标准化转码。",
        )
