from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from app.common import error_code
from app.common.exceptions import AppException
from app.config import settings


LLM_NOT_CONFIGURED = "llm_not_configured"
LLM_REQUEST_FAILED = "llm_request_failed"
LLM_TIMEOUT = "llm_timeout"
LLM_INVALID_RESPONSE = "llm_invalid_response"


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    base_url: str
    api_key: str
    model: str
    timeout_seconds: int


class LLMClient:
    def __init__(self) -> None:
        self.config = self._load_config()

    def _load_config(self) -> LLMConfig:
        return LLMConfig(
            provider=settings.get_llm_provider(),
            base_url=settings.get_llm_base_url(),
            api_key=settings.get_llm_api_key(),
            model=settings.get_llm_model(),
            timeout_seconds=settings.get_llm_timeout_seconds(),
        )

    def is_configured(self) -> bool:
        return (
            self.config.provider == "openai_compatible"
            and bool(self.config.base_url)
            and bool(self.config.api_key)
            and bool(self.config.model)
        )

    def status(self) -> dict[str, object | None]:
        if not self.is_configured():
            return {
                "available": False,
                "provider": None,
                "model": None,
                "message": "AI 服务未配置",
            }
        return {
            "available": True,
            "provider": self.config.provider,
            "model": self.config.model,
        }

    def chat(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 1200) -> str:
        if not self.is_configured():
            raise self._error(LLM_NOT_CONFIGURED, "AI 服务未配置，请先配置模型服务。")

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        request = urllib.request.Request(
            self._chat_completions_url(),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise self._error(LLM_REQUEST_FAILED, f"AI 服务请求失败：HTTP {exc.code}") from exc
        except TimeoutError as exc:
            raise self._error(LLM_TIMEOUT, "AI 服务请求超时，请稍后重试。") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise self._error(LLM_TIMEOUT, "AI 服务请求超时，请稍后重试。") from exc
            raise self._error(LLM_REQUEST_FAILED, "AI 服务请求失败，请检查模型服务配置。") from exc

        try:
            body: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise self._error(LLM_INVALID_RESPONSE, "AI 服务返回格式不正确。") from exc

        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise self._error(LLM_INVALID_RESPONSE, "AI 服务未返回有效内容。")

        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise self._error(LLM_INVALID_RESPONSE, "AI 服务返回内容为空。")
        return content.strip()

    def _chat_completions_url(self) -> str:
        return f"{self.config.base_url.rstrip('/')}/chat/completions"

    @staticmethod
    def _error(error_type: str, message: str) -> AppException:
        return AppException(
            error_code.INTERNAL_ERROR,
            message,
            status_code=500,
            data={"errorType": error_type},
        )


def create_llm_client() -> LLMClient:
    return LLMClient()
