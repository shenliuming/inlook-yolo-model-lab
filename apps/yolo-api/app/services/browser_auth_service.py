from __future__ import annotations

import shutil
import threading
import time
from datetime import datetime
from pathlib import Path

from app.clients.browser_client import PLATFORM_CONFIG, browser_client
from app.common import error_code
from app.common.exceptions import AppException
from app.config.paths import BROWSER_PROFILES_DIR
from app.tasks.task_store import read_json, write_json

STATUS_UNAUTHORIZED = "unauthorized"
STATUS_AUTHORIZING = "authorizing"
STATUS_AUTHORIZED = "authorized"
STATUS_EXPIRED = "expired"
STATUS_FAILED = "failed"

_monitor_threads: dict[str, threading.Thread] = {}
_monitor_lock = threading.RLock()


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _ensure_platform(platform: str) -> str:
    value = (platform or "").strip().lower()
    if value not in PLATFORM_CONFIG:
        raise AppException(error_code.BAD_REQUEST, "当前仅支持抖音和B站授权。", status_code=400)
    return value


def _profile_dir(platform: str) -> Path:
    return BROWSER_PROFILES_DIR / platform


def _status_path(platform: str) -> Path:
    return _profile_dir(platform) / "auth_status.json"


def _default_status(platform: str) -> dict:
    profile_path = _profile_dir(platform)
    return {
        "platform": platform,
        "status": STATUS_UNAUTHORIZED,
        "profilePath": str(profile_path),
        "updatedAt": _now_text(),
        "lastCheckAt": _now_text(),
        "message": "未授权",
    }


def _write_status(platform: str, status: str, message: str) -> dict:
    current = _read_status(platform)
    payload = {
        **current,
        "platform": platform,
        "status": status,
        "profilePath": str(_profile_dir(platform)),
        "updatedAt": _now_text(),
        "lastCheckAt": _now_text(),
        "message": message,
    }
    write_json(_status_path(platform), payload)
    return payload


def _read_status(platform: str) -> dict:
    path = _status_path(platform)
    if not path.exists():
        return _default_status(platform)
    try:
        payload = read_json(path)
    except Exception:
        return _default_status(platform)
    return {
        **_default_status(platform),
        **payload,
    }


def _monitor_authorization(platform: str) -> None:
    try:
        for _ in range(300):
            time.sleep(2)
            signal = browser_client.get_auth_status(platform)
            if signal.get("authorized"):
                _write_status(platform, STATUS_AUTHORIZED, "已授权")
                return
        _write_status(platform, STATUS_FAILED, "授权超时，请重新打开授权窗口。")
    except AppException as exc:
        _write_status(platform, STATUS_FAILED, exc.message)
    except Exception as exc:
        _write_status(platform, STATUS_FAILED, f"授权检测失败：{exc}")
    finally:
        with _monitor_lock:
            _monitor_threads.pop(platform, None)


def start_browser_authorization(platform: str) -> dict:
    platform = _ensure_platform(platform)
    _profile_dir(platform).mkdir(parents=True, exist_ok=True)
    _write_status(platform, STATUS_AUTHORIZING, f"已打开{('抖音' if platform == 'douyin' else 'B站')}登录窗口，请在浏览器中完成登录。")
    browser_client.open_login_page(platform)
    with _monitor_lock:
        existing = _monitor_threads.get(platform)
        if existing is None or not existing.is_alive():
            thread = threading.Thread(target=_monitor_authorization, args=(platform,), daemon=True)
            _monitor_threads[platform] = thread
            thread.start()
    return _read_status(platform)


def get_browser_auth_status(platform: str) -> dict:
    platform = _ensure_platform(platform)
    payload = _read_status(platform)
    signal = browser_client.get_auth_status(platform)
    if signal.get("authorized") and payload.get("status") != STATUS_AUTHORIZED:
        payload = _write_status(platform, STATUS_AUTHORIZED, "已授权")
    elif payload.get("status") == STATUS_AUTHORIZING:
        payload["lastCheckAt"] = _now_text()
        write_json(_status_path(platform), payload)
    return payload


def clear_browser_authorization(platform: str) -> dict:
    platform = _ensure_platform(platform)
    browser_client.close_browser(platform)
    profile_dir = _profile_dir(platform)
    if profile_dir.exists():
        shutil.rmtree(profile_dir, ignore_errors=True)
    profile_dir.mkdir(parents=True, exist_ok=True)
    return _write_status(platform, STATUS_UNAUTHORIZED, "授权已清除")


def ensure_platform_authorized(platform: str) -> None:
    payload = get_browser_auth_status(platform)
    if payload.get("status") != STATUS_AUTHORIZED:
        raise AppException(
            error_code.INTERNAL_ERROR,
            f"请先授权{('抖音' if platform == 'douyin' else 'B站')}账号，或上传本地视频。",
            status_code=400,
            data={
                "sourceType": platform,
                "errorType": "platform_not_authorized",
            },
        )


def mark_platform_authorization_expired(platform: str, message: str) -> None:
    platform = _ensure_platform(platform)
    _write_status(platform, STATUS_EXPIRED, message or "授权已失效，请重新授权。")
