from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from app.common import error_code
from app.common.exceptions import AppException
from app.config.paths import BROWSER_PROFILES_DIR

PLATFORM_CONFIG: dict[str, dict[str, str]] = {
    "douyin": {
        "loginUrl": "https://www.douyin.com/",
        "domain": "douyin.com",
    },
    "bilibili": {
        "loginUrl": "https://www.bilibili.com/",
        "domain": "bilibili.com",
    },
}

RESPONSE_HINTS: dict[str, tuple[str, ...]] = {
    "douyin": ("aweme/detail", "web/aweme/detail", "iteminfo", "video"),
    "bilibili": ("x/web-interface/view", "x/player/wbi/playurl", "x/player/playurl"),
}


@dataclass
class BrowserSession:
    platform: str
    playwright: Any
    context: Any
    thread_id: int


class BrowserClient:
    def __init__(self) -> None:
        self._sessions: dict[str, BrowserSession] = {}
        self._lock = threading.RLock()

    def _ensure_platform(self, platform: str) -> dict[str, str]:
        config = PLATFORM_CONFIG.get((platform or "").strip().lower())
        if not config:
            raise AppException(error_code.BAD_REQUEST, "当前仅支持抖音和B站授权。", status_code=400)
        return config

    def _import_playwright(self):
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ModuleNotFoundError as exc:
            raise AppException(
                error_code.INTERNAL_ERROR,
                "未安装 Playwright，请先执行 `playwright install chromium`。",
                status_code=500,
                data={"errorType": "browser_open_failed"},
            ) from exc
        return sync_playwright, PlaywrightTimeoutError

    def profile_dir(self, platform: str) -> Path:
        self._ensure_platform(platform)
        return BROWSER_PROFILES_DIR / platform

    def _session_key(self, platform: str, headless: bool) -> str:
        return f"{platform}:{'headless' if headless else 'visible'}"

    def _close_session(self, session_key: str, session: BrowserSession) -> None:
        self._sessions.pop(session_key, None)
        try:
            session.context.close()
        except Exception:
            pass
        try:
            session.playwright.stop()
        except Exception:
            pass

    def start_persistent_browser(self, platform: str, *, headless: bool = False):
        platform = platform.strip().lower()
        self._ensure_platform(platform)
        session_key = self._session_key(platform, headless)
        current_thread_id = threading.get_ident()
        with self._lock:
            session = self._sessions.get(session_key)
            if session is not None:
                try:
                    if session.thread_id != current_thread_id:
                        raise RuntimeError("browser session thread changed")
                    _ = session.context.pages
                    return session
                except Exception:
                    self._close_session(session_key, session)
            sync_playwright, _ = self._import_playwright()
            try:
                playwright = sync_playwright().start()
                context = playwright.chromium.launch_persistent_context(
                    user_data_dir=str(self.profile_dir(platform)),
                    headless=headless,
                    viewport={"width": 1440, "height": 900},
                    args=[] if headless else ["--start-maximized"],
                )
            except Exception as exc:
                raise AppException(
                    error_code.INTERNAL_ERROR,
                    f"浏览器启动失败：{exc}",
                    status_code=500,
                    data={"errorType": "browser_open_failed"},
                ) from exc
            session = BrowserSession(
                platform=platform,
                playwright=playwright,
                context=context,
                thread_id=current_thread_id,
            )
            self._sessions[session_key] = session
            return session

    def _get_runtime_session(self, platform: str):
        platform = platform.strip().lower()
        current_thread_id = threading.get_ident()
        with self._lock:
            visible = self._sessions.get(self._session_key(platform, False))
            if visible is not None:
                try:
                    if visible.thread_id != current_thread_id:
                        raise RuntimeError("browser session thread changed")
                    _ = visible.context.pages
                    return visible
                except Exception:
                    self._close_session(self._session_key(platform, False), visible)
        return self.start_persistent_browser(platform, headless=True)

    def open_login_page(self, platform: str) -> None:
        config = self._ensure_platform(platform)
        session = self.start_persistent_browser(platform, headless=False)
        try:
            page = session.context.pages[0] if session.context.pages else session.context.new_page()
            page.goto(config["loginUrl"], wait_until="domcontentloaded", timeout=45000)
        except Exception as exc:
            raise AppException(
                error_code.INTERNAL_ERROR,
                f"授权页面打开失败：{exc}",
                status_code=500,
                data={"errorType": "page_load_failed"},
            ) from exc

    def open_material_page(self, platform: str, url: str) -> dict:
        session = self._get_runtime_session(platform)
        response_hints = RESPONSE_HINTS.get(platform, ())
        responses: list[dict[str, Any]] = []
        try:
            page = session.context.new_page()

            def handle_response(response):
                response_url = response.url or ""
                if response_hints and not any(hint in response_url for hint in response_hints):
                    return
                content_type = (response.headers or {}).get("content-type", "")
                if "json" not in content_type:
                    return
                try:
                    payload = response.json()
                except Exception:
                    return
                responses.append({"url": response_url, "payload": payload})

            page.on("response", handle_response)
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            page.wait_for_timeout(3000)
            final_url = page.url
            html = page.content()
            page.close()
            return {"finalUrl": final_url, "responses": responses, "html": html}
        except Exception as exc:
            raise AppException(
                error_code.INTERNAL_ERROR,
                f"页面加载失败：{exc}",
                status_code=500,
                data={"errorType": "page_load_failed"},
            ) from exc

    def download_file(self, platform: str, *, target_url: str, output_path: Path, referer: str = "") -> Path:
        session = self._get_runtime_session(platform)
        headers = {
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        if referer:
            headers["Referer"] = referer
            origin = urlsplit(referer)
            if origin.scheme and origin.netloc:
                headers["Origin"] = f"{origin.scheme}://{origin.netloc}"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            response = session.context.request.get(target_url, headers=headers, fail_on_status_code=False, timeout=120000)
            if not response.ok:
                raise AppException(
                    error_code.INTERNAL_ERROR,
                    f"视频源下载失败：HTTP {response.status}",
                    status_code=500,
                    data={"errorType": "material_download_failed"},
                )
            output_path.write_bytes(response.body())
        except AppException:
            raise
        except Exception as exc:
            raise AppException(
                error_code.INTERNAL_ERROR,
                f"视频源下载失败：{exc}",
                status_code=500,
                data={"errorType": "material_download_failed"},
            ) from exc
        return output_path

    def _load_profile_cookies(self, platform: str) -> list[dict[str, str]]:
        config = self._ensure_platform(platform)
        cookies: list[dict[str, str]] = []
        cookie_files = list(self.profile_dir(platform).rglob("Cookies"))
        for cookie_file in cookie_files:
            try:
                with sqlite3.connect(f"file:{cookie_file}?mode=ro", uri=True) as connection:
                    cursor = connection.execute(
                        "select host_key, path, name, value from cookies where host_key like ?",
                        (f"%{config['domain']}%",),
                    )
                    for host_key, path, name, value in cursor.fetchall():
                        if not name or value in (None, ""):
                            continue
                        cookies.append(
                            {
                                "domain": str(host_key or ""),
                                "path": str(path or "/"),
                                "name": str(name),
                                "value": str(value),
                            }
                        )
            except Exception:
                continue
        return cookies

    def export_netscape_cookies(self, platform: str, output_path: Path) -> int:
        cookies = self._load_profile_cookies(platform)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Netscape HTTP Cookie File",
            "# This file is generated by INLOOK Studio browser auth runtime.",
        ]
        count = 0
        for cookie in cookies:
            name = str(cookie.get("name") or "").strip()
            value = str(cookie.get("value") or "")
            domain = str(cookie.get("domain") or "").strip()
            path = str(cookie.get("path") or "/").strip() or "/"
            if not name or not value or not domain:
                continue
            include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
            secure = "TRUE" if domain.startswith(".") or domain.endswith("bilibili.com") else "FALSE"
            lines.append("\t".join([domain, include_subdomains, path, secure, "0", name, value]))
            count += 1
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return count

    def get_auth_status(self, platform: str) -> dict[str, Any]:
        config = self._ensure_platform(platform)
        cookie_count = 0
        cookie_files = list(self.profile_dir(platform).rglob("Cookies"))
        for cookie_file in cookie_files:
            try:
                with sqlite3.connect(f"file:{cookie_file}?mode=ro", uri=True) as connection:
                    cursor = connection.execute(
                        "select count(1) from cookies where host_key like ?",
                        (f"%{config['domain']}%",),
                    )
                    count = int(cursor.fetchone()[0] or 0)
                    cookie_count += count
            except Exception:
                continue
        with self._lock:
            active = any(key.startswith(f"{platform}:") for key in self._sessions)
        if cookie_count <= 0:
            return {"platform": platform, "authorized": False, "cookieCount": 0, "active": active}
        return {
            "platform": platform,
            "authorized": True,
            "cookieCount": cookie_count,
            "active": active,
        }

    def close_browser(self, platform: str) -> None:
        for headless in (False, True):
            with self._lock:
                session = self._sessions.pop(self._session_key(platform, headless), None)
            if session is None:
                continue
            try:
                session.context.close()
            except Exception:
                pass
            try:
                session.playwright.stop()
            except Exception:
                pass


browser_client = BrowserClient()
