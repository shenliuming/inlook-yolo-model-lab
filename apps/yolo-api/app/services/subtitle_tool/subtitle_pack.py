#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Union
from typing import List, Optional


@dataclass
class SubtitleSegment:
    start: float
    end: float
    text: str


def run(cmd: List[str], quiet: bool = False) -> None:
    if not quiet:
        print("[cmd]", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError as exc:
        raise SystemExit(f"命令不存在：{cmd[0]}，请先安装。") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"命令执行失败：{' '.join(cmd)}") from exc


def get_ffmpeg_subtitle_filter() -> str:
    try:
        result = subprocess.run(
            ["ffmpeg", "-filters"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SystemExit("未检测到 ffmpeg。macOS：brew install ffmpeg") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit("无法检查 ffmpeg 滤镜，请确认 ffmpeg 安装完整。") from exc

    filter_names: set[str] = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            filter_names.add(parts[1])

    if "subtitles" in filter_names:
        return "subtitles"
    if "ass" in filter_names:
        return "ass"

    raise SystemExit(
        "当前 ffmpeg 不支持字幕烧录滤镜（缺少 subtitles/ass，通常是 libass 未启用）。"
        "请安装带 libass 的 ffmpeg。"
    )


def check_ffmpeg() -> str:
    if shutil.which("ffmpeg") is None:
        raise SystemExit("未检测到 ffmpeg。macOS：brew install ffmpeg")
    if shutil.which("ffprobe") is None:
        raise SystemExit("未检测到 ffprobe，请确认 ffmpeg 安装完整。")
    return get_ffmpeg_subtitle_filter()


def extract_audio(input_file: Union[Path, str], output_wav: Path) -> None:
    run([
        "ffmpeg", "-y",
        "-i", str(input_file),
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        "-acodec", "pcm_s16le",
        "-f", "wav",
        str(output_wav),
    ], quiet=True)


def clean_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    text = text.replace("\\N", " ")
    return text.strip()


def split_for_ass(text: str, max_chars: int = 24) -> str:
    text = clean_text(text)
    if len(text) <= max_chars:
        return text

    punctuation = "，。！？；、,.!?;"
    mid = len(text) // 2
    candidates = [i for i, ch in enumerate(text) if ch in punctuation]
    if candidates:
        split_at = min(candidates, key=lambda i: abs(i - mid)) + 1
    else:
        split_at = mid

    left = text[:split_at].strip()
    right = text[split_at:].strip()
    return f"{left}\\N{right}" if left and right else text


def srt_time(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600)
    t -= h * 3600
    m = int(t // 60)
    t -= m * 60
    s = int(t)
    ms = int(round((t - s) * 1000))
    if ms == 1000:
        s += 1
        ms = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def ass_time(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600)
    t -= h * 3600
    m = int(t // 60)
    t -= m * 60
    s = int(t)
    cs = int(round((t - s) * 100))
    if cs == 100:
        s += 1
        cs = 0
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def escape_ass_text(text: str) -> str:
    return split_for_ass(text).replace("{", "｛").replace("}", "｝")


def escape_ffmpeg_filter_path(path: Path) -> str:
    value = path.resolve().as_posix()
    value = value.replace("\\", r"\\")
    value = value.replace("'", r"\'")
    value = value.replace(":", r"\:")
    value = value.replace(",", r"\,")
    value = value.replace("[", r"\[")
    value = value.replace("]", r"\]")
    value = value.replace(" ", r"\ ")
    return value


def video_has_audio_stream(video: Path) -> bool:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=index",
        "-of", "csv=p=0",
        str(video),
    ]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise SystemExit("未检测到 ffprobe，请确认 ffmpeg 安装完整。") from exc
    except subprocess.CalledProcessError:
        return False
    return bool(result.stdout.strip())


def transcribe(
    audio_wav: Path,
    model_name: str,
    language: str,
    device: str,
    compute_type: str,
    beam_size: int,
    vad_filter: bool,
    initial_prompt: str | None = None,
) -> List[SubtitleSegment]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise SystemExit("未安装 faster-whisper，请先执行：uv pip install -r requirements.txt") from exc

    print(f"[whisper] model={model_name}, device={device}, compute_type={compute_type}")
    model = WhisperModel(model_name, device=device, compute_type=compute_type)

    segments, info = model.transcribe(
        str(audio_wav),
        language=language,
        task="transcribe",
        beam_size=beam_size,
        best_of=5,
        temperature=0,
        vad_filter=vad_filter,
        vad_parameters={"min_silence_duration_ms": 450},
        condition_on_previous_text=True,
        initial_prompt=initial_prompt,
        word_timestamps=False,
    )

    print(f"[whisper] language={info.language}, prob={info.language_probability:.2f}")

    out: List[SubtitleSegment] = []
    for seg in segments:
        text = clean_text(seg.text)
        if text:
            out.append(SubtitleSegment(float(seg.start), float(seg.end), text))
    return out


def write_srt(segments: List[SubtitleSegment], path: Path) -> None:
    lines = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{srt_time(seg.start)} --> {srt_time(seg.end)}")
        lines.append(seg.text)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_txt(segments: List[SubtitleSegment], path: Path) -> None:
    path.write_text("\n".join(seg.text for seg in segments) + "\n", encoding="utf-8")


def write_ass(
    segments: List[SubtitleSegment],
    path: Path,
    width: int,
    height: int,
    font_size: int,
    margin_v: int,
) -> None:
    ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: INLOOK,Noto Sans CJK SC,{font_size},&H00FFFFFF,&H000000FF,&H00101010,&H00000000,1,0,0,0,100,100,0,0,1,5,0,2,70,70,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    for seg in segments:
        ass += (
            f"Dialogue: 0,{ass_time(seg.start)},{ass_time(seg.end)},INLOOK,,0,0,0,,"
            f"{escape_ass_text(seg.text)}\n"
        )

    path.write_text(ass, encoding="utf-8")


def build_subtitle_filter(subtitle_filter_name: str, ass_file: Path, width: int, height: int) -> str:
    escaped_ass = escape_ffmpeg_filter_path(ass_file)
    if subtitle_filter_name == "subtitles":
        return f"subtitles=filename='{escaped_ass}':original_size={width}x{height}"
    return f"ass=filename='{escaped_ass}'"


def burn_video(
    video: Path,
    audio: Optional[Path],
    ass_file: Path,
    output: Path,
    width: int,
    height: int,
    crf: int,
    keep_original_audio: bool,
    subtitle_filter_name: str,
) -> None:
    subtitle_filter = build_subtitle_filter(subtitle_filter_name, ass_file, width, height)
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"{subtitle_filter}"
    )

    keep_source_audio = keep_original_audio and video_has_audio_stream(video)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video),
        "-vf", vf,
        "-map", "0:v:0",
    ]

    if audio:
        cmd += ["-i", str(audio), "-map", "1:a:0"]
    elif keep_source_audio:
        cmd += ["-map", "0:a:0?"]

    cmd += [
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
    ]

    if audio:
        cmd += ["-c:a", "aac", "-b:a", "160k", "-shortest"]
    elif keep_source_audio:
        cmd += ["-c:a", "aac", "-b:a", "160k"]

    cmd += ["-movflags", "+faststart", str(output)]
    run(cmd)


