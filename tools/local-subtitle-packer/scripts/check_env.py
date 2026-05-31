#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import shutil
import subprocess
import sys


def check_python() -> tuple[bool, str]:
    version = sys.version_info
    ok = version >= (3, 10)
    return ok, f"Python {version.major}.{version.minor}.{version.micro}"


def check_command(name: str) -> tuple[bool, str]:
    path = shutil.which(name)
    if path:
        return True, path
    return False, "未找到"


def check_faster_whisper() -> tuple[bool, str]:
    try:
        import faster_whisper  # type: ignore
    except ImportError:
        return False, "未安装"
    version = getattr(faster_whisper, "__version__", "unknown")
    return True, f"已安装 ({version})"


def check_subtitle_filter() -> tuple[bool, str]:
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        return False, "未安装 ffmpeg"
    try:
        result = subprocess.run([ffmpeg_path, "-filters"], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError:
        return False, "无法读取 ffmpeg 滤镜列表"

    filters = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            filters.add(parts[1])

    if "subtitles" in filters:
        return True, "支持 subtitles"
    if "ass" in filters:
        return True, "支持 ass"
    return False, "缺少 subtitles/ass（通常是 libass 未启用）"


def print_result(label: str, ok: bool, detail: str) -> None:
    status = "OK" if ok else "FAIL"
    print(f"[{status}] {label}: {detail}")


def main() -> None:
    results = [
        ("Python 版本", *check_python()),
        ("ffmpeg", *check_command("ffmpeg")),
        ("ffprobe", *check_command("ffprobe")),
        ("faster-whisper", *check_faster_whisper()),
        ("字幕滤镜支持", *check_subtitle_filter()),
    ]

    has_failure = False
    for label, ok, detail in results:
        print_result(label, ok, detail)
        has_failure = has_failure or not ok

    if has_failure:
        raise SystemExit(1)

    print("\n环境检查通过，可以开始本地字幕打包。")


if __name__ == "__main__":
    main()
