from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a manual timeline plan from selected template clips")
    parser.add_argument("--runtime-dir", required=True, help="Template Clip Bank runtime directory")
    parser.add_argument("--min-source-gap-seconds", type=float, default=8.0, help="Preferred minimum gap between consecutive source_start values")
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
    raise SystemExit(f"Unsupported candidates json structure: {path}")


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


def _candidate_duration(candidate: dict[str, Any]) -> float:
    duration = candidate.get("duration")
    if duration is not None:
        try:
            parsed = float(duration)
            if parsed > 0:
                return parsed
        except (TypeError, ValueError):
            pass
    start = candidate.get("start")
    end = candidate.get("end")
    try:
        parsed = float(end) - float(start)
        if parsed > 0:
            return parsed
    except (TypeError, ValueError):
        pass
    raise SystemExit(f"Candidate missing valid duration: {candidate.get('clip_id')}")


def _build_candidate_map(candidates: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, candidate in enumerate(candidates, start=1):
        clip_id = str(candidate.get("clip_id") or f"clip_{index:03d}")
        result[clip_id] = {
            **candidate,
            "clip_id": clip_id,
            "duration": _candidate_duration(candidate),
            "source_group": str(candidate.get("source_group") or ""),
            "source_start": float(candidate.get("start") or 0.0),
            "source_end": float(candidate.get("end") or 0.0),
            "path": str(candidate.get("path") or ""),
            "tags": list(candidate.get("tags") or []),
            "content_hint": str(candidate.get("content_hint") or ""),
            "motion_hint": str(candidate.get("motion_hint") or ""),
            "manual_note": str(candidate.get("manual_note") or ""),
            "usable": candidate.get("usable", True) is not False,
        }
    return result


def _tag_profile(selected_ids: list[str], candidate_map: dict[str, dict[str, Any]]) -> Counter[str]:
    profile: Counter[str] = Counter()
    for clip_id in selected_ids:
        candidate = candidate_map.get(clip_id, {})
        for tag in candidate.get("tags") or []:
            if tag:
                profile[str(tag)] += 1
    return profile


def _candidate_ok(
    candidate: dict[str, Any],
    *,
    last_clip_id: str,
    last_group: str,
    last_source_start: float | None,
    min_source_gap_seconds: float,
) -> tuple[bool, bool]:
    if candidate.get("usable") is False:
        return False, False
    if candidate["clip_id"] == last_clip_id:
        return False, False
    group_ok = not last_group or candidate.get("source_group") != last_group
    gap_ok = last_source_start is None or abs(float(candidate.get("source_start") or 0.0) - last_source_start) >= min_source_gap_seconds
    return group_ok and gap_ok, group_ok


def _fallback_sort_key(
    candidate: dict[str, Any],
    *,
    selected_tag_profile: Counter[str],
    last_source_start: float | None,
    min_source_gap_seconds: float,
) -> tuple[float, float, float, str]:
    source_start = float(candidate.get("source_start") or 0.0)
    if last_source_start is None:
        forward_penalty = 0.0
        gap_excess = 0.0
    else:
        forward_penalty = 0.0 if source_start >= last_source_start else 1.0
        gap = abs(source_start - last_source_start)
        gap_excess = abs(gap - min_source_gap_seconds)
    tag_score = -sum(selected_tag_profile.get(str(tag), 0) for tag in candidate.get("tags") or [])
    return (forward_penalty, gap_excess, tag_score, candidate["clip_id"])


def _pick_from_all_candidates(
    candidate_map: dict[str, dict[str, Any]],
    *,
    selected_tag_profile: Counter[str],
    last_clip_id: str,
    last_group: str,
    last_source_start: float | None,
    min_source_gap_seconds: float,
    require_group_ok: bool,
    require_gap_ok: bool,
) -> dict[str, Any] | None:
    pool: list[dict[str, Any]] = []
    for candidate in candidate_map.values():
        if candidate.get("usable") is False:
            continue
        if candidate["clip_id"] == last_clip_id:
            continue
        group_ok = not last_group or candidate.get("source_group") != last_group
        gap_ok = last_source_start is None or abs(float(candidate.get("source_start") or 0.0) - last_source_start) >= min_source_gap_seconds
        if require_group_ok and not group_ok:
            continue
        if require_gap_ok and not gap_ok:
            continue
        pool.append(candidate)
    if not pool:
        return None
    pool.sort(
        key=lambda candidate: _fallback_sort_key(
            candidate,
            selected_tag_profile=selected_tag_profile,
            last_source_start=last_source_start,
            min_source_gap_seconds=min_source_gap_seconds,
        )
    )
    return pool[0]


def _pick_next_candidate(
    selected_ids: list[str],
    candidate_map: dict[str, dict[str, Any]],
    cursor: int,
    *,
    selected_tag_profile: Counter[str],
    last_clip_id: str,
    last_group: str,
    last_source_start: float | None,
    min_source_gap_seconds: float,
) -> tuple[dict[str, Any], int, str | None]:
    if len(selected_ids) == 1:
        return candidate_map[selected_ids[0]], cursor + 1, None

    ordered = [selected_ids[(cursor + offset) % len(selected_ids)] for offset in range(len(selected_ids))]

    for candidate_id in ordered:
        candidate = candidate_map[candidate_id]
        if candidate.get("usable") is False:
            continue
        accepted, _group_ok = _candidate_ok(
            candidate,
            last_clip_id=last_clip_id,
            last_group=last_group,
            last_source_start=last_source_start,
            min_source_gap_seconds=min_source_gap_seconds,
        )
        if accepted:
            next_cursor = selected_ids.index(candidate_id) + 1
            return candidate, next_cursor, None

    alternate = _pick_from_all_candidates(
        candidate_map,
        selected_tag_profile=selected_tag_profile,
        last_clip_id=last_clip_id,
        last_group=last_group,
        last_source_start=last_source_start,
        min_source_gap_seconds=min_source_gap_seconds,
        require_group_ok=True,
        require_gap_ok=True,
    )
    if alternate is not None:
        return (
            alternate,
            cursor,
            "selected clips were too similar, so an alternate usable clip was chosen to improve source diversity.",
        )

    for candidate_id in ordered:
        candidate = candidate_map[candidate_id]
        if candidate.get("usable") is False:
            continue
        if candidate["clip_id"] == last_clip_id:
            continue
        if not last_group or candidate.get("source_group") != last_group:
            next_cursor = selected_ids.index(candidate_id) + 1
            return candidate, next_cursor, "source_start gap rule could not be satisfied, so a closer clip was used."

    alternate = _pick_from_all_candidates(
        candidate_map,
        selected_tag_profile=selected_tag_profile,
        last_clip_id=last_clip_id,
        last_group=last_group,
        last_source_start=last_source_start,
        min_source_gap_seconds=min_source_gap_seconds,
        require_group_ok=True,
        require_gap_ok=False,
    )
    if alternate is not None:
        return (
            alternate,
            cursor,
            "selected clips could not satisfy spacing, so an alternate usable clip from a different source group was chosen.",
        )

    for candidate_id in ordered:
        candidate = candidate_map[candidate_id]
        if candidate.get("usable") is False:
            continue
        if candidate["clip_id"] != last_clip_id:
            next_cursor = selected_ids.index(candidate_id) + 1
            return candidate, next_cursor, "source_group and source_start gap rules could not be satisfied, so a similar clip was used."

    alternate = _pick_from_all_candidates(
        candidate_map,
        selected_tag_profile=selected_tag_profile,
        last_clip_id=last_clip_id,
        last_group=last_group,
        last_source_start=last_source_start,
        min_source_gap_seconds=min_source_gap_seconds,
        require_group_ok=False,
        require_gap_ok=False,
    )
    if alternate is not None:
        return (
            alternate,
            cursor,
            "selected clips were exhausted, so an alternate usable clip was chosen as a last-resort fallback.",
        )

    for candidate_id in ordered:
        candidate = candidate_map[candidate_id]
        if candidate.get("usable") is not False:
            return candidate, cursor + 1, "Only one usable clip pattern was available, so all spacing rules were skipped."

    raise SystemExit("No usable clips remain after applying usable=false filtering.")


def _build_timeline(
    selected_ids: list[str],
    candidate_map: dict[str, dict[str, Any]],
    target_audio_duration: float,
    min_source_gap_seconds: float,
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    selected_tag_profile = _tag_profile(selected_ids, candidate_map)
    if len(selected_ids) == 1:
        warnings.append("Only one selected clip is available; repeated usage is allowed for MVP.")

    timeline: list[dict[str, Any]] = []
    total = 0.0
    cursor = 0
    last_clip_id = ""
    last_group = ""
    last_source_start: float | None = None
    order = 1

    while total < target_audio_duration:
        candidate, cursor, warning = _pick_next_candidate(
            selected_ids,
            candidate_map,
            cursor,
            selected_tag_profile=selected_tag_profile,
            last_clip_id=last_clip_id,
            last_group=last_group,
            last_source_start=last_source_start,
            min_source_gap_seconds=min_source_gap_seconds,
        )
        if warning:
            warnings.append(
                f"order {order}: {warning} clip_id={candidate['clip_id']} source_group={candidate.get('source_group') or ''}"
            )
        clip_duration = float(candidate["duration"])
        remaining = max(0.0, target_audio_duration - total)
        used_duration = min(clip_duration, remaining)
        start_time = total
        end_time = total + used_duration
        if used_duration < clip_duration:
            reason = "trimmed to match audio duration"
        elif warning and "alternate usable clip" in warning:
            reason = "alternate usable clip chosen for source diversity"
        else:
            reason = "manual selected"
        timeline.append(
            {
                "order": order,
                "clip_id": candidate["clip_id"],
                "source_group": candidate.get("source_group") or "",
                "source_start": round(float(candidate.get("source_start") or 0.0), 3),
                "source_end": round(float(candidate.get("source_end") or 0.0), 3),
                "start_time": round(start_time, 3),
                "end_time": round(end_time, 3),
                "duration": round(clip_duration, 3),
                "used_duration": round(used_duration, 3),
                "path": str(candidate.get("path") or ""),
                "tags": list(candidate.get("tags") or []),
                "content_hint": str(candidate.get("content_hint") or ""),
                "motion_hint": str(candidate.get("motion_hint") or ""),
                "manual_note": str(candidate.get("manual_note") or ""),
                "reason": reason,
            }
        )
        total = end_time
        last_clip_id = candidate["clip_id"]
        last_group = str(candidate.get("source_group") or "")
        last_source_start = float(candidate.get("source_start") or 0.0)
        order += 1

    return timeline, warnings


def main() -> int:
    args = parse_args()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    input_dir = runtime_dir / "input"
    reports_dir = runtime_dir / "reports"

    selected_json = input_dir / "selected_clips.json"
    candidates_json = reports_dir / "candidates_enriched.json"
    narration_audio = input_dir / "narration.wav"
    output_json = reports_dir / "timeline_plan.json"

    for path in (selected_json, candidates_json, narration_audio):
        if not path.exists():
            raise SystemExit(f"Missing required input: {path}")

    target_audio_duration = _probe_duration(narration_audio)
    selected_ids = _load_selected_clip_ids(selected_json)
    candidate_map = _build_candidate_map(_load_candidates(candidates_json))

    missing_ids = [clip_id for clip_id in selected_ids if clip_id not in candidate_map]
    if missing_ids:
        raise SystemExit(f"Selected clip ids not found in candidates_enriched.json: {', '.join(missing_ids)}")

    usable_selected_ids = [clip_id for clip_id in selected_ids if candidate_map[clip_id].get("usable") is not False]
    if not usable_selected_ids:
        raise SystemExit("No usable clips remain after filtering selected_clips.json against candidates_enriched.json.")
    skipped_unusable_ids = [clip_id for clip_id in selected_ids if clip_id not in usable_selected_ids]

    timeline, warnings = _build_timeline(
        usable_selected_ids,
        candidate_map,
        target_audio_duration,
        args.min_source_gap_seconds,
    )
    if skipped_unusable_ids:
        warnings.insert(
            0,
            "Skipped clips marked unusable: " + ", ".join(skipped_unusable_ids),
        )

    payload = {
        "target_audio_duration": round(target_audio_duration, 3),
        "total_timeline_duration": round(sum(item["used_duration"] for item in timeline), 3),
        "min_source_gap_seconds": args.min_source_gap_seconds,
        "timeline": timeline,
        "warnings": warnings,
    }
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[DONE] timeline={output_json}")
    print(f"[DONE] items={len(timeline)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
