from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import settings


def _mask_token(value: str) -> str:
    token = (value or "").strip()
    if not token:
        return ""
    if len(token) <= 12:
        return f"{token[:3]}***{token[-2:]}"
    return f"{token[:6]}***{token[-4:]}"


def _redact_json(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in {"secret_key", "secretkey"}:
                redacted[key] = "***"
            elif lowered in {"access_token", "authorization"}:
                redacted[key] = _mask_token(str(item))
            else:
                redacted[key] = _redact_json(item)
        return redacted
    if isinstance(value, list):
        return [_redact_json(item) for item in value]
    return value


class ChanjingApiError(Exception):
    def __init__(
        self,
        message: str,
        *,
        http_status: int = 0,
        code: int | None = None,
        msg: str = "",
        trace_id: str = "",
        response_json: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.code = code
        self.msg = msg or message
        self.trace_id = trace_id
        self.response_json = response_json or {}


class ChanjingClient:
    def __init__(self, *, timeout_seconds: float = 60.0) -> None:
        self.timeout_seconds = timeout_seconds
        self.base_url = settings.get_chanjing_api_base_url().rstrip("/")
        self.base_path = "/" + settings.get_chanjing_api_base_path().strip("/")
        self.access_token_header = settings.get_chanjing_access_token_header()
        self._access_token = ""
        self.last_exchange: dict[str, Any] = {}
        self.last_transfer: dict[str, Any] = {}
        self._client = httpx.Client(timeout=self.timeout_seconds, follow_redirects=True)

    def set_access_token(self, access_token: str) -> None:
        self._access_token = (access_token or "").strip()

    def get_access_token(self, app_id: str, secret_key: str) -> dict[str, Any]:
        return self._request("POST", "/access_token", json_body={"app_id": app_id, "secret_key": secret_key}, auth_required=False)

    def create_upload_url(self, service: str, name: str) -> dict[str, Any]:
        return self._request("GET", "/common/create_upload_url", params={"service": service, "name": name})

    def upload_file_to_signed_url(self, sign_url: str, local_path: str, mime_type: str | None = None) -> None:
        path = Path(local_path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise ChanjingApiError(f"待上传文件不存在: {path}")
        resolved_mime = mime_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        headers = {"Content-Type": resolved_mime}
        self.last_transfer = {
            "type": "upload",
            "request": {
                "method": "PUT",
                "url": sign_url,
                "headers": headers,
                "local_path": str(path),
                "mime_type": resolved_mime,
            }
        }
        try:
            with path.open("rb") as file:
                response = self._client.put(sign_url, content=file, headers=headers)
        except httpx.TimeoutException as exc:
            raise ChanjingApiError("上传签名地址超时") from exc
        except httpx.HTTPError as exc:
            raise ChanjingApiError(f"上传签名地址失败: {exc}") from exc
        self.last_transfer["response"] = {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "text": response.text[:2000],
        }
        if response.status_code >= 400:
            raise ChanjingApiError(f"上传签名地址失败: HTTP {response.status_code}", http_status=response.status_code)

    def file_list(self, service: str, page: int = 1, page_size: int = 20, file_id: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"service": service, "page": page, "page_size": page_size}
        if file_id:
            payload["id"] = file_id
        return self._request("POST", "/common/file_list", json_body=payload)

    def file_detail(self, file_id: str) -> dict[str, Any]:
        return self._request("GET", "/common/file_detail", params={"id": file_id})

    def delete_file(self, file_id: str) -> dict[str, Any]:
        return self._request("POST", "/common/delete_file", json_body={"id": file_id})

    def create_customised_person(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/create_customised_person", json_body=payload)

    def get_customised_person(self, person_id: str) -> dict[str, Any]:
        return self._request("GET", "/customised_person", params={"id": person_id})

    def list_customised_person(self, page: int = 1, page_size: int = 20, person_id: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"page": page, "page_size": page_size}
        if person_id:
            payload["id"] = person_id
        return self._request("POST", "/list_customised_person", json_body=payload)

    def delete_customised_person(self, person_id: str) -> dict[str, Any]:
        return self._request("POST", "/delete_customised_person", json_body={"id": person_id})

    def list_common_dp(
        self,
        page: int = 1,
        size: int = 20,
        sort: str | None = None,
        tag_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"page": page, "size": size}
        if sort:
            params["sort"] = sort
        if tag_ids:
            params["tag_ids"] = ",".join(str(item) for item in tag_ids)
        return self._request("GET", "/list_common_dp", params=params)

    def list_common_audio(self, page: int = 1, size: int = 20) -> dict[str, Any]:
        return self._request("GET", "/list_common_audio", params={"page": page, "size": size})

    def create_video(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/create_video", json_body=payload)

    def get_video(self, video_id: str) -> dict[str, Any]:
        return self._request("GET", "/video", params={"id": video_id})

    def video_list(self, page: int = 1, page_size: int = 20) -> dict[str, Any]:
        return self._request("POST", "/video_list", json_body={"page": page, "page_size": page_size})

    def download_video(self, video_url: str, output_path: str) -> str:
        target = Path(output_path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        self.last_transfer = {
            "type": "download",
            "request": {"method": "GET", "url": video_url, "output_path": str(target)},
        }
        try:
            with self._client.stream("GET", video_url) as response:
                if response.status_code >= 400:
                    raise ChanjingApiError(f"下载视频失败: HTTP {response.status_code}", http_status=response.status_code)
                with target.open("wb") as file:
                    for chunk in response.iter_bytes():
                        if chunk:
                            file.write(chunk)
                self.last_transfer["response"] = {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "output_path": str(target),
                }
        except httpx.TimeoutException as exc:
            raise ChanjingApiError("下载视频超时") from exc
        except httpx.HTTPError as exc:
            raise ChanjingApiError(f"下载视频失败: {exc}") from exc
        return str(target)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        auth_required: bool = True,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{self.base_path}{path}"
        headers = {"Accept": "application/json"}
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        if auth_required:
            if not self._access_token:
                raise ChanjingApiError("access_token 缺失，无法调用蝉镜业务接口")
            headers[self.access_token_header] = self._access_token
        self.last_exchange = {
            "request": {
                "method": method,
                "url": url if not params else f"{url}?{urlencode(params, doseq=True)}",
                "headers": _redact_json(headers),
                "params": _redact_json(params or {}),
                "json": _redact_json(json_body or {}),
            }
        }
        try:
            response = self._client.request(method, url, params=params, json=json_body, headers=headers)
        except httpx.TimeoutException as exc:
            raise ChanjingApiError(f"请求蝉镜接口超时: {path}") from exc
        except httpx.HTTPError as exc:
            raise ChanjingApiError(f"请求蝉镜接口失败: {path}: {exc}") from exc

        response_text = response.text
        try:
            body = response.json()
        except json.JSONDecodeError as exc:
            self.last_exchange["response"] = {"status_code": response.status_code, "text": response_text[:4000]}
            raise ChanjingApiError(
                f"蝉镜接口返回非 JSON: {path}",
                http_status=response.status_code,
                response_json={},
            ) from exc

        trace_id = str(body.get("trace_id") or "")
        self.last_exchange["response"] = {
            "status_code": response.status_code,
            "json": _redact_json(body),
            "trace_id": trace_id,
        }
        if response.status_code != 200:
            raise ChanjingApiError(
                f"蝉镜接口 HTTP 异常: {path}",
                http_status=response.status_code,
                code=body.get("code"),
                msg=str(body.get("msg") or ""),
                trace_id=trace_id,
                response_json=body,
            )
        code = body.get("code")
        if code != 0:
            raise ChanjingApiError(
                f"蝉镜接口业务失败: {path}",
                http_status=response.status_code,
                code=code if isinstance(code, int) else None,
                msg=str(body.get("msg") or ""),
                trace_id=trace_id,
                response_json=body,
            )
        return body


chanjing_client = ChanjingClient()
