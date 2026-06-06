from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import cv2


@dataclass
class OcrSegment:
    start: float
    end: float
    text: str
    confidence: float = 0.0
    frame: str = ""


@dataclass
class OcrResult:
    ocrStatus: str
    ocrText: str = ""
    ocrSegments: list[dict[str, Any]] = field(default_factory=list)
    frameCount: int = 0
    textLength: int = 0
    errorMessage: str | None = None
    warnings: list[str] = field(default_factory=list)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _clean_ocr_text(value: str) -> str:
    text = str(value or "").replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("Chat GPT", "ChatGPT").replace("Open AI", "OpenAI")
    text = text.replace("ＣｈａｔＧＰＴ", "ChatGPT").replace("ＯｐｅｎＡＩ", "OpenAI")
    return text.strip("丨|·•~-_—=+* ")


def _is_noise_text(text: str) -> bool:
    if len(text) < 2:
        return True
    if not re.search(r"[\u4e00-\u9fffA-Za-z0-9]", text):
        return True
    symbol_count = len(re.findall(r"[^\u4e00-\u9fffA-Za-z0-9\s]", text))
    return symbol_count > max(4, len(text) * 0.65)


def _similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left, right).ratio()


def _load_ocr_engine() -> Any | None:
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        try:
            from rapidocr import RapidOCR
        except ImportError:
            return None
    return RapidOCR()


def _parse_ocr_output(raw_result: Any) -> tuple[str, float]:
    if raw_result is None:
        return "", 0.0

    result = raw_result[0] if isinstance(raw_result, tuple) else raw_result
    if hasattr(result, "txts"):
        texts = list(getattr(result, "txts") or [])
        scores = list(getattr(result, "scores") or [])
        text = _clean_ocr_text(" ".join(str(item) for item in texts))
        confidence = float(sum(scores) / len(scores)) if scores else 0.0
        return text, confidence

    texts: list[str] = []
    scores: list[float] = []
    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict):
                text = item.get("text") or item.get("rec_text") or ""
                score = item.get("score") or item.get("confidence") or item.get("rec_score") or 0.0
            elif isinstance(item, (list, tuple)) and len(item) >= 3:
                text = item[1]
                score = item[2]
            else:
                continue
            cleaned = _clean_ocr_text(str(text))
            if cleaned:
                texts.append(cleaned)
                try:
                    scores.append(float(score))
                except (TypeError, ValueError):
                    pass

    text = _clean_ocr_text(" ".join(texts))
    confidence = float(sum(scores) / len(scores)) if scores else 0.0
    return text, confidence


def _extract_frames(video_path: Path, frames_dir: Path, max_frames: int) -> list[Path]:
    frames_dir.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        "fps=1",
        "-frames:v",
        str(max_frames),
        str(frames_dir / "frame_%05d.jpg"),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"抽帧失败：{result.stderr.strip()}")
    return sorted(frames_dir.glob("frame_*.jpg"))


def _crop_subtitle_region(frame_path: Path, debug_dir: Path, ratio: float) -> Path | None:
    image = cv2.imread(str(frame_path))
    if image is None:
        return None
    height = image.shape[0]
    crop_y = max(0, int(height * (1.0 - ratio)))
    cropped = image[crop_y:height, :]
    debug_dir.mkdir(parents=True, exist_ok=True)
    debug_path = debug_dir / f"{frame_path.stem}_bottom_{int(ratio * 100)}.jpg"
    cv2.imwrite(str(debug_path), cropped)
    return debug_path


def _dedupe_segments(segments: list[OcrSegment]) -> list[OcrSegment]:
    deduped: list[OcrSegment] = []
    for segment in segments:
        if not deduped:
            deduped.append(segment)
            continue
        previous = deduped[-1]
        if previous.text == segment.text or _similarity(previous.text, segment.text) >= 0.85:
            previous.end = segment.end
            previous.confidence = max(previous.confidence, segment.confidence)
            if len(segment.text) > len(previous.text):
                previous.text = segment.text
                previous.frame = segment.frame
            continue
        deduped.append(segment)
    return deduped


def _save_empty_result(output_dir: Path, status: str, warning: str, error_message: str | None = None) -> OcrResult:
    result = OcrResult(ocrStatus=status, errorMessage=error_message, warnings=[warning])
    (output_dir / "ocr_text.txt").write_text("", encoding="utf-8")
    _write_json(output_dir / "ocr_subtitles.json", [])
    return result


def extract_ocr_subtitles(video_path: Path, output_dir: Path, *, max_frames: int = 80) -> OcrResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = output_dir / "ocr_frames"
    debug_dir = output_dir / "ocr_debug"
    shutil.rmtree(frames_dir, ignore_errors=True)
    shutil.rmtree(debug_dir, ignore_errors=True)

    engine = _load_ocr_engine()
    if engine is None:
        return _save_empty_result(output_dir, "skipped", "OCR 依赖未安装，已使用 ASR 结果。")

    try:
        frame_paths = _extract_frames(video_path, frames_dir, max_frames=max_frames)
    except Exception as exc:
        return _save_empty_result(output_dir, "failed", "OCR 抽帧失败，已使用 ASR 结果。", str(exc))

    segments: list[OcrSegment] = []
    warnings: list[str] = []
    for index, frame_path in enumerate(frame_paths):
        frame_time = float(index)
        best_text = ""
        best_confidence = 0.0
        best_frame = ""
        for ratio in (0.35, 0.45):
            crop_path = _crop_subtitle_region(frame_path, debug_dir, ratio)
            if crop_path is None:
                continue
            try:
                text, confidence = _parse_ocr_output(engine(str(crop_path)))
            except Exception as exc:
                warnings.append(f"OCR 识别失败：{frame_path.name}")
                if len(warnings) <= 2:
                    warnings.append(str(exc))
                continue
            if text and not _is_noise_text(text):
                best_text = text
                best_confidence = confidence
                best_frame = crop_path.name
                break
        if best_text:
            segments.append(
                OcrSegment(
                    start=frame_time,
                    end=frame_time + 1.0,
                    text=best_text,
                    confidence=round(best_confidence, 4),
                    frame=best_frame,
                )
            )

    deduped = _dedupe_segments(segments)
    payload = [
        {
            "start": item.start,
            "end": item.end,
            "text": item.text,
            "confidence": item.confidence,
            "frame": item.frame,
        }
        for item in deduped
    ]
    ocr_text = "\n".join(item["text"] for item in payload).strip()
    (output_dir / "ocr_text.txt").write_text(ocr_text + ("\n" if ocr_text else ""), encoding="utf-8")
    _write_json(output_dir / "ocr_subtitles.json", payload)

    if not ocr_text:
        return OcrResult(
            ocrStatus="failed",
            frameCount=len(frame_paths),
            errorMessage="OCR 未识别到有效字幕。",
            warnings=[*warnings, "OCR 未识别到有效字幕，已使用 ASR 结果。"],
        )

    return OcrResult(
        ocrStatus="success",
        ocrText=ocr_text,
        ocrSegments=payload,
        frameCount=len(frame_paths),
        textLength=len(ocr_text),
        warnings=warnings,
    )