def main() -> None:
    parser = argparse.ArgumentParser(description="INLOOK Local Subtitle Packer")
    parser.add_argument("--video", required=True, help="输入视频 mp4")
    parser.add_argument("--audio", default=None, help="可选：单独录制的人声 m4a/mp3/wav")
    parser.add_argument("--output", required=True, help="输出视频 mp4")
    parser.add_argument("--model", default="small", help="tiny/base/small/medium/large-v3")
    parser.add_argument("--language", default="zh", help="默认 zh")
    parser.add_argument("--device", default="cpu", help="cpu/cuda/auto")
    parser.add_argument("--compute-type", default="int8", help="int8/float16/float32")
    parser.add_argument("--beam-size", type=int, default=5)
    parser.add_argument("--no-vad", action="store_true")
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--font-size", type=int, default=62)
    parser.add_argument("--margin-v", type=int, default=250)
    parser.add_argument("--crf", type=int, default=20)
    parser.add_argument("--no-audio", action="store_true", help="没有 --audio 时不保留原视频音频")

    args = parser.parse_args()
    subtitle_filter_name = check_ffmpeg()

    video = Path(args.video).expanduser().resolve()
    if not video.exists():
        raise SystemExit(f"视频不存在：{video}")

    audio = Path(args.audio).expanduser().resolve() if args.audio else None
    if audio and not audio.exists():
        raise SystemExit(f"音频不存在：{audio}")

    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    stem = output.with_suffix("")
    srt_path = stem.with_suffix(".srt")
    ass_path = stem.with_suffix(".ass")
    txt_path = stem.with_suffix(".txt")

    with tempfile.TemporaryDirectory(prefix="inlook_subtitle_") as td:
        wav_path = Path(td) / "asr.wav"
        asr_source = audio if audio else video

        extract_audio(asr_source, wav_path)
        segments = transcribe(
            wav_path,
            model_name=args.model,
            language=args.language,
            device=args.device,
            compute_type=args.compute_type,
            beam_size=args.beam_size,
            vad_filter=not args.no_vad,
        )

        if not segments:
            raise SystemExit("没有识别到有效语音。")

        write_srt(segments, srt_path)
        write_ass(segments, ass_path, args.width, args.height, args.font_size, args.margin_v)
        write_txt(segments, txt_path)

        print("[output]", srt_path)
        print("[output]", ass_path)
        print("[output]", txt_path)
        print(f"[ffmpeg] subtitle_filter={subtitle_filter_name}")

        burn_video(
            video=video,
            audio=audio,
            ass_file=ass_path,
            output=output,
            width=args.width,
            height=args.height,
            crf=args.crf,
            keep_original_audio=not args.no_audio,
            subtitle_filter_name=subtitle_filter_name,
        )

    print("[done]", output)


if __name__ == "__main__":
    main()
