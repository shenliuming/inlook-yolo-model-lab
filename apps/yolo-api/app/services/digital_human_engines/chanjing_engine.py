from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from app.clients.chanjing_client import ChanjingApiError, ChanjingClient, chanjing_client
from app.config import settings

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov"}
FILE_READY_STATUS = 1
FILE_WAITING_STATUS = 0
FILE_FAILED_STATUSES = {98, 99, 100}


def estimate_duration_seconds(text: str, language: str = "cn") -> float:
    units = {
        "cn": 234.0,
        "zh": 234.0,
        "en": 365.0,
        "ja": 201.0,
        "jp": 201.0,
        "ko": 574.0,
        "de": 379.0,
        "fr": 345.0,
    }
    raw = (text or "").strip()
    if not raw:
        return 0.0
    per_thousand = units.get((language or "cn").strip().lower(), 234.0)
    return round(len(raw) * per_thousand / 1000.0, 2)


class ChanjingDigitalHumanEngine:
    def __init__(self, client: ChanjingClient | None = None) -> None:
        self.client = client or chanjing_client
        self.app_id = settings.get_chanjing_app_id()
        self.secret_key = settings.get_chanjing_secret_key()
        self.default_model = settings.get_chanjing_default_model()
        self.default_screen_width = settings.get_chanjing_default_screen_width()
        self.default_screen_height = settings.get_chanjing_default_screen_height()
        self.token_margin_seconds = settings.get_chanjing_token_expire_margin_seconds()
        self.audio_upload_services = settings.get_chanjing_audio_upload_services()
        self._access_token = ""
        self._expire_at = 0.0

    def ensure_access_token(self, force_refresh: bool = False) -> str:
        if not self.app_id or not self.secret_key:
            raise ChanjingApiError("缺少 CHANJING_APP_ID 或 CHANJING_SECRET_KEY")
        now = time.time()
        if not force_refresh and self._access_token and now < self._expire_at - self.token_margin_seconds:
            self.client.set_access_token(self._access_token)
            return self._access_token
        body = self.client.get_access_token(self.app_id, self.secret_key)
        data = body.get("data") if isinstance(body.get("data"), dict) else {}
        token = str(data.get("access_token") or "").strip()
        expire_in = int(data.get("expire_in") or 0)
        if not token:
            raise ChanjingApiError(
                "获取 access_token 失败：响应缺少 access_token",
                code=body.get("code") if isinstance(body.get("code"), int) else None,
                msg=str(body.get("msg") or ""),
                trace_id=str(body.get("trace_id") or ""),
                response_json=body,
            )
        self._access_token = token
        self._expire_at = now + max(expire_in, self.token_margin_seconds + 60)
        self.client.set_access_token(token)
        return token

    def upload_file(self, local_path: str, *, service: str) -> dict[str, Any]:
        path = Path(local_path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise ChanjingApiError(f"待上传文件不存在: {path}")
        self.ensure_access_token()
        upload_body = self._call_with_token_refresh(self.client.create_upload_url, service=service, name=path.name)
        data = upload_body.get("data") if isinstance(upload_body.get("data"), dict) else {}
        sign_url = str(data.get("sign_url") or data.get("upload_url") or "").strip()
        file_id = str(data.get("id") or data.get("file_id") or "").strip()
        mime_type = str(data.get("mime_type") or "").strip() or None
        if not sign_url:
            raise ChanjingApiError(
                "创建上传地址失败：响应缺少 sign_url",
                code=upload_body.get("code") if isinstance(upload_body.get("code"), int) else None,
                msg=str(upload_body.get("msg") or ""),
                trace_id=str(upload_body.get("trace_id") or ""),
                response_json=upload_body,
            )
        self.client.upload_file_to_signed_url(sign_url, str(path), mime_type=mime_type)
        return {
            "local_video_path": str(path),
            "file_id": file_id,
            "sign_url": sign_url,
            "mime_type": mime_type,
            "service": service,
            "response": upload_body,
        }

    def upload_custom_person_video(self, local_video_path: str) -> dict[str, Any]:
        path = Path(local_video_path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise ChanjingApiError(f"训练视频不存在: {path}")
        if path.suffix.lower() not in ALLOWED_VIDEO_EXTENSIONS:
            raise ChanjingApiError("训练视频格式不支持，仅支持 mp4/webm/mov")
        return self.upload_file(str(path), service="customised_person")

    def upload_audio_for_video(self, local_audio_path: str) -> dict[str, Any]:
        path = Path(local_audio_path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise ChanjingApiError(f"数字人口播音频不存在: {path}")

        errors: list[str] = []
        for service in self.audio_upload_services:
            try:
                result = self.upload_file(str(path), service=service)
                self.wait_file_ready(str(result.get("file_id") or ""), service=service)
                return result
            except ChanjingApiError as exc:
                errors.append(f"{service}: {exc}")
        raise ChanjingApiError("上传数字人口播音频失败: " + " | ".join(errors))

    def wait_file_ready(self, file_id: str, service: str = "customised_person", timeout_seconds: int = 90) -> dict[str, Any]:
        deadline = time.time() + timeout_seconds
        last_body: dict[str, Any] | None = None
        while time.time() < deadline:
            detail_body = self._call_with_token_refresh(self.client.file_detail, file_id=file_id)
            last_body = detail_body
            data = detail_body.get("data")
            if isinstance(data, dict) and data:
                status = self._extract_file_status(data)
                if status == FILE_READY_STATUS:
                    return detail_body
                if status in FILE_FAILED_STATUSES:
                    raise ChanjingApiError(
                        "上传文件处理失败",
                        code=detail_body.get("code") if isinstance(detail_body.get("code"), int) else None,
                        msg=self._extract_reason(data) or str(detail_body.get("msg") or ""),
                        trace_id=str(detail_body.get("trace_id") or ""),
                        response_json=detail_body,
                    )
            list_body = self._call_with_token_refresh(self.client.file_list, service=service, file_id=file_id, page=1, page_size=20)
            last_body = list_body
            item = self._find_item_by_id(list_body.get("data"), file_id)
            if item is not None:
                status = self._extract_file_status(item)
                if status == FILE_READY_STATUS:
                    return list_body
                if status in FILE_FAILED_STATUSES:
                    raise ChanjingApiError(
                        "上传文件处理失败",
                        code=list_body.get("code") if isinstance(list_body.get("code"), int) else None,
                        msg=self._extract_reason(item) or str(list_body.get("msg") or ""),
                        trace_id=str(list_body.get("trace_id") or ""),
                        response_json=list_body,
                    )
            time.sleep(3)
        raise ChanjingApiError(
            "等待上传文件可用超时",
            code=last_body.get("code") if isinstance((last_body or {}).get("code"), int) else None,
            msg=str((last_body or {}).get("msg") or ""),
            trace_id=str((last_body or {}).get("trace_id") or ""),
            response_json=last_body or {},
        )

    def create_custom_person_training_job(
        self,
        name: str,
        file_id: str,
        train_type: str = "both",
        callback: str = "",
        error_skip: bool = False,
        resolution_rate: int = 0,
        language: str = "cn",
        version: str = "1.0",
        auth_text: str | None = None,
        auth_video_file_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": name,
            "file_id": file_id,
            "train_type": train_type,
            "callback": callback,
            "error_skip": bool(error_skip),
            "resolution_rate": resolution_rate,
            "language": language,
            "version": version,
        }
        if auth_text:
            payload["auth_text"] = auth_text
        if auth_video_file_id:
            payload["auth_video_file_id"] = auth_video_file_id
        self.ensure_access_token()
        return self._call_with_token_refresh(self.client.create_customised_person, payload=payload)

    def poll_custom_person(self, person_id: str) -> dict[str, Any]:
        self.ensure_access_token()
        return self._call_with_token_refresh(self.client.get_customised_person, person_id=person_id)

    def create_video_job(
        self,
        person_id: str,
        audio_type: str,
        text: str | None = None,
        wav_url: str | None = None,
        audio_file_id: str | None = None,
        audio_man_id: str | None = None,
        figure_type: str | None = None,
        screen_width: int = 1080,
        screen_height: int = 1920,
        person_x: int = 0,
        person_y: int = 0,
        person_width: int | None = None,
        person_height: int | None = None,
        model: int = 0,
        resolution_rate: int = 0,
        add_compliance_watermark: bool = False,
        hide_subtitle: bool = False,
        bg_color: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "screen_width": screen_width or self.default_screen_width,
            "screen_height": screen_height or self.default_screen_height,
            "model": model if model is not None else self.default_model,
            "resolution_rate": resolution_rate,
            "add_compliance_watermark": bool(add_compliance_watermark),
            "hide_subtitle": bool(hide_subtitle),
            "person": {
                "id": person_id,
                "x": person_x,
                "y": person_y,
                "width": person_width or screen_width or self.default_screen_width,
                "height": person_height or screen_height or self.default_screen_height,
                "backway": 1,
            },
        }
        if figure_type:
            payload["person"]["figure_type"] = figure_type
        if bg_color:
            payload["bg_color"] = bg_color

        if audio_type == "audio":
            audio: dict[str, Any] = {"type": "audio", "volume": 100, "language": "cn"}
            if wav_url:
                audio["wav_url"] = wav_url
            elif audio_file_id:
                audio["file_id"] = audio_file_id
            else:
                raise ChanjingApiError("audio 模式下必须提供 wav_url 或 audio_file_id")
        elif audio_type == "tts":
            if not text or not text.strip():
                raise ChanjingApiError("tts 模式下必须提供 text")
            if not audio_man_id:
                raise ChanjingApiError("tts 模式下必须提供 audio_man_id")
            audio = {
                "type": "tts",
                "volume": 100,
                "language": "cn",
                "tts": {
                    "text": [text],
                    "audio_man": audio_man_id,
                    "speed": 1,
                    "pitch": 0,
                },
            }
        else:
            raise ChanjingApiError("audio_type 仅支持 audio 或 tts")
        payload["audio"] = audio

        self.ensure_access_token()
        return self._call_with_token_refresh(self.client.create_video, payload=payload)

    def poll_video(self, video_id: str) -> dict[str, Any]:
        self.ensure_access_token()
        return self._call_with_token_refresh(self.client.get_video, video_id=video_id)

    def download_result(self, video_url: str, output_path: str) -> str:
        if not video_url:
            raise ChanjingApiError("视频生成成功但 video_url 为空")
        return self.client.download_video(video_url, output_path)

    def _call_with_token_refresh(self, func: Any, **kwargs: Any) -> dict[str, Any]:
        self.ensure_access_token()
        try:
            return func(**kwargs)
        except ChanjingApiError as exc:
            if self._is_token_invalid_error(exc):
                self.ensure_access_token(force_refresh=True)
                return func(**kwargs)
            raise

    @staticmethod
    def _is_token_invalid_error(exc: ChanjingApiError) -> bool:
        lowered = (exc.msg or str(exc)).lower()
        return exc.code in {401, 40100} or "token" in lowered and any(word in lowered for word in ("invalid", "expire", "expired", "失效", "过期"))

    @staticmethod
    def _extract_file_status(data: dict[str, Any]) -> int | None:
        raw = data.get("status")
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _find_item_by_id(data: Any, target_id: str) -> dict[str, Any] | None:
        if isinstance(data, dict):
            items = data.get("list") or data.get("items") or data.get("records") or []
        elif isinstance(data, list):
            items = data
        else:
            items = []
        for item in items:
            if isinstance(item, dict) and str(item.get("id") or item.get("file_id") or "") == target_id:
                return item
        return None

    @staticmethod
    def _extract_reason(data: dict[str, Any]) -> str:
        for key in ("err_reason", "reason", "msg", "message"):
            value = str(data.get(key) or "").strip()
            if value:
                return value
        return ""


chanjing_engine = ChanjingDigitalHumanEngine()
