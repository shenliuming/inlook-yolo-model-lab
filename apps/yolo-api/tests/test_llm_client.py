from __future__ import annotations

import json
import os
import unittest
from unittest import mock

from app.clients.llm_client import LLMClient
from app.common.exceptions import AppException


class LLMClientTest(unittest.TestCase):
    def tearDown(self) -> None:
        for key in [
            "LLM_PROVIDER",
            "LLM_BASE_URL",
            "LLM_API_KEY",
            "LLM_MODEL",
            "LLM_TIMEOUT_SECONDS",
        ]:
            os.environ.pop(key, None)

    def test_status_unavailable_without_env(self) -> None:
        client = LLMClient()

        self.assertFalse(client.is_configured())
        self.assertEqual(
            client.status(),
            {
                "available": False,
                "provider": None,
                "model": None,
                "message": "AI 服务未配置",
            },
        )
        with self.assertRaises(AppException) as context:
            client.chat([{"role": "user", "content": "你好"}])
        self.assertEqual(context.exception.data["errorType"], "llm_not_configured")

    def test_chat_uses_openai_compatible_payload_and_returns_text(self) -> None:
        os.environ["LLM_PROVIDER"] = "openai_compatible"
        os.environ["LLM_BASE_URL"] = "https://example.test/v1"
        os.environ["LLM_API_KEY"] = "test-key"
        os.environ["LLM_MODEL"] = "test-model"
        os.environ["LLM_TIMEOUT_SECONDS"] = "12"

        body = {
            "choices": [
                {
                    "message": {
                        "content": "可以，模型已连接。",
                    }
                }
            ]
        }

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self) -> bytes:
                return json.dumps(body).encode("utf-8")

        with mock.patch("urllib.request.urlopen", return_value=FakeResponse()) as opener:
            client = LLMClient()
            text = client.chat([{"role": "user", "content": "你好"}], temperature=0.2, max_tokens=300)

        self.assertEqual(text, "可以，模型已连接。")
        request = opener.call_args.args[0]
        self.assertEqual(request.full_url, "https://example.test/v1/chat/completions")
        self.assertEqual(request.headers["Authorization"], "Bearer test-key")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "test-model")
        self.assertEqual(payload["temperature"], 0.2)
        self.assertEqual(payload["max_tokens"], 300)


if __name__ == "__main__":
    unittest.main()
