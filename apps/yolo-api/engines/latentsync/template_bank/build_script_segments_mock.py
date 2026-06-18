from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any


TYPE_KEYWORDS = {
    "transition": ["但是", "不过", "反过来", "先说", "接下来", "然后", "另外", "第二", "第三"],
    "emphasis": ["重点", "关键", "一定", "必须", "真正", "核心", "最重要"],
}

TYPE_CONFIG = {
    "intro": {"emotion": "confident", "need_gesture": True, "preferred_tags": ["neutral", "gesture", "good_for_explain"]},
    "explain": {"emotion": "neutral", "need_gesture": False, "preferred_tags": ["neutral", "stable", "good_for_explain"]},
    "transition": {"emotion": "serious", "need_gesture": True, "preferred_tags": ["neutral", "gesture", "transition"]},
    "emphasis": {"emotion": "confident", "need_gesture": True, "preferred_tags": ["gesture", "emphasis", "good_for_explain"]},
    "outro": {"emotion": "confident", "need_gesture": True, "preferred_tags": ["neutral", "gesture", "closing"]},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build mock script segments from script.txt and narration.wav")
    parser.add_argument("--runtime-dir", required=True, help="Template Clip Bank runtime directory")
    parser.add_argument("--script-file", default="", help="Optional override for script.txt")
    parser.add_argument("--output", default="", help="Optional override for script_segments.json")
    parser.add_argument("--min-segment-duration", type=float, default=1.2, help="Minimum segment duration in seconds")
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


def _resolve_input_path(runtime_dir: Path, override: str, default_rel: str) -> Path:
    if override:
        raw = Path(override).expanduser()
        if raw.is_absolute():
            return raw.resolve()
        cwd_path = raw.resolve()
        if cwd_path.exists():
            return cwd_path
        return (runtime_dir / raw).resolve()
    return (runtime_dir / default_rel).resolve()


def _split_script(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    parts = re.split(r"[。！？；\n]+", normalized)
    return [part.strip() for part in parts if part.strip()]


def _infer_type(index: int, total: int, text: str) -> str:
    if index == 0:
        return "intro"
    if index == total - 1:
        return "outro"
    if any(keyword in text for keyword in TYPE_KEYWORDS["transition"]):
        return "transition"
    if any(keyword in text for keyword in TYPE_KEYWORDS["emphasis"]):
        return "emphasis"
    return "explain"


def _segment_char_weight(text: str) -> int:
    stripped = re.sub(r"\s+", "", text)
    return max(1, len(stripped))


def _distribute_durations(texts: list[str], audio_duration: float, min_segment_duration: float) -> list[float]:
    if not texts:
        return []
    weights = [_segment_char_weight(text) for text in texts]
    total_weight = sum(weights)
    base = [audio_duration * (weight / total_weight) for weight in weights]
    durations = [max(min_segment_duration, value) for value in base]
    total = sum(durations)
    if total <= 0:
        return [round(audio_duration / len(texts), 3)] * len(texts)

    scale = audio_duration / total
    durations = [duration * scale for duration in durations]
    durations = [round(duration, 3) for duration in durations]
    diff = round(audio_duration - sum(durations), 3)
    durations[-1] = round(max(min_segment_duration, durations[-1] + diff), 3)
    final_diff = round(audio_duration - sum(durations), 3)
    if abs(final_diff) > 0:
        durations[-1] = round(durations[-1] + final_diff, 3)
    return durations


def main() -> int:
    args = parse_args()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    input_dir = runtime_dir / "input"
    script_path = _resolve_input_path(runtime_dir, args.script_file, "input/script.txt")
    audio_path = (input_dir / "narration.wav").resolve()
    output_path = _resolve_input_path(runtime_dir, args.output, "input/script_segments.json")

    if args.min_segment_duration <= 0:
        raise SystemExit("min-segment-duration must be > 0")
    if not script_path.exists():
        raise SystemExit(f"input/script.txt not found. Create script.txt first or remove --build-script-segments.")
    if not audio_path.exists():
        raise SystemExit(f"Missing narration.wav: {audio_path}")

    script_text = script_path.read_text(encoding="utf-8").strip()
    if not script_text:
        raise SystemExit(f"script.txt is empty: {script_path}")

    audio_duration = _probe_duration(audio_path)
    parts = _split_script(script_text)
    if not parts:
        raise SystemExit("No valid script segments found after punctuation split.")

    warnings: list[str] = []
    if len(parts) * args.min_segment_duration > audio_duration:
        warnings.append(
            "min_segment_duration cannot be fully satisfied because script has too many segments for the narration duration."
        )

    durations = _distribute_durations(parts, audio_duration, args.min_segment_duration)

    segments: list[dict[str, Any]] = []
    for index, text in enumerate(parts):
        segment_type = _infer_type(index, len(parts), text)
        config = TYPE_CONFIG[segment_type]
        segments.append(
            {
                "segment_id": f"seg_{index + 1:03d}",
                "text": text,
                "duration": durations[index],
                "type": segment_type,
                "emotion": config["emotion"],
                "need_gesture": config["need_gesture"],
                "preferred_tags": list(config["preferred_tags"]),
            }
        )

    total_duration = round(sum(float(segment["duration"]) for segment in segments), 3)
    diff = round(audio_duration - total_duration, 3)
    if segments and abs(diff) > 0:
        segments[-1]["duration"] = round(max(args.min_segment_duration, float(segments[-1]["duration"]) + diff), 3)
        total_duration = round(sum(float(segment["duration"]) for segment in segments), 3)

    payload = {
        "source": "mock_rule",
        "script_path": "input/script.txt",
        "audio_path": "input/narration.wav",
        "audio_duration": round(audio_duration, 3),
        "total_duration": total_duration,
        "segments": segments,
        "warnings": warnings,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[DONE] segments={len(segments)}")
    print(f"[DONE] output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
