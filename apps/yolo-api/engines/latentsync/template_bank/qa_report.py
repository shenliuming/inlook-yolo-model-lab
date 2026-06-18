from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

EPSILON = 1e-9


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a QA report for prepared_template.mp4")
    parser.add_argument("--runtime-dir", required=True, help="Template Clip Bank runtime directory")
    return parser.parse_args()


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True)


def _probe_media(path: Path) -> dict[str, Any]:
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size:stream=index,codec_type,codec_name,avg_frame_rate,nb_frames,width,height,sample_rate,channels,duration",
            "-of",
            "json",
            str(path),
        ]
    )
    if result.returncode != 0:
        raise SystemExit(f"ffprobe failed for {path}: {(result.stderr or result.stdout).strip()}")
    return json.loads(result.stdout or "{}")


def _fps_from_rate(value: str) -> float | None:
    if not value or value == "0/0":
        return None
    if "/" in value:
        left, right = value.split("/", 1)
        try:
            denominator = float(right)
            if denominator == 0:
                return None
            return float(left) / denominator
        except ValueError:
            return None
    try:
        return float(value)
    except ValueError:
        return None


def _find_stream(payload: dict[str, Any], codec_type: str) -> dict[str, Any]:
    for stream in payload.get("streams") or []:
        if stream.get("codec_type") == codec_type:
            return stream
    return {}


def _load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _round_or_none(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _resolve_report_path(runtime_dir: Path, path_value: str | None) -> str:
    if not path_value:
        return ""
    raw = Path(path_value)
    if raw.is_absolute():
        return str(raw.resolve())
    return str((runtime_dir / raw).resolve())


def main() -> int:
    args = parse_args()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    input_dir = runtime_dir / "input"
    output_dir = runtime_dir / "output"
    reports_dir = runtime_dir / "reports"

    narration_audio = input_dir / "narration.wav"
    prepared_video = output_dir / "prepared_template.mp4"
    timeline_plan_json = reports_dir / "timeline_plan.json"
    prepare_report_json = reports_dir / "prepare_report.json"
    qa_report_json = reports_dir / "qa_report.json"

    if not prepared_video.exists():
        raise SystemExit(f"Prepared template not found: {prepared_video}")
    if not narration_audio.exists():
        raise SystemExit(f"Narration audio not found: {narration_audio}")

    reports_dir.mkdir(parents=True, exist_ok=True)

    video_probe = _probe_media(prepared_video)
    audio_probe = _probe_media(narration_audio)
    video_stream = _find_stream(video_probe, "video")
    audio_stream = _find_stream(audio_probe, "audio")

    video_duration = _as_float((video_probe.get("format") or {}).get("duration"))
    audio_duration = _as_float((audio_probe.get("format") or {}).get("duration"))
    fps = _fps_from_rate(str(video_stream.get("avg_frame_rate") or "0/0"))

    frame_count_raw = video_stream.get("nb_frames")
    frame_count = _as_int(frame_count_raw)
    if frame_count <= 0 and fps and fps > 0 and video_duration > 0:
        frame_count = int(round(video_duration * fps))

    duration_diff = abs(video_duration - audio_duration)
    frame_duration = (1.0 / fps) if fps and fps > 0 else None
    pass_duration_check = duration_diff <= (frame_duration + EPSILON) if frame_duration else False

    timeline_plan = _load_optional_json(timeline_plan_json)
    prepare_report = _load_optional_json(prepare_report_json)
    timeline_items = sorted(
        [item for item in (timeline_plan.get("timeline") or []) if isinstance(item, dict)],
        key=lambda item: _as_int(item.get("order")),
    )

    used_clip_ids = [str(item.get("clip_id") or "") for item in timeline_items if item.get("clip_id")]
    clip_id_counts = Counter(used_clip_ids)
    repeated_clip_ids = sorted([clip_id for clip_id, count in clip_id_counts.items() if count > 1])

    source_groups = [str(item.get("source_group") or "") for item in timeline_items if item.get("source_group")]
    source_group_counts = Counter(source_groups)
    repeated_source_groups = {group: count for group, count in source_group_counts.items() if count > 1}
    source_group_reuse_count = sum(repeated_source_groups.values())

    timeline_warnings = list(timeline_plan.get("warnings") or [])
    prepare_warnings = list(prepare_report.get("warnings") or [])
    warnings: list[str] = []

    if fps is None:
        warnings.append("Unable to read video fps.")
    if frame_duration is not None and duration_diff > (frame_duration + EPSILON):
        warnings.append("Video/audio duration difference exceeds one frame.")
    if repeated_clip_ids:
        warnings.append("Some clips are reused in timeline.")
    if source_group_reuse_count > 1:
        warnings.append("Timeline uses clips from repeated or highly similar source groups.")
    if frame_duration is not None and duration_diff > (frame_duration + EPSILON) and video_duration + EPSILON < audio_duration:
        warnings.append("Prepared template is shorter than narration.")

    payload = {
        "video": {
            "path": str(prepared_video),
            "duration": round(video_duration, 6),
            "fps": _round_or_none(fps, 6),
            "frame_count": frame_count,
            "width": _as_int(video_stream.get("width")),
            "height": _as_int(video_stream.get("height")),
            "codec_name": str(video_stream.get("codec_name") or ""),
            "file_size_mb": round(_as_float((video_probe.get("format") or {}).get("size")) / (1024 * 1024), 3),
        },
        "audio": {
            "path": str(narration_audio),
            "duration": round(audio_duration, 6),
            "sample_rate": _as_int(audio_stream.get("sample_rate")),
            "channels": _as_int(audio_stream.get("channels")),
            "codec_name": str(audio_stream.get("codec_name") or ""),
        },
        "checks": {
            "duration_diff": round(duration_diff, 6),
            "frame_duration": _round_or_none(frame_duration, 6),
            "pass_duration_check": pass_duration_check,
        },
        "timeline": {
            "timeline_total_duration": _round_or_none(_as_float(timeline_plan.get("total_timeline_duration")), 6)
            if timeline_plan
            else None,
            "timeline_item_count": len(timeline_items),
            "used_clip_count": len(used_clip_ids),
            "unique_used_clip_count": len(set(used_clip_ids)),
            "repeated_clip_ids": repeated_clip_ids,
            "source_group_reuse_count": source_group_reuse_count,
            "warnings_from_timeline": timeline_warnings,
        },
        "prepare": {
            "mode": str(prepare_report.get("mode") or ""),
            "encoder_used": str(prepare_report.get("encoder_used") or ""),
            "warnings_from_prepare": prepare_warnings,
        },
        "warnings": warnings,
    }

    if timeline_items:
        payload["timeline"]["used_clip_paths"] = [
            _resolve_report_path(runtime_dir, str(item.get("path") or "")) for item in timeline_items
        ]

    qa_report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[DONE] qa={qa_report_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
