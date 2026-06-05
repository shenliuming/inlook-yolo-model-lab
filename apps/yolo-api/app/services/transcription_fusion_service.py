from __future__ import annotations

import re
from typing import Any

DEFAULT_HOTWORDS = [
    "OpenAI",
    "ChatGPT",
    "ChatGPT Plus",
    "GPT",
    "Cursor",
    "Claude",
    "Gemini",
    "马耳他",
    "AI",
    "免费",
    "合法",
    "订阅",
    "模型",
    "课程",
    "评论区",
    "私聊",
    "网站",
    "Plus",
    "20 美刀",
]

HOTWORD_CORRECTIONS = [
    ("XGBT Plus", "ChatGPT Plus"),
    ("XGB Plus", "ChatGPT Plus"),
    ("XGP Plus", "ChatGPT Plus"),
    ("OpenI", "OpenAI"),
    ("Openl", "OpenAI"),
    ("openI", "OpenAI"),
    ("open ai", "OpenAI"),
    ("XGBT", "ChatGPT"),
    ("XGB", "ChatGPT"),
    ("XGP", "ChatGPT"),
    ("GPTB", "ChatGPT"),
    ("恰GPT", "ChatGPT"),
    ("查GPT", "ChatGPT"),
    ("马尔拉他", "马耳他"),
    ("马尔拉", "马耳他"),
    ("马尔他", "马耳他"),
    ("莫尾", "末尾"),
    ("试料", "私聊"),
    ("叫20美刀", "交 20 美刀"),
    ("去说订阅", "去订阅"),
    ("AI数量课程", "AI 相关课程"),
    ("前处用户", "普通用户"),
    ("隐吼", "入口"),
]


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
    for key in ("title", "description"):
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
    prompt_hotwords = "、".join(hotwords[:24])
    return (
        "以下是中文短视频口播内容，可能包含中英文混合词和专有名词："
        f"{prompt_hotwords}。"
        "请尽量保持这些专有名词准确。"
        "不要把 ChatGPT 识别成 XGB、XGBT。"
        "不要把 OpenAI 识别成 OpenI。"
        "不要把马耳他识别成马尔他。"
    )


def correct_hotwords(text: str) -> tuple[str, list[dict[str, Any]]]:
    corrected = str(text or "")
    applied: list[dict[str, Any]] = []

    for source, target in HOTWORD_CORRECTIONS:
        count = corrected.count(source)
        if count <= 0:
            continue
        corrected = corrected.replace(source, target)
        applied.append({"from": source, "to": target, "count": count})

    return corrected, applied
