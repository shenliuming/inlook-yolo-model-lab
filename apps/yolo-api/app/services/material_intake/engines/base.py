#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass
class DownloadResult:
    ok: bool
    engine: str
    platform: str
    source_url: str = ""
    output_path: str = ""
    title: str = ""
    duration: float = 0.0
    error: str = ""
    next_action: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DownloadEngine:
    name = "base"

    def can_handle(self, source: str, platform: str) -> bool:
        return False

    def download(self, source: str, work_dir: Path, platform: str) -> DownloadResult:
        raise NotImplementedError
