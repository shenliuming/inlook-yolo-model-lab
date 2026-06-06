from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any


DEFAULT_HOTWORDS = [
    "OpenAI",
    "ChatGPT",
    "ChatGPT Plus",
    "GPT",
    "GPT-4",
    "GPT-5",
    "Cursor",
    "Claude",
    "Gemini",
    "AI",
    "马耳他",
    "Plus",
    "免费",
    "合法",
    "订阅",
    "模型",
    "课程",
    "评论区",
    "私聊",
    "网站",
    "20 美刀",
    "普通用户",
    "基础能力",
]

HOTWORD_CORRECTIONS = [
    ("XGBT Plus", "ChatGPT Plus"),
    ("XGB Plus", "ChatGPT Plus"),
    ("XGP Plus", "ChatGPT Plus"),
    ("XG PLUS", "ChatGPT Plus"),
    ("XG Plus", "ChatGPT Plus"),
    ("摆一套PLUS", "白嫖一套 Plus"),
    ("白嫖PLUS", "白嫖 Plus"),
    ("OpenI", "OpenAI"),
    ("Openl", "OpenAI"),
    ("openI", "OpenAI"),
    ("openl", "OpenAI"),
    ("open ai", "OpenAI"),
    ("XGBT", "ChatGPT"),
    ("XGB", "ChatGPT"),
    ("XGP", "ChatGPT"),
    ("GPTB", "ChatGPT"),
    ("恰GPT", "ChatGPT"),
    ("查GPT", "ChatGPT"),
    ("马尔他军兵", "马耳他居民"),
    ("马尔拉他", "马耳他"),
    ("马尔拉", "马耳他"),
    ("马尔他", "马耳他"),
    ("AI数码课程", "AI 数字课程"),
    ("AI数量课程", "AI 相关课程"),
    ("硬豪", "硬薅"),
    ("叫20美刀", "交 20 美刀"),
    ("去说订阅", "去订阅"),
    ("试料", "私聊"),
    ("莫尾", "末尾"),
    ("隐吼", "入口"),
    ("全属用户", "全体用户"),
    ("也会不会用AI", "以后会不会用 AI"),
    ("这条身份真正值得看的", "这条视频真正值得看的"),
    ("前处用户", "普通用户"),
]

OCR_EVIDENCE_CORRECTIONS = [
    ("ChatGPT Plus", [("XG PLUS", "ChatGPT Plus"), ("XG Plus", "ChatGPT Plus"), ("XGB Plus", "ChatGPT Plus"), ("XGBT Plus", "ChatGPT Plus")]),
    ("ChatGPT", [("XGBT", "ChatGPT"), ("XGB", "ChatGPT"), ("XGP", "ChatGPT"), ("GPTB", "ChatGPT")]),
    ("OpenAI", [("OpenI", "OpenAI"), ("Openl", "OpenAI"), ("openI", "OpenAI"), ("openl", "OpenAI")]),
    ("马耳他居民", [("马尔他军兵", "马耳他居民")]),
    ("马耳他", [("马尔他", "马耳他"), ("马尔拉", "马耳他")]),
    ("AI 数字课程", [("AI数码课程", "AI 数字课程")]),
    ("私聊", [("试料", "私聊")]),
    ("硬薅", [("硬豪", "硬薅")]),
    ("交 20 美刀", [("叫20美刀", "交 20 美刀")]),
    ("去订阅", [("去说订阅", "去订阅")]),
]


