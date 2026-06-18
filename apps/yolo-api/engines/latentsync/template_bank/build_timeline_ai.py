from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


TYPE_TAG_BONUS = {
    "intro": {"intro", "opening", "gesture", "good_for_explain"},
    "explain": {"explain", "good_for_explain", "neutral", "stable"},
    "transition": {"transition", "neutral"},
    "emphasis": {"emphasis", "gesture"},
    "outro": {"outro", "closing", "neutral"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an AI-scored timeline plan from candidate clips")
    parser.add_argument("--runtime-dir", required=True, help="Template Clip Bank runtime directory")
    parser.add_argument("--script-segments", default="", help="Optional override for script_segments.json")
    parser.add_argument("--min-source-gap-seconds", type=float, default=8.0, help="Preferred minimum gap between consecutive source_start values")
    parser.add_argument("--max-reuse-per-clip", type=int, default=2, help="Maximum reuse count per clip")
    parser.add_argument("--max-reuse-per-source-group", type=int, default=2, help="Maximum reuse count per source group")
    parser.add_argument("--min-overall-score", type=float, default=60.0, help="Minimum fallback overall score")
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


def _load_segments(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    segments = payload.get("segments")
    if not isinstance(segments, list):
        raise SystemExit(f"script_segments.json missing segments list: {path}")
    return [item for item in segments if isinstance(item, dict)]


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
        ai_score = candidate.get("ai_score") if isinstance(candidate.get("ai_score"), dict) else {}
        result[clip_id] = {
            **candidate,
            "clip_id": clip_id,
            "duration": _candidate_duration(candidate),
            "source_group": str(candidate.get("source_group") or ""),
            "source_start": float(candidate.get("start") or 0.0),
            "source_end": float(candidate.get("end") or 0.0),
            "path": str(candidate.get("path") or ""),
            "tags": [str(tag) for tag in (candidate.get("tags") or []) if tag],
            "content_hint": str(candidate.get("content_hint") or ""),
            "motion_hint": str(candidate.get("motion_hint") or ""),
            "manual_note": str(candidate.get("manual_note") or ""),
            "usable": candidate.get("usable", True) is not False,
            "ai_score": {
                "provider": str(ai_score.get("provider") or ""),
                "overall_score": float(ai_score.get("overall_score") or 0.0),
                "recommended": bool(ai_score.get("recommended")),
                "recommended_tags": [str(tag) for tag in (ai_score.get("recommended_tags") or []) if tag],
                "risk_tags": [str(tag) for tag in (ai_score.get("risk_tags") or []) if tag],
                "mouth_occlusion_risk": float(ai_score.get("mouth_occlusion_risk") or 0.0),
                "motion_risk": float(ai_score.get("motion_risk") or 0.0),
                **ai_score,
            },
        }
    return result


def _candidate_sort_key(candidate: dict[str, Any]) -> tuple[float, float, float, str]:
    ai_score = candidate.get("ai_score") or {}
    recommended_rank = 0 if ai_score.get("recommended") else 1
    overall_score = -float(ai_score.get("overall_score") or 0.0)
    reuse_value = -float(ai_score.get("reuse_value_score") or 0.0)
    return (recommended_rank, overall_score, reuse_value, candidate["clip_id"])


def _dynamic_pick_sort_key(
    candidate: dict[str, Any],
    *,
    clip_usage: Counter[str],
    group_usage: Counter[str],
    last_source_start: float | None,
    min_source_gap_seconds: float,
) -> tuple[float, float, float, float, float, str]:
    ai_score = candidate.get("ai_score") or {}
    source_group = str(candidate.get("source_group") or "")
    source_start = float(candidate.get("source_start") or 0.0)
    clip_used = clip_usage[candidate["clip_id"]]
    group_used = group_usage[source_group] if source_group else 0
    if last_source_start is None:
        forward_penalty = 0.0
        gap_penalty = 0.0
    else:
        forward_penalty = 0.0 if source_start >= last_source_start else 1.0
        gap_penalty = abs(abs(source_start - last_source_start) - min_source_gap_seconds)
    return (
        clip_used,
        group_used,
        forward_penalty,
        gap_penalty,
        -float(ai_score.get("overall_score") or 0.0),
        candidate["clip_id"],
    )


def _fits_limits(
    candidate: dict[str, Any],
    *,
    clip_usage: Counter[str],
    group_usage: Counter[str],
    max_reuse_per_clip: int,
    max_reuse_per_source_group: int,
    allow_limit_fallback: bool,
) -> bool:
    if allow_limit_fallback:
        return True
    if clip_usage[candidate["clip_id"]] >= max_reuse_per_clip:
        return False
    source_group = str(candidate.get("source_group") or "")
    if source_group and group_usage[source_group] >= max_reuse_per_source_group:
        return False
    return True


def _dedupe_warning_append(warnings: list[str], new_warnings: list[str]) -> None:
    seen = set(warnings)
    for warning in new_warnings:
        if warning not in seen:
            warnings.append(warning)
            seen.add(warning)


def _segment_duration(segment: dict[str, Any], default: float) -> float:
    try:
        value = float(segment.get("duration") or 0.0)
        if value > 0:
            return value
    except (TypeError, ValueError):
        pass
    return default


def _resolve_script_segments_path(runtime_dir: Path, override: str) -> Path | None:
    if override:
        raw = Path(override).expanduser()
        if raw.is_absolute():
            return raw.resolve()
        cwd_path = raw.resolve()
        if cwd_path.exists():
            return cwd_path
        runtime_path = (runtime_dir / raw).resolve()
        return runtime_path
    default = runtime_dir / "input" / "script_segments.json"
    return default.resolve() if default.exists() else None


def _pick_candidate(
    pools: list[tuple[str, list[dict[str, Any]]]],
    *,
    last_clip_id: str,
    last_group: str,
    last_source_start: float | None,
    min_source_gap_seconds: float,
    clip_usage: Counter[str],
    group_usage: Counter[str],
    max_reuse_per_clip: int,
    max_reuse_per_source_group: int,
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    limit_fallback_used = False

    for pool_index, (_pool_name, pool) in enumerate(pools):
        if not pool:
            continue
        if pool_index == 1:
            warnings.append("Not enough recommended clips; fallback to clips with overall_score >= 60.")
        elif pool_index == 2:
            warnings.append("Not enough high-score clips; fallback to all usable clips.")

        for allow_limit_fallback in (False, True):
            if allow_limit_fallback and not limit_fallback_used:
                warnings.append("Clip reuse limit was reached; fallback reuse allowed for MVP.")
                limit_fallback_used = True

            exact_matches: list[dict[str, Any]] = []
            group_matches: list[dict[str, Any]] = []
            basic_matches: list[dict[str, Any]] = []

            for candidate in pool:
                if candidate["clip_id"] == last_clip_id:
                    continue
                if not _fits_limits(
                    candidate,
                    clip_usage=clip_usage,
                    group_usage=group_usage,
                    max_reuse_per_clip=max_reuse_per_clip,
                    max_reuse_per_source_group=max_reuse_per_source_group,
                    allow_limit_fallback=allow_limit_fallback,
                ):
                    continue
                source_group = str(candidate.get("source_group") or "")
                source_start = float(candidate.get("source_start") or 0.0)
                group_ok = not last_group or source_group != last_group
                gap_ok = last_source_start is None or abs(source_start - last_source_start) >= min_source_gap_seconds
                if group_ok and gap_ok:
                    exact_matches.append(candidate)
                elif group_ok:
                    group_matches.append(candidate)
                else:
                    basic_matches.append(candidate)

            sort_key = lambda candidate: _dynamic_pick_sort_key(
                candidate,
                clip_usage=clip_usage,
                group_usage=group_usage,
                last_source_start=last_source_start,
                min_source_gap_seconds=min_source_gap_seconds,
            )
            exact_matches.sort(key=sort_key)
            group_matches.sort(key=sort_key)
            basic_matches.sort(key=sort_key)

            if exact_matches:
                return exact_matches[0], warnings
            if group_matches:
                warnings.append("Source group gap rule could not be fully satisfied.")
                return group_matches[0], warnings
            if basic_matches:
                warnings.append("Source group gap rule could not be fully satisfied.")
                return basic_matches[0], warnings

    raise SystemExit("No usable AI-scored clips remain to build timeline.")


def _build_score_only_timeline(
    candidate_map: dict[str, dict[str, Any]],
    *,
    target_audio_duration: float,
    min_source_gap_seconds: float,
    max_reuse_per_clip: int,
    max_reuse_per_source_group: int,
    min_overall_score: float,
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    usable_candidates = [candidate for candidate in candidate_map.values() if candidate.get("usable") is not False]
    if not usable_candidates:
        raise SystemExit("No usable clips remain after applying usable=false filtering.")

    usable_candidates.sort(key=_candidate_sort_key)
    recommended_pool = [c for c in usable_candidates if bool((c.get("ai_score") or {}).get("recommended"))]
    high_score_pool = [c for c in usable_candidates if float((c.get("ai_score") or {}).get("overall_score") or 0.0) >= min_overall_score]
    all_usable_pool = list(usable_candidates)

    clip_usage: Counter[str] = Counter()
    group_usage: Counter[str] = Counter()
    timeline: list[dict[str, Any]] = []
    total = 0.0
    last_clip_id = ""
    last_group = ""
    last_source_start: float | None = None
    order = 1

    while total < target_audio_duration:
        candidate, pick_warnings = _pick_candidate(
            [
                ("recommended", recommended_pool),
                ("high_score", high_score_pool),
                ("usable", all_usable_pool),
            ],
            last_clip_id=last_clip_id,
            last_group=last_group,
            last_source_start=last_source_start,
            min_source_gap_seconds=min_source_gap_seconds,
            clip_usage=clip_usage,
            group_usage=group_usage,
            max_reuse_per_clip=max_reuse_per_clip,
            max_reuse_per_source_group=max_reuse_per_source_group,
        )
        _dedupe_warning_append(warnings, pick_warnings)

        clip_duration = float(candidate["duration"])
        remaining = max(0.0, target_audio_duration - total)
        used_duration = min(clip_duration, remaining)
        start_time = total
        end_time = total + used_duration
        reason = "trimmed to match audio duration" if used_duration < clip_duration else "selected by ai_score overall_score"

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
                "ai_score": {
                    "provider": str((candidate.get("ai_score") or {}).get("provider") or ""),
                    "overall_score": float((candidate.get("ai_score") or {}).get("overall_score") or 0.0),
                    "recommended": bool((candidate.get("ai_score") or {}).get("recommended")),
                },
                "reason": reason,
            }
        )

        total = end_time
        clip_usage[candidate["clip_id"]] += 1
        source_group = str(candidate.get("source_group") or "")
        if source_group:
            group_usage[source_group] += 1
        last_clip_id = candidate["clip_id"]
        last_group = source_group
        last_source_start = float(candidate.get("source_start") or 0.0)
        order += 1

    return timeline, warnings


def _segment_match_score(
    candidate: dict[str, Any],
    segment: dict[str, Any],
    *,
    last_clip_id: str,
    last_group: str,
    last_source_start: float | None,
    min_source_gap_seconds: float,
    clip_usage: Counter[str],
    group_usage: Counter[str],
    max_reuse_per_clip: int,
    max_reuse_per_source_group: int,
    allow_limit_fallback: bool,
) -> tuple[float, float, float, list[str], list[str]]:
    ai_score = candidate.get("ai_score") or {}
    tags = set(candidate.get("tags") or [])
    preferred_tags = {str(tag) for tag in (segment.get("preferred_tags") or []) if tag}
    recommended_tags = {str(tag) for tag in (ai_score.get("recommended_tags") or []) if tag}
    matched_tags: list[str] = []
    reasons: list[str] = []

    base_score = float(ai_score.get("overall_score") or 0.0)
    tag_matches = sorted(tags & preferred_tags)
    if tag_matches:
        base_score += len(tag_matches) * 8
        matched_tags.extend(tag_matches)
        reasons.append("preferred_tags")

    rec_matches = sorted(recommended_tags & preferred_tags)
    if rec_matches:
        base_score += len(rec_matches) * 6
        matched_tags.extend(rec_matches)
        reasons.append("recommended_tags")

    need_gesture = bool(segment.get("need_gesture"))
    if need_gesture and "gesture" in tags:
        base_score += 8
        if "gesture" not in matched_tags:
            matched_tags.append("gesture")
        reasons.append("need_gesture")
    if not need_gesture and ({"stable", "neutral"} & tags):
        base_score += 5
        matched_tags.extend(sorted(({"stable", "neutral"} & tags) - set(matched_tags)))
        reasons.append("need_stable")

    segment_type = str(segment.get("type") or "").strip().lower()
    type_hits = sorted(tags & TYPE_TAG_BONUS.get(segment_type, set()))
    if type_hits:
        base_score += 5
        matched_tags.extend([tag for tag in type_hits if tag not in matched_tags])
        reasons.append(segment_type)

    risk_tags = [str(tag) for tag in (ai_score.get("risk_tags") or []) if tag]
    if risk_tags:
        base_score -= len(risk_tags) * 10
        reasons.append("risk_tags")
    if float(ai_score.get("mouth_occlusion_risk") or 0.0) > 50:
        base_score -= 20
        reasons.append("mouth_occlusion_risk")
    if float(ai_score.get("motion_risk") or 0.0) > 60:
        base_score -= 15
        reasons.append("motion_risk")

    diversity_penalty = 0.0
    if candidate["clip_id"] == last_clip_id:
        diversity_penalty += 1000
        reasons.append("same_clip_blocked")

    source_group = str(candidate.get("source_group") or "")
    if source_group and source_group == last_group:
        diversity_penalty += 70
        reasons.append("same_source_group")

    source_start = float(candidate.get("source_start") or 0.0)
    if last_source_start is not None and abs(source_start - last_source_start) < min_source_gap_seconds:
        diversity_penalty += 40
        reasons.append("source_gap_penalty")

    if clip_usage[candidate["clip_id"]] > 0:
        diversity_penalty += 80
        reasons.append("clip_used")
    if source_group and group_usage[source_group] > 0:
        diversity_penalty += 60
        reasons.append("source_group_used")

    if not allow_limit_fallback:
        if clip_usage[candidate["clip_id"]] >= max_reuse_per_clip:
            diversity_penalty += 1000
            reasons.append("clip_reuse_limit")
        if source_group and group_usage[source_group] >= max_reuse_per_source_group:
            diversity_penalty += 1000
            reasons.append("source_group_reuse_limit")

    final_score = base_score - diversity_penalty
    return base_score, diversity_penalty, final_score, sorted(set(matched_tags)), reasons


def _script_stage_specs(min_overall_score: float) -> list[tuple[str, str]]:
    return [
        ("preferred_unused_group", "recommended_only"),
        ("preferred_unused_clip", "all_usable"),
        ("preferred_allow_group_reuse", "all_usable"),
        ("fallback_high_score", "high_score"),
        ("fallback_reuse_allowed", "all_usable"),
    ]


def _candidate_in_stage(
    candidate: dict[str, Any],
    stage: str,
    *,
    last_clip_id: str,
    last_group: str,
    last_source_start: float | None,
    min_source_gap_seconds: float,
    clip_usage: Counter[str],
    group_usage: Counter[str],
    max_reuse_per_clip: int,
    max_reuse_per_source_group: int,
    min_overall_score: float,
) -> bool:
    ai_score = candidate.get("ai_score") or {}
    source_group = str(candidate.get("source_group") or "")
    source_start = float(candidate.get("source_start") or 0.0)
    if candidate.get("usable") is False:
        return False
    if candidate["clip_id"] == last_clip_id:
        return False
    if stage == "preferred_unused_group":
        return (
            bool(ai_score.get("recommended"))
            and clip_usage[candidate["clip_id"]] == 0
            and group_usage[source_group] == 0
            and clip_usage[candidate["clip_id"]] < max_reuse_per_clip
            and (not source_group or group_usage[source_group] < max_reuse_per_source_group)
            and source_group != last_group
            and (last_source_start is None or abs(source_start - last_source_start) >= min_source_gap_seconds)
        )
    if stage == "preferred_unused_clip":
        return (
            clip_usage[candidate["clip_id"]] == 0
            and group_usage[source_group] == 0
            and clip_usage[candidate["clip_id"]] < max_reuse_per_clip
            and (not source_group or group_usage[source_group] < max_reuse_per_source_group)
        )
    if stage == "preferred_allow_group_reuse":
        return (
            clip_usage[candidate["clip_id"]] == 0
            and clip_usage[candidate["clip_id"]] < max_reuse_per_clip
            and (not source_group or group_usage[source_group] < max_reuse_per_source_group)
        )
    if stage == "fallback_high_score":
        return float(ai_score.get("overall_score") or 0.0) >= min_overall_score
    if stage == "fallback_reuse_allowed":
        return True
    return False


def _pick_script_aware_candidate(
    segment: dict[str, Any],
    usable_candidates: list[dict[str, Any]],
    *,
    last_clip_id: str,
    last_group: str,
    last_source_start: float | None,
    min_source_gap_seconds: float,
    clip_usage: Counter[str],
    group_usage: Counter[str],
    max_reuse_per_clip: int,
    max_reuse_per_source_group: int,
    min_overall_score: float,
) -> tuple[dict[str, Any], dict[str, Any], list[str], list[str]]:
    stage_warnings: list[str] = []
    stage_labels = _script_stage_specs(min_overall_score)

    for stage_name, pool_kind in stage_labels:
        candidates_with_scores: list[tuple[float, float, float, dict[str, Any], list[str], list[str]]] = []
        allow_limit_fallback = stage_name == "fallback_reuse_allowed"
        for candidate in usable_candidates:
            if pool_kind == "recommended_only" and not bool((candidate.get("ai_score") or {}).get("recommended")):
                continue
            if pool_kind == "high_score" and float((candidate.get("ai_score") or {}).get("overall_score") or 0.0) < min_overall_score:
                continue
            if not _candidate_in_stage(
                candidate,
                stage_name,
                last_clip_id=last_clip_id,
                last_group=last_group,
                last_source_start=last_source_start,
                min_source_gap_seconds=min_source_gap_seconds,
                clip_usage=clip_usage,
                group_usage=group_usage,
                max_reuse_per_clip=max_reuse_per_clip,
                max_reuse_per_source_group=max_reuse_per_source_group,
                min_overall_score=min_overall_score,
            ):
                continue
            base_score, diversity_penalty, final_score, matched_tags, reasons = _segment_match_score(
                candidate,
                segment,
                last_clip_id=last_clip_id,
                last_group=last_group,
                last_source_start=last_source_start,
                min_source_gap_seconds=min_source_gap_seconds,
                clip_usage=clip_usage,
                group_usage=group_usage,
                max_reuse_per_clip=max_reuse_per_clip,
                max_reuse_per_source_group=max_reuse_per_source_group,
                allow_limit_fallback=allow_limit_fallback,
            )
            if final_score <= -900:
                continue
            candidates_with_scores.append((final_score, base_score, diversity_penalty, candidate, matched_tags, reasons))

        if not candidates_with_scores:
            if stage_name == "preferred_allow_group_reuse":
                stage_warnings.append(
                    f"segment {segment.get('segment_id')}: no unused source_group candidate available; fallback to reused source_group."
                )
            elif stage_name == "fallback_high_score":
                stage_warnings.append(
                    f"segment {segment.get('segment_id')}: no unused clip candidate available; fallback to high-score reusable clip."
                )
            continue

        candidates_with_scores.sort(
            key=lambda item: (
                -item[0],
                clip_usage[item[3]["clip_id"]],
                group_usage[str(item[3].get("source_group") or "")],
                abs((float(item[3].get("source_start") or 0.0) - (last_source_start if last_source_start is not None else float(item[3].get("source_start") or 0.0))) - min_source_gap_seconds),
                item[3]["clip_id"],
            )
        )
        final_score, base_score, diversity_penalty, best_candidate, matched_tags, reasons = candidates_with_scores[0]
        if stage_name == "fallback_reuse_allowed":
            stage_warnings.append(
                f"segment {segment.get('segment_id')}: clip reuse allowed because no better candidate satisfied constraints."
            )
        debug = {
            "base_match_score": round(base_score, 3),
            "diversity_penalty": round(diversity_penalty, 3),
            "final_match_score": round(final_score, 3),
            "selection_stage": stage_name,
            "reasons": reasons,
        }
        return best_candidate, debug, matched_tags, stage_warnings

    raise SystemExit("No usable AI-scored clips remain to build script-aware timeline.")


def _build_script_aware_timeline(
    candidate_map: dict[str, dict[str, Any]],
    segments: list[dict[str, Any]],
    *,
    target_audio_duration: float,
    min_source_gap_seconds: float,
    max_reuse_per_clip: int,
    max_reuse_per_source_group: int,
    min_overall_score: float,
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    usable_candidates = [candidate for candidate in candidate_map.values() if candidate.get("usable") is not False]
    usable_candidates.sort(key=_candidate_sort_key)
    if not usable_candidates:
        raise SystemExit("No usable clips remain after applying usable=false filtering.")

    clip_usage: Counter[str] = Counter()
    group_usage: Counter[str] = Counter()
    timeline: list[dict[str, Any]] = []
    last_clip_id = ""
    last_group = ""
    last_source_start: float | None = None
    cursor = 0.0

    segment_total = sum(_segment_duration(segment, 0.0) for segment in segments)
    close_to_audio = abs(segment_total - target_audio_duration) < 1.0
    if not close_to_audio:
        warnings.append("Script segments total duration differs from narration duration.")

    for order, segment in enumerate(segments, start=1):
        candidate, debug, matched_tags, stage_warnings = _pick_script_aware_candidate(
            segment,
            usable_candidates,
            last_clip_id=last_clip_id,
            last_group=last_group,
            last_source_start=last_source_start,
            min_source_gap_seconds=min_source_gap_seconds,
            clip_usage=clip_usage,
            group_usage=group_usage,
            max_reuse_per_clip=max_reuse_per_clip,
            max_reuse_per_source_group=max_reuse_per_source_group,
            min_overall_score=min_overall_score,
        )
        _dedupe_warning_append(warnings, stage_warnings)

        requested_duration = _segment_duration(segment, float(candidate["duration"]))
        remaining = max(0.0, target_audio_duration - cursor)
        if close_to_audio and order == len(segments):
            used_duration = min(float(candidate["duration"]), remaining if remaining > 0 else requested_duration)
        else:
            used_duration = min(requested_duration, float(candidate["duration"]), remaining)
        used_duration = round(max(0.0, used_duration), 3)
        start_time = cursor
        end_time = round(cursor + used_duration, 3)
        segment_type = str(segment.get("type") or "")
        reason_parts = ["script-aware match"]
        if segment_type:
            reason_parts.append(segment_type)
        if matched_tags:
            reason_parts.append("preferred_tags")
        reason = ": ".join([reason_parts[0], " + ".join(reason_parts[1:])]) if len(reason_parts) > 1 else reason_parts[0]

        timeline.append(
            {
                "order": order,
                "segment_id": str(segment.get("segment_id") or f"seg_{order:03d}"),
                "segment_type": segment_type,
                "segment_text": str(segment.get("text") or ""),
                "segment_emotion": str(segment.get("emotion") or ""),
                "clip_id": candidate["clip_id"],
                "source_group": candidate.get("source_group") or "",
                "source_start": round(float(candidate.get("source_start") or 0.0), 3),
                "source_end": round(float(candidate.get("source_end") or 0.0), 3),
                "start_time": round(start_time, 3),
                "end_time": end_time,
                "duration": round(float(candidate["duration"]), 3),
                "used_duration": used_duration,
                "path": str(candidate.get("path") or ""),
                "tags": list(candidate.get("tags") or []),
                "content_hint": str(candidate.get("content_hint") or ""),
                "motion_hint": str(candidate.get("motion_hint") or ""),
                "ai_score": {
                    "provider": str((candidate.get("ai_score") or {}).get("provider") or ""),
                    "overall_score": float((candidate.get("ai_score") or {}).get("overall_score") or 0.0),
                    "recommended": bool((candidate.get("ai_score") or {}).get("recommended")),
                },
                "match_score": round(float(debug["final_match_score"]), 3),
                "base_match_score": round(float(debug["base_match_score"]), 3),
                "diversity_penalty": round(float(debug["diversity_penalty"]), 3),
                "final_match_score": round(float(debug["final_match_score"]), 3),
                "selection_stage": str(debug["selection_stage"]),
                "matched_tags": matched_tags,
                "reason": reason,
            }
        )

        clip_usage[candidate["clip_id"]] += 1
        source_group = str(candidate.get("source_group") or "")
        if source_group:
            group_usage[source_group] += 1
        last_clip_id = candidate["clip_id"]
        last_group = source_group
        last_source_start = float(candidate.get("source_start") or 0.0)
        cursor = end_time
        if cursor >= target_audio_duration:
            break

    filler_index = 1
    fallback_segment = segments[-1] if segments else {}
    while cursor < target_audio_duration - 1e-6:
        candidate, debug, matched_tags, stage_warnings = _pick_script_aware_candidate(
            fallback_segment,
            usable_candidates,
            last_clip_id=last_clip_id,
            last_group=last_group,
            last_source_start=last_source_start,
            min_source_gap_seconds=min_source_gap_seconds,
            clip_usage=clip_usage,
            group_usage=group_usage,
            max_reuse_per_clip=max_reuse_per_clip,
            max_reuse_per_source_group=max_reuse_per_source_group,
            min_overall_score=min_overall_score,
        )
        _dedupe_warning_append(warnings, stage_warnings)

        remaining = max(0.0, target_audio_duration - cursor)
        used_duration = round(min(float(candidate["duration"]), remaining), 3)
        start_time = cursor
        end_time = round(cursor + used_duration, 3)
        base_segment_id = str(fallback_segment.get("segment_id") or "seg_fill")
        timeline.append(
            {
                "order": len(timeline) + 1,
                "segment_id": f"{base_segment_id}_fill_{filler_index:03d}",
                "segment_type": str(fallback_segment.get("type") or ""),
                "segment_text": str(fallback_segment.get("text") or ""),
                "segment_emotion": str(fallback_segment.get("emotion") or ""),
                "clip_id": candidate["clip_id"],
                "source_group": candidate.get("source_group") or "",
                "source_start": round(float(candidate.get("source_start") or 0.0), 3),
                "source_end": round(float(candidate.get("source_end") or 0.0), 3),
                "start_time": round(start_time, 3),
                "end_time": end_time,
                "duration": round(float(candidate["duration"]), 3),
                "used_duration": used_duration,
                "path": str(candidate.get("path") or ""),
                "tags": list(candidate.get("tags") or []),
                "content_hint": str(candidate.get("content_hint") or ""),
                "motion_hint": str(candidate.get("motion_hint") or ""),
                "ai_score": {
                    "provider": str((candidate.get("ai_score") or {}).get("provider") or ""),
                    "overall_score": float((candidate.get("ai_score") or {}).get("overall_score") or 0.0),
                    "recommended": bool((candidate.get("ai_score") or {}).get("recommended")),
                },
                "match_score": round(float(debug["final_match_score"]), 3),
                "base_match_score": round(float(debug["base_match_score"]), 3),
                "diversity_penalty": round(float(debug["diversity_penalty"]), 3),
                "final_match_score": round(float(debug["final_match_score"]), 3),
                "selection_stage": str(debug["selection_stage"]),
                "matched_tags": matched_tags,
                "reason": "script-aware fallback fill to match narration duration",
            }
        )
        clip_usage[candidate["clip_id"]] += 1
        source_group = str(candidate.get("source_group") or "")
        if source_group:
            group_usage[source_group] += 1
        last_clip_id = candidate["clip_id"]
        last_group = source_group
        last_source_start = float(candidate.get("source_start") or 0.0)
        cursor = end_time
        filler_index += 1

    return timeline, warnings


def main() -> int:
    args = parse_args()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    reports_dir = runtime_dir / "reports"
    input_dir = runtime_dir / "input"

    candidates_json = reports_dir / "candidates_ai_scored.json"
    narration_audio = input_dir / "narration.wav"
    output_json = reports_dir / "timeline_plan.json"
    script_segments_path = _resolve_script_segments_path(runtime_dir, args.script_segments)

    for path in (candidates_json, narration_audio):
        if not path.exists():
            raise SystemExit(f"Missing required input: {path}")
    if args.max_reuse_per_clip <= 0:
        raise SystemExit("max-reuse-per-clip must be > 0")
    if args.max_reuse_per_source_group <= 0:
        raise SystemExit("max-reuse-per-source-group must be > 0")

    target_audio_duration = _probe_duration(narration_audio)
    candidate_map = _build_candidate_map(_load_candidates(candidates_json))

    if script_segments_path and script_segments_path.exists():
        segments = _load_segments(script_segments_path)
        timeline, warnings = _build_script_aware_timeline(
            candidate_map,
            segments,
            target_audio_duration=target_audio_duration,
            min_source_gap_seconds=args.min_source_gap_seconds,
            max_reuse_per_clip=args.max_reuse_per_clip,
            max_reuse_per_source_group=args.max_reuse_per_source_group,
            min_overall_score=args.min_overall_score,
        )
        planner = "ai_mock_script_aware"
    else:
        timeline, warnings = _build_score_only_timeline(
            candidate_map,
            target_audio_duration=target_audio_duration,
            min_source_gap_seconds=args.min_source_gap_seconds,
            max_reuse_per_clip=args.max_reuse_per_clip,
            max_reuse_per_source_group=args.max_reuse_per_source_group,
            min_overall_score=args.min_overall_score,
        )
        planner = "ai_mock_score"

    payload = {
        "target_audio_duration": round(target_audio_duration, 3),
        "total_timeline_duration": round(sum(item["used_duration"] for item in timeline), 3),
        "planner": planner,
        "min_source_gap_seconds": args.min_source_gap_seconds,
        "max_reuse_per_clip": args.max_reuse_per_clip,
        "max_reuse_per_source_group": args.max_reuse_per_source_group,
        "timeline": timeline,
        "warnings": warnings,
    }
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[DONE] timeline={output_json}")
    print(f"[DONE] items={len(timeline)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
