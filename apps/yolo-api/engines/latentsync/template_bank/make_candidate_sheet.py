from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build per-clip preview sheets and a combined candidate sheet")
    parser.add_argument("--runtime-dir", required=True, help="Template Clip Bank runtime directory")
    parser.add_argument("--frames-per-clip", type=int, default=6, help="Number of frames to sample from each clip")
    parser.add_argument("--thumb-height", type=int, default=180, help="Output height for each sampled frame")
    parser.add_argument("--max-clips-per-page", type=int, default=12, help="Maximum number of clip previews per sheet page")
    return parser.parse_args()


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


def _format_seconds(value: Any) -> str:
    try:
        return f"{float(value):.2f}s"
    except (TypeError, ValueError):
        return "unknown"


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
        return runtime_path.resolve()
    clip_id = str(candidate.get("clip_id") or f"clip_{fallback_index:03d}")
    direct = candidates_dir / f"{clip_id}.mp4"
    if direct.exists():
        return direct.resolve()
    matches = sorted(candidates_dir.glob("*.mp4"))
    if 0 <= fallback_index - 1 < len(matches):
        return matches[fallback_index - 1].resolve()
    return direct.resolve()


def _sample_frame_indexes(frame_count: int, sample_count: int) -> list[int]:
    if frame_count <= 0:
        return [0] * sample_count
    if frame_count == 1:
        return [0] * sample_count
    indexes = np.linspace(0, frame_count - 1, num=sample_count)
    return [int(round(float(index))) for index in indexes]


def _read_frame(capture: cv2.VideoCapture, frame_index: int) -> np.ndarray | None:
    capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, frame = capture.read()
    if not ok or frame is None:
        return None
    return frame


def _resize_to_height(image: np.ndarray, target_height: int) -> np.ndarray:
    height, width = image.shape[:2]
    if height <= 0 or width <= 0:
        return image
    target_width = max(1, int(round(width * target_height / height)))
    return cv2.resize(image, (target_width, target_height), interpolation=cv2.INTER_AREA)