@dataclass
class FusionResult:
    finalText: str
    fusionSource: str
    fusionStats: dict[str, Any] = field(default_factory=dict)
    correctionsApplied: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _normalize_hotword(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def build_hotwords(material: dict[str, Any] | None = None, extra_keywords: list[str] | None = None) -> list[str]:
    hotwords: list[str] = []

    def add(word: str) -> None:
        normalized = _normalize_hotword(word)
        if normalized and normalized not in hotwords:
            hotwords.append(normalized)

    for word in DEFAULT_HOTWORDS:
        add(word)

    material = material if isinstance(material, dict) else {}
    for key in ("title", "description", "caption"):
        value = material.get(key)
        if isinstance(value, str):
            add(value)

    for tag in material.get("tags") or []:
        if isinstance(tag, str):
            add(tag)

    for keyword in material.get("keepKeywords") or []:
        if isinstance(keyword, str):
            add(keyword)

    for keyword in extra_keywords or []:
        if isinstance(keyword, str):
            add(keyword)

    return hotwords


def build_initial_prompt(hotwords: list[str]) -> str:
    prompt_hotwords = "、".join(hotwords[:28])
    return (
        "以下是中文短视频口播内容，可能包含中英文混合词和专有名词："
        f"{prompt_hotwords}。"
        "请尽量保持这些专有名词准确。"
        "不要把 ChatGPT 识别成 XGB、XGBT。"
        "不要把 OpenAI 识别成 OpenI。"
        "不要把马耳他识别成马尔他。"
    )


def _apply_correction_pairs(text: str, pairs: list[tuple[str, str]], source: str) -> tuple[str, list[dict[str, Any]]]:
    corrected = str(text or "")
    applied: list[dict[str, Any]] = []

    for raw, target in pairs:
        count = corrected.count(raw)
        if count <= 0:
            continue
        corrected = corrected.replace(raw, target)
        applied.append({"from": raw, "to": target, "count": count, "source": source})

    return corrected, applied


def apply_asr_corrections(asr_text: str, hotwords: list[str] | None = None) -> tuple[str, list[dict[str, Any]]]:
    del hotwords
    return _apply_correction_pairs(asr_text, HOTWORD_CORRECTIONS, "asr_rule")


def correct_hotwords(text: str) -> tuple[str, list[dict[str, Any]]]:
    return apply_asr_corrections(text)


def _normalize_text(value: str) -> str:
    text = str(value or "").replace(",", "，")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    for term in ("ChatGPT Plus", "ChatGPT", "OpenAI", "GPT-4", "GPT-5", "GPT", "AI", "Plus"):
        text = re.sub(rf"\s*{re.escape(term)}\s*", f" {term} ", text)
    text = re.sub(r"([\u4e00-\u9fff]) +(ChatGPT|OpenAI|GPT|AI|Plus)", r"\1 \2", text)
    text = re.sub(r"(ChatGPT Plus|ChatGPT|OpenAI|GPT-4|GPT-5|GPT|AI|Plus) +([\u4e00-\u9fff])", r"\1 \2", text)
    text = re.sub(r" {2,}", " ", text)
    text = text.replace("Chat GPT Plus", "ChatGPT Plus")
    text = text.replace("Chat GPT", "ChatGPT")
    text = text.replace("Open AI", "OpenAI")
    return "\n".join(line.strip() for line in text.splitlines() if line.strip()).strip()


def _is_ocr_noise(text: str) -> bool:
    value = str(text or "").strip()
    if len(value) < 6:
        return True
    if not re.search(r"[\u4e00-\u9fffA-Za-z0-9]", value):
        return True
    unique_chars = len(set(value))
    return unique_chars <= 3 and len(value) > 12


def _overlap_ratio(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_start = float(left.get("start") or 0.0)
    left_end = float(left.get("end") or left_start)
    right_start = float(right.get("start") or 0.0)
    right_end = float(right.get("end") or right_start)
    overlap = max(0.0, min(left_end, right_end) - max(left_start, right_start))
    duration = max(0.001, left_end - left_start)
    return overlap / duration


def _text_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left, right).ratio()


def _contains_evidence(text: str) -> bool:
    return bool(re.search(r"ChatGPT|OpenAI|GPT|AI|Plus|马耳他|私聊|课程|评论区|20 美刀", text))


def _apply_ocr_evidence(text: str, ocr_text: str) -> tuple[str, list[dict[str, Any]]]:
    corrected = str(text or "")
    applied: list[dict[str, Any]] = []
    for evidence, pairs in OCR_EVIDENCE_CORRECTIONS:
        if evidence not in ocr_text:
            continue
        corrected, current = _apply_correction_pairs(corrected, pairs, "ocr_evidence")
        applied.extend(current)
    return corrected, applied


def _best_ocr_match(asr_segment: dict[str, Any], ocr_segments: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, float]:
    best: dict[str, Any] | None = None
    best_ratio = 0.0
    for segment in ocr_segments:
        ratio = _overlap_ratio(asr_segment, segment)
        if ratio > best_ratio:
            best = segment
            best_ratio = ratio
    return best, best_ratio


def build_final_text_from_asr_ocr(
    *,
    asr_text: str,
    asr_segments: list[dict[str, Any]],
    corrected_asr_text: str,
    ocr_text: str,
    ocr_segments: list[dict[str, Any]],
    ocr_status: str,
) -> FusionResult:
    corrected = _normalize_text(corrected_asr_text or asr_text)
    ocr_clean = _normalize_text(ocr_text)
    warnings: list[str] = []
    fusion_corrections: list[dict[str, Any]] = []
    stats = {
        "asrLength": len(asr_text or ""),
        "ocrLength": len(ocr_clean),
        "ocrSegmentCount": len(ocr_segments or []),
        "replacedSegmentCount": 0,
    }

    if ocr_status != "success" or not ocr_clean or _is_ocr_noise(ocr_clean):
        if ocr_status != "success":
            warnings.append("OCR 未可用，已使用 ASR 纠错结果。")
        elif not ocr_clean:
            warnings.append("OCR 未识别到有效字幕，已使用 ASR 纠错结果。")
        else:
            warnings.append("OCR 文本疑似噪声，已使用 ASR 纠错结果。")
        return FusionResult(finalText=corrected, fusionSource="asr_only", fusionStats=stats, warnings=warnings)

    if len(ocr_clean) >= max(24, len(asr_text or "") * 0.55) and len(ocr_segments or []) >= 5:
        stats["replacedSegmentCount"] = len(ocr_segments or [])
        return FusionResult(finalText=ocr_clean, fusionSource="ocr_primary", fusionStats=stats, warnings=warnings)

    if not asr_segments:
        text, evidence_corrections = _apply_ocr_evidence(corrected, ocr_clean)
        fusion_corrections.extend(evidence_corrections)
        return FusionResult(
            finalText=_normalize_text(text),
            fusionSource="asr_ocr_fusion" if fusion_corrections else "asr_only",
            fusionStats=stats,
            correctionsApplied=fusion_corrections,
            warnings=warnings,
        )

    final_segments: list[str] = []
    for segment in asr_segments:
        asr_segment_text, segment_corrections = apply_asr_corrections(str(segment.get("text") or ""))
        fusion_corrections.extend(segment_corrections)
        matched_ocr, ratio = _best_ocr_match(segment, ocr_segments or [])
        if matched_ocr and ratio > 0.3:
            matched_text = _normalize_text(str(matched_ocr.get("text") or ""))
            if len(matched_text) >= 4 and (
                _contains_evidence(matched_text)
                or len(matched_text) >= max(4, len(asr_segment_text) * 0.45)
                or _text_similarity(matched_text, asr_segment_text) >= 0.35
            ):
                final_segments.append(matched_text)
                stats["replacedSegmentCount"] += 1
                fusion_corrections.append({
                    "from": asr_segment_text,
                    "to": matched_text,
                    "count": 1,
                    "source": "ocr_time_overlap",
                })
                continue
        fixed_text, evidence_corrections = _apply_ocr_evidence(asr_segment_text, ocr_clean)
        fusion_corrections.extend(evidence_corrections)
        final_segments.append(fixed_text)

    final_text = _normalize_text("\n".join(final_segments))
    return FusionResult(
        finalText=final_text or corrected,
        fusionSource="asr_ocr_fusion" if stats["replacedSegmentCount"] or fusion_corrections else "asr_only",
        fusionStats=stats,
        correctionsApplied=fusion_corrections,
        warnings=warnings,
    )
