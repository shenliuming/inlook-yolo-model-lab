#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from scripts.subtitle_pack import (
        build_subtitle_filter,
        run,
        video_has_audio_stream,
    )
except ImportError:
    from subtitle_pack import (  # type: ignore
        build_subtitle_filter,
        run,
        video_has_audio_stream,
    )


def check_ffmpeg_ass() -> None:
    try:
        from scripts.subtitle_pack import check_ffmpeg
    except ImportError:
        from subtitle_pack import check_ffmpeg  # type: ignore

    subtitle_filter_name = check_ffmpeg()
    if subtitle_filter_name != "ass":
        raise SystemExit("当前 ffmpeg 不支持 ass 滤镜，无法保留 ASS 字幕样式。请安装带 libass 的 ffmpeg。")


def burn_ass_video(
    video: Path,
    ass_file: Path,
    output: Path,
    crf: int,
    keep_original_audio: bool,
) -> None:
    subtitle_filter = build_subtitle_filter("ass", ass_file, 0, 0)
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video),
        "-vf", subtitle_filter,
        "-map", "0:v:0",
    ]

    if keep_original_audio and video_has_audio_stream(video):
        cmd += ["-map", "0:a:0?"]

    cmd += [
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
    ]

    if keep_original_audio and video_has_audio_stream(video):
        cmd += ["-c:a", "aac", "-b:a", "160k"]

    cmd += ["-movflags", "+faststart", str(output)]
    run(cmd)


def main() -> None:
    parser = argparse.ArgumentParser(description="Burn edited ASS subtitles back into video without rerunning Whisper")
    parser.add_argument("--video", required=True, help="输入视频 mp4")
    parser.add_argument("--ass", required=True, help="已经修改好的 ASS 字幕文件")
    parser.add_argument("--output", required=True, help="输出视频 mp4")
    parser.add_argument("--crf", type=int, default=20)
    parser.add_argument("--no-audio", action="store_true", help="不保留原视频音频")
    args = parser.parse_args()

    check_ffmpeg_ass()

    video = Path(args.video).expanduser().resolve()
    ass_file = Path(args.ass).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()

    if not video.exists():
        raise SystemExit(f"视频不存在：{video}")
    if not ass_file.exists():
        raise SystemExit(f"ASS 字幕不存在：{ass_file}")

    output.parent.mkdir(parents=True, exist_ok=True)

    burn_ass_video(
        video=video,
        ass_file=ass_file,
        output=output,
        crf=args.crf,
        keep_original_audio=not args.no_audio,
    )

    print("[done]", output)


if __name__ == "__main__":
    main()
