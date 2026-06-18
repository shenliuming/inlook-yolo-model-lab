from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a prepared template video from manually selected candidate clips")
    parser.add_argument("--runtime-dir", required=True, help="Template Clip Bank runtime directory")
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


def _load_candidates(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("clips", "candidates"):
            items = payload.get(key)
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
    raise SystemExit(f"Unsupported candidates.json structure: {path}")


def _load_primary_candidates(reports_dir: Path) -> tuple[Path, list[dict[str, Any]]]:
    for candidate_path in (reports_dir / "candidates_enriched.json", reports_dir / "candidates.json"):
        if candidate_path.exists():
            return candidate_path, _load_candidates(candidate_path)
    raise SystemExit(f"Missing candidates source in {reports_dir}")


def _candidate_clip_path(
    candidate: dict[str, Any],
    runtime_dir: Path,
    candidates_dir: Path,
    fallback_index: int,
) -> Path:
    for key in ("clip_path", "path", "file", "filename"):
        value = candidate.get(key)
        if not value:
            continue
        raw_path = Path(str(value))
        if raw_path.is_absolute():
            return raw_path.resolve()
        runtime_path = runtime_dir / raw_path
        if runtime_path.exists():
            return runtime_path.resolve()
        candidate_path = candidates_dir / raw_path.name
        if candidate_path.exists():
            return candidate_path.resolve()
        clip_id = str(candidate.get("clip_id") or f"clip_{fallback_index:03d}")
        fallback = candidates_dir / f"{clip_id}.mp4"
        return fallback.resolve()
    clip_id = str(candidate.get("clip_id") or f"clip_{fallback_index:03d}")
    return (candidates_dir / f"{clip_id}.mp4").resolve()


def _load_selected_clip_ids(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    selected = payload.get("selected")
    if not isinstance(selected, list):
        raise SystemExit(f"selected_clips.json missing selected list: {path}")
    clip_ids: list[str] = []
    for item in selected:
        if isinstance(item, str):
            clip_ids.append(item)
        elif isinstance(item, dict) and item.get("clip_id"):
            clip_ids.append(str(item["clip_id"]))
    clip_ids = [clip_id for clip_id in clip_ids if clip_id]
    if not clip_ids:
        raise SystemExit(f"No usable selected clips found in: {path}")
    return clip_ids


def _load_timeline_plan(path: Path) -> tuple[list[dict[str, Any]], list[str], float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    timeline = payload.get("timeline")
    if not isinstance(timeline, list) or not timeline:
        raise SystemExit(f"timeline_plan.json missing timeline list: {path}")
    warnings = [str(item) for item in (payload.get("warnings") or [])]
    total_duration = float(payload.get("total_timeline_duration") or 0.0)
    items = [item for item in timeline if isinstance(item, dict)]
    items.sort(key=lambda item: int(item.get("order") or 0))
    return items, warnings, total_duration


def _candidate_duration(candidate: dict[str, Any], clip_path: Path) -> float:
    start = candidate.get("start")
    end = candidate.get("end")
    try:
        if start is not None and end is not None:
            duration = float(end) - float(start)
            if duration > 0:
                return duration
    except (TypeError, ValueError):
        pass
    return _probe_duration(clip_path)


def _build_timeline(
    selected_ids: list[str],
    candidate_map: dict[str, dict[str, Any]],
    target_duration: float,
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    if len(selected_ids) == 1:
        warnings.append("Only one selected clip was provided, so repetition was allowed.")

    timeline: list[dict[str, Any]] = []
    total_duration = 0.0
    cursor = 0
    last_clip_id = ""
    order = 1

    while total_duration < target_duration:
        candidate_id = selected_ids[cursor % len(selected_ids)]
        cursor += 1

        if len(selected_ids) > 1 and candidate_id == last_clip_id:
            continue

        candidate = candidate_map[candidate_id]
        clip_duration = float(candidate["clip_duration"])
        remaining = max(0.0, target_duration - total_duration)
        used_duration = min(clip_duration, remaining)

        timeline.append(
            {
                "order": order,
                "clip_id": candidate_id,
                "source_start": candidate.get("start"),
                "source_end": candidate.get("end"),
                "used_duration": round(used_duration, 3),
                "path": candidate["resolved_path"],
            }
        )
        total_duration += used_duration
        last_clip_id = candidate_id
        order += 1

    return timeline, warnings


def _resolve_timeline_plan(
    runtime_dir: Path,
    timeline_items: list[dict[str, Any]],
    candidate_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for item in timeline_items:
        clip_id = str(item.get("clip_id") or "")
        if clip_id not in candidate_map:
            raise SystemExit(f"Timeline clip id not found in candidates: {clip_id}")
        candidate = candidate_map[clip_id]
        raw_path = Path(str(item.get("path") or candidate["resolved_path"]))
        if raw_path.is_absolute():
            resolved_path = raw_path.resolve()
        else:
            resolved_path = (runtime_dir / raw_path).resolve()
        resolved.append(
            {
                "order": int(item.get("order") or len(resolved) + 1),
                "clip_id": clip_id,
                "source_group": item.get("source_group") or candidate.get("source_group") or "",
                "source_start": item.get("source_start"),
                "source_end": item.get("source_end"),
                "used_duration": round(float(item.get("used_duration") or candidate["clip_duration"]), 3),
                "path": str(resolved_path),
                "reason": str(item.get("reason") or "manual selected"),
            }
        )
    return resolved


def _concat_escape(path: Path) -> str:
    return str(path).replace("'", r"'\''")


def _write_concat_file(timeline: list[dict[str, Any]], path: Path) -> None:
    lines: list[str] = []
    for item in timeline:
        clip_path = Path(item["path"])
        lines.append(f"file '{_concat_escape(clip_path)}'")
        lines.append("inpoint 0")
        lines.append(f"outpoint {float(item['used_duration']):.3f}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _render_with_encoder(concat_file: Path, output_path: Path, target_duration: float, encoder: str) -> subprocess.CompletedProcess[str]:
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-t",
        f"{target_duration:.3f}",
        "-an",
        "-c:v",
        encoder,
    ]
    if encoder == "libx264":
        command += ["-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "18"]
    else:
        command += ["-q:v", "4"]
    command.append(str(output_path))
    return _run(command)


def main() -> int:
    args = parse_args()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    reports_dir = runtime_dir / "reports"
    input_dir = runtime_dir / "input"
    candidates_dir = runtime_dir / "candidates"
    output_dir = runtime_dir / "output"
    temp_dir = runtime_dir / "tmp"

    candidates_json = reports_dir / "candidates.json"
    timeline_plan_json = reports_dir / "timeline_plan.json"
    selected_json = input_dir / "selected_clips.json"
    narration_audio = input_dir / "narration.wav"
    output_video = output_dir / "prepared_template.mp4"
    report_path = reports_dir / "prepare_report.json"
    concat_file = temp_dir / "prepared_concat.txt"

    for path in (narration_audio, candidates_dir):
        if not path.exists():
            raise SystemExit(f"Missing required input: {path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    target_audio_duration = _probe_duration(narration_audio)
    _candidates_source_path, candidates = _load_primary_candidates(reports_dir)

    candidate_map: dict[str, dict[str, Any]] = {}
    for index, candidate in enumerate(candidates, start=1):
        clip_id = str(candidate.get("clip_id") or f"clip_{index:03d}")
        clip_path = _candidate_clip_path(candidate, runtime_dir, candidates_dir, index)
        candidate_map[clip_id] = {
            **candidate,
            "clip_id": clip_id,
            "resolved_path": str(clip_path),
            "clip_duration": _candidate_duration(candidate, clip_path),
        }

    selected_clip_count: int
    mode: str
    if timeline_plan_json.exists():
        timeline_items, warnings, _plan_duration = _load_timeline_plan(timeline_plan_json)
        timeline = _resolve_timeline_plan(runtime_dir, timeline_items, candidate_map)
        selected_clip_count = len({item["clip_id"] for item in timeline})
        mode = "timeline_plan"
    else:
        if not selected_json.exists():
            raise SystemExit(f"Missing required input: {selected_json}")
        selected_ids = _load_selected_clip_ids(selected_json)
        missing_ids = [clip_id for clip_id in selected_ids if clip_id not in candidate_map]
        if missing_ids:
            raise SystemExit(f"Selected clip ids not found in candidates.json: {', '.join(missing_ids)}")
        timeline, warnings = _build_timeline(selected_ids, candidate_map, target_audio_duration)
        selected_clip_count = len(selected_ids)
        mode = "selected_clips_fallback"

    _write_concat_file(timeline, concat_file)

    encoder_used = "libx264"
    result = _render_with_encoder(concat_file, output_video, target_audio_duration, encoder_used)
    if result.returncode != 0:
        encoder_used = "mpeg4"
        warnings.append("libx264 encode failed, fell back to mpeg4.")
        result = _render_with_encoder(concat_file, output_video, target_audio_duration, encoder_used)
    if result.returncode != 0 or not output_video.exists():
        message = (result.stderr or result.stdout).strip()
        raise SystemExit(f"Failed to render prepared template: {message}")

    prepared_video_duration = _probe_duration(output_video)
    report = {
        "mode": mode,
        "target_audio_duration": round(target_audio_duration, 3),
        "prepared_video_duration": round(prepared_video_duration, 3),
        "timeline_item_count": len(timeline),
        "used_clip_count": len(timeline),
        "selected_clip_count": selected_clip_count,
        "encoder_used": encoder_used,
        "timeline": [
            {
                "order": item["order"],
                "clip_id": item["clip_id"],
                "source_group": item.get("source_group") or "",
                "source_start": item["source_start"],
                "source_end": item["source_end"],
                "used_duration": item["used_duration"],
                "reason": item.get("reason") or ("manual selected" if mode == "timeline_plan" else "selected clips fallback"),
            }
            for item in timeline
        ],
        "warnings": warnings,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[DONE] output={output_video}")
    print(f"[DONE] report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
