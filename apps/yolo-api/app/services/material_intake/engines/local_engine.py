#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import shutil
from pathlib import Path

from .base import DownloadEngine, DownloadResult


class LocalEngine(DownloadEngine):
    name = "local"

    def can_handle(self, source: str, platform: str) -> bool:
        return platform == "local"

    def download(self, source: str, work_dir: Path, platform: str) -> DownloadResult:
        path = Path(source).expanduser().resolve()
        if not path.exists():
            return DownloadResult(
                ok=False,
                engine=self.name,
                platform="local",
                error=f"Local file not found: {path}",
                next_action="请选择存在的本地视频文件。",
            )

        work_dir.mkdir(parents=True, exist_ok=True)
        target = work_dir / f"source{path.suffix.lower() or '.mp4'}"
        shutil.copy2(path, target)

        return DownloadResult(
            ok=True,
            engine=self.name,
            platform="local",
            output_path=str(target),
            title=path.stem,
            next_action="可以继续进行标准化转码。",
        )
