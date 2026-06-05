from __future__ import annotations

import json
from urllib import error as urllib_error
from urllib import request as urllib_request

from app.common import error_code
from app.common.exceptions import AppException
from app.config import settings


class CopyPilotClient:
    def __init__(self) -> None:
        self.api_url = settings.get_copy_pilot_api_url()
        self.timeout = settings.get_copy_pilot_timeout()

    def extract(self, url: str, source_type: str = "auto") -> dict:
        payload = {
            "url": str(url or "").strip(),
            "type": str(source_type or "auto").strip() or "auto",
        }
        if not payload["url"]:
            raise AppException(
                error_code.INTERNAL_ERROR,
                "素材提取失败：CopyPilot 请求缺少视频链接。",
                status_code=500,
                data={"errorType": "extractor_failed"},
            )

        body = json.dumps(payload).encode("utf-8")
        request = urllib_request.Request(
            self.api_url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "User-Agent": "INLOOK-Studio/1.0",
                "Accept": "application/json",
            },
        )
        try:
            with urllib_request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib_error.HTTPError as exc:
            raise AppException(
                error_code.INTERNAL_ERROR,
                f"素材提取失败：CopyPilot 接口调用失败，具体原因：HTTP {exc.code}",
                status_code=500,
                data={"errorType": "extractor_failed"},
            ) from exc
        except urllib_error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            raise AppException(
                error_code.INTERNAL_ERROR,
                f"素材提取失败：CopyPilot 接口调用失败，具体原因：{reason}",
                status_code=500,
                data={"errorType": "extractor_failed"},
            ) from exc
        except TimeoutError as exc:
            raise AppException(
                error_code.INTERNAL_ERROR,
                "素材提取失败：CopyPilot 接口调用超时。",
                status_code=500,
                data={"errorType": "extractor_failed"},
            ) from exc
        except Exception as exc:
            raise AppException(
                error_code.INTERNAL_ERROR,
                f"素材提取失败：CopyPilot 接口调用失败，具体原因：{exc}",
                status_code=500,
                data={"errorType": "extractor_failed"},
            ) from exc

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AppException(
                error_code.INTERNAL_ERROR,
                "素材提取失败：CopyPilot 返回非 JSON 数据。",
                status_code=500,
                data={"errorType": "extractor_failed"},
            ) from exc

        if not isinstance(payload, dict):
            raise AppException(
                error_code.INTERNAL_ERROR,
                "素材提取失败：CopyPilot 返回结构异常。",
                status_code=500,
                data={"errorType": "extractor_failed"},
            )
        if payload.get("ok") is not True:
            message = str(payload.get("message") or payload.get("error") or "CopyPilot 返回失败。").strip()
            raise AppException(
                error_code.INTERNAL_ERROR,
                f"素材提取失败：CopyPilot 返回失败，具体原因：{message}",
                status_code=500,
                data={"errorType": "extractor_failed"},
            )
        data = payload.get("data")
        aweme_detail = data.get("aweme_detail") if isinstance(data, dict) else None
        if not isinstance(aweme_detail, dict):
            raise AppException(
                error_code.INTERNAL_ERROR,
                "素材提取失败：CopyPilot 返回缺少 aweme_detail。",
                status_code=500,
                data={"errorType": "extractor_failed"},
            )
        return payload


copy_pilot_client = CopyPilotClient()
