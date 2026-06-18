from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


NEGATIVE_TAGS = {"bad", "unusable", "occlusion", "hand_cover_mouth"}
POSITIVE_TAGS = {"gesture", "neutral", "good_for_explain"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate mock AI scores for Template Clip Bank candidates")
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
    raise SystemExit(f"Unsupported candidates json structure: {path}")


def _sheet_path(runtime_dir: Path, clip_id: str) -> tuple[str, bool]:
    rel = Path("sheets") / f"{clip_id}.jpg"
    abs_path = runtime_dir / rel
    return str(rel), abs_path.exists()


def _mock_ai_score(candidate: dict[str, Any], *, sheet_exists: bool) -> dict[str, Any]:
    tags = {str(tag) for tag in (candidate.get("tags") or []) if tag}
    usable = candidate.get("usable", True) is not False

    overall_score = 70
    face_visible_score = 80
    stability_score = 70
    gesture_score = 60
    mouth_occlusion_risk = 20
    motion_risk = 30
    reuse_value_score = 70
    recommended = True
    recommended_tags: list[str] = []
    risk_tags: list[str] = []
    ai_content_hint = ""
    ai_motion_hint = ""
    ai_reason_parts = ["mock score for pipeline compatibility"]

    positive_hits = sorted(tags & POSITIVE_TAGS)
    negative_hits = sorted(tags & NEGATIVE_TAGS)

    if "neutral" in tags:
        overall_score += 4
        face_visible_score += 2
        stability_score += 4
        reuse_value_score += 5
        recommended_tags.extend(["neutral", "explain"])
        ai_reason_parts.append("neutral tag increases reuse value")

    if "gesture" in tags:
        overall_score += 3
        gesture_score += 12
        reuse_value_score += 4
        if "gesture" not in recommended_tags:
            recommended_tags.append("gesture")
        ai_reason_parts.append("gesture tag suggests usable speaking motion")

    if "good_for_explain" in tags:
        overall_score += 6
        stability_score += 4
        reuse_value_score += 6
        if "good_for_explain" not in recommended_tags:
            recommended_tags.append("good_for_explain")
        ai_reason_parts.append("good_for_explain tag boosts explain suitability")

    if not sheet_exists:
        overall_score -= 10
        face_visible_score -= 10
        stability_score -= 5
        motion_risk += 10
        risk_tags.append("missing_sheet_preview")
        ai_reason_parts.append("sheet preview is missing")

    if not usable:
        overall_score -= 25
        reuse_value_score -= 30
        recommended = False
        risk_tags.append("manual_unusable")
        ai_reason_parts.append("manual usable=false lowers recommendation")

    if negative_hits:
        overall_score -= 20
        mouth_occlusion_risk += 25 if {"occlusion", "hand_cover_mouth"} & tags else 10
        motion_risk += 15 if "bad" in tags else 5
        recommended = False
        risk_tags.extend(negative_hits)
        ai_reason_parts.append("negative tags increase risk")

    overall_score = max(0, min(100, overall_score))
    face_visible_score = max(0, min(100, face_visible_score))
    stability_score = max(0, min(100, stability_score))
    gesture_score = max(0, min(100, gesture_score))
    mouth_occlusion_risk = max(0, min(100, mouth_occlusion_risk))
    motion_risk = max(0, min(100, motion_risk))
    reuse_value_score = max(0, min(100, reuse_value_score))

    if overall_score < 50:
        recommended = False

    if not recommended_tags and usable:
        recommended_tags = ["neutral"] if not negative_hits else []

    if positive_hits and not ai_content_hint:
        ai_content_hint = "适合口播复用的稳定候选片段"
    if "gesture" in tags and not ai_motion_hint:
        ai_motion_hint = "存在轻微自然手势，适合解释型内容"

    return {
        "provider": "mock",
        "overall_score": overall_score,
        "face_visible_score": face_visible_score,
        "stability_score": stability_score,
        "gesture_score": gesture_score,
        "mouth_occlusion_risk": mouth_occlusion_risk,
        "motion_risk": motion_risk,
        "reuse_value_score": reuse_value_score,
        "recommended": recommended,
        "recommended_tags": recommended_tags,
        "risk_tags": sorted(set(risk_tags)),
        "ai_content_hint": ai_content_hint,
        "ai_motion_hint": ai_motion_hint,
        "ai_reason": "; ".join(ai_reason_parts),
    }


def _vision_review_prompt() -> str:
    return """# Vision Review Prompt

## Task

You are reviewing candidate template-video clips for a template digital human pipeline.
Each input image is a contact sheet built from one short clip, usually six sampled frames from that clip.

Your job is to judge whether the clip is visually reusable for talking-head style narration.

## Input

- One or more candidate preview sheets such as `clip_001.jpg`
- Each sheet represents one candidate video clip
- A clip may already include manual tags or notes, but your visual judgment should focus on what is visible in the preview image

## Review Criteria

For each clip, evaluate:

1. Whether the face is clearly visible
2. Whether the subject is front-facing or only slightly side-facing
3. Whether hands or objects cover the mouth
4. Whether motion is stable enough for later lip-sync reuse
5. Whether the expression looks natural
6. Whether the clip is suitable for reusable talking-head narration
7. Which content types it best fits:
   - intro
   - explain
   - transition
   - emphasis
   - outro

## Output Requirement

Return JSON only.

## JSON Format

```json
{
  "clips": [
    {
      "clip_id": "clip_001",
      "overall_score": 85,
      "face_visible_score": 90,
      "stability_score": 80,
      "gesture_score": 75,
      "mouth_occlusion_risk": 10,
      "motion_risk": 20,
      "reuse_value_score": 85,
      "recommended": true,
      "recommended_tags": ["neutral", "gesture", "good_for_explain"],
      "risk_tags": [],
      "ai_content_hint": "正脸讲解，表情自然，适合解释型内容",
      "ai_motion_hint": "轻微手势，头部稳定",
      "ai_reason": "人脸清晰，动作自然，没有明显挡嘴"
    }
  ]
}
```
"""


def main() -> int:
    args = parse_args()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    reports_dir = runtime_dir / "reports"
    input_json = reports_dir / "candidates_enriched.json"
    output_json = reports_dir / "candidates_ai_scored.json"
    prompt_md = reports_dir / "vision_review_prompt.md"

    if not input_json.exists():
        raise SystemExit(f"Missing candidates_enriched.json: {input_json}")

    payload, candidates = _load_candidates(input_json)
    scored_clips: list[dict[str, Any]] = []

    for index, candidate in enumerate(candidates, start=1):
        clip_id = str(candidate.get("clip_id") or f"clip_{index:03d}")
        sheet_path, sheet_exists = _sheet_path(runtime_dir, clip_id)
        scored_clips.append(
            {
                **candidate,
                "clip_id": clip_id,
                "sheet_path": sheet_path,
                "ai_score": _mock_ai_score(candidate, sheet_exists=sheet_exists),
            }
        )

    output_payload: dict[str, Any]
    if payload:
        output_payload = dict(payload)
        if "clips" in output_payload:
            output_payload["clips"] = scored_clips
        elif "candidates" in output_payload:
            output_payload["candidates"] = scored_clips
        else:
            output_payload["clips"] = scored_clips
    else:
        output_payload = {"clips": scored_clips}

    output_json.write_text(json.dumps(output_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    prompt_md.write_text(_vision_review_prompt(), encoding="utf-8")

    print(f"[DONE] scored={len(scored_clips)}")
    print(f"[DONE] output={output_json}")
    print(f"[DONE] prompt={prompt_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
