from __future__ import annotations

import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from app.main import app
from app.dto.ai_dto import CopyRewriteRequestDTO
from app.services.copy_rewrite_service import _build_rewrite_messages


class AiControllerTest(unittest.TestCase):
    def setUp(self) -> None:
        for key in [
            "LLM_PROVIDER",
            "LLM_BASE_URL",
            "LLM_API_KEY",
            "LLM_MODEL",
            "LLM_TIMEOUT_SECONDS",
        ]:
            os.environ.pop(key, None)
        self.client = TestClient(app)

    def test_ai_status_unavailable_without_llm_env(self) -> None:
        response = self.client.get("/api/v1/ai/status")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["data"]["available"], False)
        self.assertIsNone(payload["data"]["provider"])
        self.assertIsNone(payload["data"]["model"])
        self.assertEqual(payload["data"]["message"], "AI 服务未配置")

    def test_copy_rewrite_requires_configured_llm(self) -> None:
        response = self.client.post(
            "/api/v1/copy/rewrite",
            json={
                "sourceText": "这是一段需要改写的口播文案。",
                "sourceTextType": "video_transcript",
                "instruction": "更自然一点",
            },
        )

        self.assertEqual(response.status_code, 500)
        payload = response.json()
        self.assertEqual(payload["code"], 50001)
        self.assertEqual(payload["message"], "AI 改写服务未配置，请先配置模型服务。")
        self.assertEqual(payload["data"]["errorType"], "llm_not_configured")

    def test_copy_rewrite_blocks_platform_description_without_confirmation(self) -> None:
        response = self.client.post(
            "/api/v1/copy/rewrite",
            json={
                "sourceText": "ChatGPT Plus 免费了？先别激动 #chatgpt",
                "sourceTextType": "platform_description",
                "allowPlatformText": False,
                "instruction": "更自然一点",
            },
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["code"], 40001)
        self.assertEqual(payload["message"], "当前只有平台文案，请先提取视频口播，或确认使用平台文案改写。")
        self.assertEqual(payload["data"]["errorType"], "source_text_not_ready")

    def test_copy_rewrite_allows_confirmed_platform_description(self) -> None:
        class FakeLLMClient:
            def is_configured(self) -> bool:
                return True

            def chat(self, *_args, **_kwargs) -> str:
                return '{"results":[{"title":"版本 A","tag":"平台文案改写","content":"改写后的真实模型文本"}]}'

        with mock.patch("app.services.copy_rewrite_service.create_llm_client", return_value=FakeLLMClient()):
            response = self.client.post(
                "/api/v1/copy/rewrite",
                json={
                    "sourceText": "ChatGPT Plus 免费了？先别激动 #chatgpt",
                    "sourceTextType": "platform_description",
                    "allowPlatformText": True,
                    "instruction": "更自然一点",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["data"]["results"][0]["content"], "改写后的真实模型文本")

    def test_rewrite_prompt_uses_default_mvp_constraints(self) -> None:
        messages = _build_rewrite_messages(
            CopyRewriteRequestDTO(
                sourceText="原始口播文案",
                sourceTextType="video_transcript",
                instruction="更像普通人分享",
                template="普通人分享",
            )
        )
        prompt = messages[1]["content"]

        self.assertIn("适合抖音 30 秒到 60 秒口播", prompt)
        self.assertIn("300 字左右", prompt)
        self.assertIn("真实自然", prompt)
        self.assertIn("输出 3 个版本", prompt)
        self.assertIn("模板方向：普通人分享", prompt)
        self.assertIn("改写要求：更像普通人分享", prompt)


if __name__ == "__main__":
    unittest.main()