def _draw_label_bar(image: np.ndarray, clip_id: str, start: Any, end: Any) -> np.ndarray:
    bar_height = 46
    label = f"{clip_id}  start={_format_seconds(start)}  end={_format_seconds(end)}"
    bar = np.full((bar_height, image.shape[1], 3), 245, dtype=np.uint8)
    cv2.putText(bar, label, (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (25, 25, 25), 2, cv2.LINE_AA)
    return np.vstack([bar, image])


def _placeholder_strip(message: str, width: int, height: int) -> np.ndarray:
    image = np.full((height, width, 3), 240, dtype=np.uint8)
    cv2.putText(image, message, (18, max(30, height // 2)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (40, 40, 180), 2, cv2.LINE_AA)
    return image


def _build_clip_preview(
    clip_path: Path,
    *,
    clip_id: str,
    start: Any,
    end: Any,
    frames_per_clip: int,
    thumb_height: int,
) -> np.ndarray:
    capture = cv2.VideoCapture(str(clip_path))
    if not capture.isOpened():
        strip = _placeholder_strip(f"Missing clip: {clip_path.name}", width=frames_per_clip * thumb_height, height=thumb_height)
        return _draw_label_bar(strip, clip_id, start, end)
    try:
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        frame_indexes = _sample_frame_indexes(frame_count, frames_per_clip)
        frames: list[np.ndarray] = []
        for frame_index in frame_indexes:
            frame = _read_frame(capture, frame_index)
            if frame is None:
                continue
            frames.append(_resize_to_height(frame, thumb_height))
    finally:
        capture.release()

    if not frames:
        strip = _placeholder_strip(f"No frames: {clip_path.name}", width=frames_per_clip * thumb_height, height=thumb_height)
        return _draw_label_bar(strip, clip_id, start, end)

    max_width = max(frame.shape[1] for frame in frames)
    normalized = []
    for frame in frames:
        pad = max_width - frame.shape[1]
        left = pad // 2
        right = pad - left
        normalized.append(cv2.copyMakeBorder(frame, 0, 0, left, right, cv2.BORDER_CONSTANT, value=(255, 255, 255)))
    strip = np.hstack(normalized)
    return _draw_label_bar(strip, clip_id, start, end)


def _make_grid(images: list[np.ndarray]) -> np.ndarray:
    if not images:
        raise SystemExit("No candidate preview images were generated")
    cell_width = max(image.shape[1] for image in images)
    cell_height = max(image.shape[0] for image in images)
    columns = max(1, min(4, math.ceil(math.sqrt(len(images)))))
    rows: list[np.ndarray] = []
    for start_index in range(0, len(images), columns):
        row_images = images[start_index : start_index + columns]
        padded_row = []
        for image in row_images:
            pad_bottom = cell_height - image.shape[0]
            pad_right = cell_width - image.shape[1]
            padded_row.append(
                cv2.copyMakeBorder(
                    image,
                    0,
                    pad_bottom,
                    0,
                    pad_right,
                    cv2.BORDER_CONSTANT,
                    value=(255, 255, 255),
                )
            )
        while len(padded_row) < columns:
            padded_row.append(np.full((cell_height, cell_width, 3), 255, dtype=np.uint8))
        rows.append(np.hstack(padded_row))
    return np.vstack(rows)


def _write_sheet_pages(
    images: list[np.ndarray],
    sheets_dir: Path,
    *,
    max_clips_per_page: int,
) -> list[Path]:
    pages: list[Path] = []
    if max_clips_per_page <= 0:
        raise SystemExit("max-clips-per-page must be > 0")
    for page_index, start_index in enumerate(range(0, len(images), max_clips_per_page), start=1):
        page_images = images[start_index : start_index + max_clips_per_page]
        page = _make_grid(page_images)
        page_path = sheets_dir / f"candidate_sheet_page_{page_index:03d}.jpg"
        cv2.imwrite(str(page_path), page, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        pages.append(page_path)
    if pages:
        first_page = cv2.imread(str(pages[0]))
        if first_page is not None:
            cv2.imwrite(str(sheets_dir / "candidate_sheet.jpg"), first_page, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    return pages


def main() -> int:
    args = parse_args()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    candidates_json = runtime_dir / "reports" / "candidates.json"
    candidates_dir = runtime_dir / "candidates"
    sheets_dir = runtime_dir / "sheets"
    sheets_dir.mkdir(parents=True, exist_ok=True)

    if not candidates_json.exists():
        raise SystemExit(f"Missing candidates.json: {candidates_json}")
    if not candidates_dir.exists():
        raise SystemExit(f"Missing candidates directory: {candidates_dir}")

    candidates = _load_candidates(candidates_json)
    preview_images: list[np.ndarray] = []

    for index, candidate in enumerate(candidates, start=1):
        clip_id = str(candidate.get("clip_id") or f"clip_{index:03d}")
        clip_path = _candidate_clip_path(candidate, runtime_dir, candidates_dir, index)
        preview = _build_clip_preview(
            clip_path,
            clip_id=clip_id,
            start=candidate.get("start"),
            end=candidate.get("end"),
            frames_per_clip=args.frames_per_clip,
            thumb_height=args.thumb_height,
        )
        clip_output = sheets_dir / f"{clip_id}.jpg"
        cv2.imwrite(str(clip_output), preview, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        preview_images.append(preview)

    pages = _write_sheet_pages(
        preview_images,
        sheets_dir,
        max_clips_per_page=args.max_clips_per_page,
    )
    sheet_path = sheets_dir / "candidate_sheet.jpg"

    print(f"[DONE] candidates={len(candidates)}")
    print(f"[DONE] sheet={sheet_path}")
    print(f"[DONE] pages={len(pages)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
