#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


def ffprobe_metadata(video_path: Path) -> dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,duration",
        "-of", "json",
        str(video_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(proc.stdout or "{}")
    stream = (data.get("streams") or [{}])[0]

    fps = 0.0
    rate = stream.get("r_frame_rate")
    if rate and "/" in rate:
        a, b = rate.split("/", 1)
        try:
            fps = float(a) / float(b)
        except Exception:
            fps = 0.0

    duration = stream.get("duration")
    try:
        duration = float(duration) if duration is not None else 0.0
    except Exception:
        duration = 0.0

    return {
        "width": int(stream.get("width") or 0),
        "height": int(stream.get("height") or 0),
        "fps": round(fps, 3),
        "duration": round(duration, 3),
    }
