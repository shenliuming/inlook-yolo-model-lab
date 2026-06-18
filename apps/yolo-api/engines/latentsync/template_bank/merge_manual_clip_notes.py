from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_CLIP_FIELDS = {
    "content_hint": "",
    "motion_hint": "",
    "tags": [],
    "usable": True,
    "manual_note": "",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge manual clip notes into candidates metadata")
    parser.add_argument("--runtime-dir", required=True, help="Template Clip Bank runtime directory")
    return parser.parse_args()


def _load_candidates(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return {}, [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("clips", "candidates"):
            items = payload.get(key)
            if isinstance(items, list):
                return payload, [item for item in items if isinstance(item, dict)]
    raise SystemExit(f"Unsupported candidates.json structure: {path}")


def _load_manual_notes(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    clips = payload.get("clips")
    if not isinstance(clips, list):
        raise SystemExit(f"manual_clip_notes.json missing clips list: {path}")
    notes: dict[str, dict[str, Any]] = {}
    for item in clips:
        if not isinstance(item, dict):
            continue
        clip_id = item.get("clip_id")
        if not clip_id:
            continue
        notes[str(clip_id)] = item
    return notes


def main() -> int:
    args = parse_args()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    reports_dir = runtime_dir / "reports"
    input_dir = runtime_dir / "input"

    candidates_json = reports_dir / "candidates.json"
    manual_notes_json = input_dir / "manual_clip_notes.json"
    output_json = reports_dir / "candidates_enriched.json"

    if not candidates_json.exists():
        raise SystemExit(f"Missing candidates.json: {candidates_json}")
    if not manual_notes_json.exists():
        raise SystemExit(f"Missing manual_clip_notes.json: {manual_notes_json}")

    payload, candidates = _load_candidates(candidates_json)
    notes_by_id = _load_manual_notes(manual_notes_json)

    enriched: list[dict[str, Any]] = []
    for candidate in candidates:
        clip_id = str(candidate.get("clip_id") or "")
        note = notes_by_id.get(clip_id, {})
        item = {
            **candidate,
            **DEFAULT_CLIP_FIELDS,
            "content_hint": note.get("content_hint", candidate.get("content_hint", "")),
            "motion_hint": note.get("motion_hint", candidate.get("motion_hint", "")),
            "tags": note.get("tags", candidate.get("tags", [])) or [],
            "usable": note.get("usable", candidate.get("usable", True)),
            "manual_note": note.get("manual_note", candidate.get("manual_note", "")),
        }
        enriched.append(item)

    output_payload: dict[str, Any]
    if payload:
        output_payload = dict(payload)
        if "clips" in output_payload:
            output_payload["clips"] = enriched
        elif "candidates" in output_payload:
            output_payload["candidates"] = enriched
        else:
            output_payload["clips"] = enriched
    else:
        output_payload = {"clips": enriched}

    output_json.write_text(json.dumps(output_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[DONE] candidates={len(enriched)}")
    print(f"[DONE] output={output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
