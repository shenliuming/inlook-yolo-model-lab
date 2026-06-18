from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract overlapping candidate clips for Template Clip Bank MVP")
    parser.add_argument("--runtime-dir", required=True, help="Template Clip Bank runtime directory")
    parser.add_argument("--template-video", default="", help="Optional override for template video path")
    parser.add_argument("--segment-length", type=float, default=5.0, help="Candidate clip length in seconds")
    parser.add_argument("--step", type=float, default=2.0, help="Sliding window step in seconds")
    return parser.parse_args()


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True)


def _probe_duration(path: Path) -> float:
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nk=1:nw=1",
            str(path),
        ]
    )
    if result.returncode != 0:
        raise SystemExit(f"ffprobe failed for {path}: {(result.stderr or result.stdout).strip()}")
    try:
        return float((result.stdout or "0").strip() or 0.0)
    except ValueError as exc:
        raise SystemExit(f"Could not parse duration for {path}") from exc


def _load_config(runtime_dir: Path) -> dict[str, Any]:
    config_path = runtime_dir / "config.json"
    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text(encoding="utf-8"))


def _resolve_template_video(runtime_dir: Path, override: str) -> Path:
    if override:
        path = Path(override).expanduser()
        if not path.is_absolute():
            path = runtime_dir / path
        return path.resolve()
    config = _load_config(runtime_dir)
    config_value = str(config.get("template_video") or "input/template.mp4")
    path = Path(config_value).expanduser()
    if not path.is_absolute():
        path = runtime_dir / path
    return path.resolve()


def _build_windows(duration: float, segment_length: float, step: float) -> list[tuple[float, float]]:
    if duration <= 0:
        return []
    if duration <= segment_length:
        return [(0.0, duration)]
    max_start = duration - segment_length
    count = int(math.floor(max_start / step)) + 1
    windows: list[tuple[float, float]] = []
    for index in range(count):
        start = round(index * step, 3)
        end = round(min(start + segment_length, duration), 3)
        windows.append((start, end))
    return windows


def _source_group_for_index(index: int, segment_length: float, step: float) -> str:
    windows_per_group = max(1, int(math.ceil(segment_length / step)))
    group_index = index // windows_per_group
    return f"group_{group_index + 1:03d}"


def _extract_clip(source: Path, output: Path, start: float, duration: float) -> None:
    command = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-ss",
        f"{start:.3f}",
        "-i",
        str(source),
        "-t",
        f"{duration:.3f}",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        str(output),
    ]
    result = _run(command)
    if result.returncode != 0:
        fallback = [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-ss",
            f"{start:.3f}",
            "-i",
            str(source),
            "-t",
            f"{duration:.3f}",
            "-c:v",
            "mpeg4",
            "-q:v",
            "4",
            "-c:a",
            "aac",
            str(output),
        ]
        fallback_result = _run(fallback)
        if fallback_result.returncode != 0:
            message = (fallback_result.stderr or fallback_result.stdout or result.stderr or result.stdout).strip()
            raise SystemExit(f"Failed to extract clip {output.name}: {message}")


def main() -> int:
    args = parse_args()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    candidates_dir = runtime_dir / "candidates"
    reports_dir = runtime_dir / "reports"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    if args.segment_length <= 0:
        raise SystemExit("segment-length must be > 0")
    if args.step <= 0:
        raise SystemExit("step must be > 0")

    template_video = _resolve_template_video(runtime_dir, args.template_video)
    if not template_video.exists():
        raise SystemExit(f"Missing template video: {template_video}")

    duration = _probe_duration(template_video)
    windows = _build_windows(duration, args.segment_length, args.step)
    clips: list[dict[str, Any]] = []

    for index, (start, end) in enumerate(windows, start=1):
        clip_id = f"clip_{index:03d}"
        clip_path = candidates_dir / f"{clip_id}.mp4"
        _extract_clip(template_video, clip_path, start, end - start)
        clips.append(
            {
                "clip_id": clip_id,
                "start": start,
                "end": end,
                "duration": round(end - start, 3),
                "path": f"candidates/{clip_id}.mp4",
                "source_group": _source_group_for_index(index - 1, args.segment_length, args.step),
                "content_hint": "",
                "motion_hint": "",
                "tags": [],
                "usable": True,
                "manual_note": "",
            }
        )

    report = {
        "source_video": str(template_video),
        "duration": round(duration, 3),
        "segment_length": args.segment_length,
        "step": args.step,
        "clip_count": len(clips),
        "clips": clips,
    }
    candidates_json = reports_dir / "candidates.json"
    candidates_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[DONE] source={template_video}")
    print(f"[DONE] clips={len(clips)}")
    print(f"[DONE] report={candidates_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
