from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

EPSILON = 1e-9


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import a LatentSync result back into Template Clip Bank runtime")
    parser.add_argument("--runtime-dir", required=True, help="Template Clip Bank runtime directory")
    parser.add_argument("--job-dir", required=True, help="Exported LatentSync job directory")
    parser.add_argument("--result-video", required=True, help="LatentSync output video to import")
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


def _find_stream(payload: dict[str, Any], codec_type: str) -> dict[str, Any]:
    for stream in payload.get("streams") or []:
        if stream.get("codec_type") == codec_type:
            return stream
    return {}


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


def _load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


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


def _round_or_none(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def _relative_to_runtime(runtime_dir: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(runtime_dir.resolve()))
    except ValueError:
        return str(path.resolve())


def main() -> int:
    args = parse_args()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    job_dir = Path(args.job_dir).expanduser().resolve()
    result_video = Path(args.result_video).expanduser().resolve()

    input_dir = runtime_dir / "input"
    final_dir = runtime_dir / "final"
    reports_dir = runtime_dir / "reports"

    narration_audio = input_dir / "narration.wav"
    job_config_path = job_dir / "job_config.json"
    manifest_path = job_dir / "manifest.json"
    template_qa_path = job_dir / "reports" / "template_qa_report.json"
    final_video_path = final_dir / "final_latentsync_output.mp4"
    final_qa_path = reports_dir / "final_qa_report.json"
    final_report_path = final_dir / "final_report.json"

    if not result_video.exists():
        raise SystemExit(f"LatentSync result video not found: {result_video}")
    if not job_dir.exists():
        raise SystemExit(f"LatentSync job directory not found: {job_dir}")
    if not job_config_path.exists():
        raise SystemExit(f"Missing job_config.json: {job_config_path}")
    if not manifest_path.exists():
        raise SystemExit(f"Missing manifest.json: {manifest_path}")
    if not narration_audio.exists():
        raise SystemExit(f"Narration audio not found: {narration_audio}")

    final_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(result_video, final_video_path)

    job_config = _load_optional_json(job_config_path)
    manifest = _load_optional_json(manifest_path)
    template_qa = _load_optional_json(template_qa_path)

    video_probe = _probe_media(final_video_path)
    audio_probe = _probe_media(narration_audio)
    video_stream = _find_stream(video_probe, "video")
    audio_stream = _find_stream(audio_probe, "audio")

    video_duration = _as_float((video_probe.get("format") or {}).get("duration"))
    audio_duration = _as_float((audio_probe.get("format") or {}).get("duration"))
    fps = _fps_from_rate(str(video_stream.get("avg_frame_rate") or "0/0"))

    frame_count = _as_int(video_stream.get("nb_frames"))
    if frame_count <= 0 and fps and fps > 0 and video_duration > 0:
        frame_count = int(round(video_duration * fps))

    duration_diff = abs(video_duration - audio_duration)
    frame_duration = (1.0 / fps) if fps and fps > 0 else None
    pass_duration_check = duration_diff <= (frame_duration + EPSILON) if frame_duration else False

    qa_warnings: list[str] = []
    if fps is None:
        qa_warnings.append("Unable to read final video fps.")
    if frame_duration is not None and duration_diff > (frame_duration + EPSILON):
        qa_warnings.append("Final video/audio duration difference exceeds one frame.")
    if frame_duration is not None and duration_diff > (frame_duration + EPSILON) and video_duration + EPSILON < audio_duration:
        qa_warnings.append("Final LatentSync output is shorter than narration.")

    final_qa_payload = {
        "video": {
            "path": _relative_to_runtime(runtime_dir, final_video_path),
            "duration": round(video_duration, 6),
            "fps": _round_or_none(fps, 6),
            "frame_count": frame_count,
            "width": _as_int(video_stream.get("width")),
            "height": _as_int(video_stream.get("height")),
            "codec_name": str(video_stream.get("codec_name") or ""),
            "file_size_mb": round(_as_float((video_probe.get("format") or {}).get("size")) / (1024 * 1024), 3),
        },
        "audio": {
            "path": _relative_to_runtime(runtime_dir, narration_audio),
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
        "job": {
            "job_id": str(job_config.get("job_id") or job_dir.name),
            "engine": str(job_config.get("engine") or ""),
            "engine_version": str(job_config.get("engine_version") or ""),
        },
        "warnings": qa_warnings,
    }
    final_qa_path.write_text(json.dumps(final_qa_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    template_warnings = list(template_qa.get("warnings") or [])
    final_report_warnings = list(qa_warnings)
    final_report_payload = {
        "status": "imported",
        "job_id": str(job_config.get("job_id") or job_dir.name),
        "engine": str(job_config.get("engine") or ""),
        "engine_version": str(job_config.get("engine_version") or ""),
        "input_job_dir": _relative_to_runtime(runtime_dir, job_dir),
        "final_video": _relative_to_runtime(runtime_dir, final_video_path),
        "final_qa_report": _relative_to_runtime(runtime_dir, final_qa_path),
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "manifest_status": str(manifest.get("status") or ""),
        "template_warnings": template_warnings,
        "warnings": final_report_warnings,
    }
    final_report_path.write_text(json.dumps(final_report_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[DONE] final_video={final_video_path}")
    print(f"[DONE] final_qa={final_qa_path}")
    print(f"[DONE] final_report={final_report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
