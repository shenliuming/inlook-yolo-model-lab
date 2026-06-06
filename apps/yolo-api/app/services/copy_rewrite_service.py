from __future__ import annotations

import json
from typing import Any

from app.clients.llm_client import LLM_NOT_CONFIGURED, create_llm_client
from app.common import error_code
from app.common.exceptions import AppException
from app.dto.ai_dto import CopyRewriteRequestDTO

DEFAULT_VERSION_COUNT = 3


def rewrite_copy(request: CopyRewriteRequestDTO) -> dict[str, object]:
    if request.sourceTextType == "platform_description" and not request.allowPlatformText:
        raise AppException(
            error_code.SOURCE_TEXT_NOT_READY,
            "当前只有平台文案，请先提取视频口播，或确认使用平台文案改写。",
            status_code=400,
            data={"errorType": "source_text_not_ready"},
        )

    llm = create_llm_client()
    if not llm.is_configured():
        raise AppException(
            error_code.INTERNAL_ERROR,
            "AI 改写服务未配置，请先配置模型服务。",
            status_code=500,
            data={"errorType": LLM_NOT_CONFIGURED},
        )

    messages = _build_rewrite_messages(request)
    text = llm.chat(messages, temperature=0.7, max_tokens=1600)
    results = _parse_rewrite_results(text, DEFAULT_VERSION_COUNT)
    return {
        "results": results,
        "rawText": text,
    }


def _build_rewrite_messages(request: CopyRewriteRequestDTO) -> list[dict[str, str]]:
    instruction = request.instruction or "保留核心信息，改成更自然的真人口播表达。"
    template = request.template or "默认"
    return [
        {
            "role": "system",
            "content": (
                "你是 INLOOK Studio 的中文短视频口播文案改写助手。"
                "只做文案改写，不编造事实，不输出营销废话，不返回解释。"
                "请返回 JSON，格式为 {\"results\":[{\"title\":\"...\",\"tag\":\"...\",\"content\":\"...\"}]}。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请基于下面原始文案输出 3 个版本。\n"
                "默认要求：\n"
                "- 适合抖音 30 秒到 60 秒口播；\n"
                "- 300 字左右；\n"
                "- 真实自然；\n"
                "- 像真人口播，不要太营销；\n"
                "- 保留原意；\n"
                "- 不编造事实；\n"
                "- 只输出 JSON，不输出解释。\n\n"
                f"模板方向：{template}\n"
                f"改写要求：{instruction}\n\n"
                f"原文案：\n{request.sourceText}"
            ),
        },
    ]


def _parse_rewrite_results(text: str, version_count: int) -> list[dict[str, str]]:
    parsed = _try_load_json(text)
    raw_results = parsed.get("results") if isinstance(parsed, dict) else None
    if isinstance(raw_results, list):
        results = []
        for index, item in enumerate(raw_results[:version_count]):
            if not isinstance(item, dict):
                continue
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            results.append(
                {
                    "id": _result_id(index),
                    "title": str(item.get("title") or f"版本 {_result_id(index)}").strip(),
                    "tag": str(item.get("tag") or "AI 改写").strip(),
                    "content": content,
                }
            )
        if results:
            return results

    # 如果模型没有按 JSON 返回，仍然只返回模型真实文本，不构造假内容。
    return [
        {
            "id": "A",
            "title": "模型返回",
            "tag": "AI 改写",
            "content": text.strip(),
        }
    ]


def _try_load_json(text: str) -> Any:
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = [line for line in candidate.splitlines() if not line.strip().startswith("```")]
        candidate = "\n".join(lines).strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def _result_id(index: int) -> str:
    return chr(ord("A") + index)
