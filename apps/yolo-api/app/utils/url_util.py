from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit, urlunsplit

from app.common import error_code
from app.common.exceptions import AppException

URL_RE = re.compile(r"https?://[^\s\u3000\n\r\t\"'<>]+", re.IGNORECASE)
BARE_URL_RE = re.compile(
    r"(?:(?:https?://)?(?:v\.douyin\.com|(?:www\.)?douyin\.com|(?:www\.)?tiktok\.com|(?:m\.)?(?:www\.)?bilibili\.com|b23\.tv))[^\s\u3000\n\r\t\"'<>]*",
    re.IGNORECASE,
)
BARE_BILIBILI_BVID_RE = re.compile(r"\b(BV[0-9A-Za-z]{10})\b", re.IGNORECASE)
TRAILING_CHARS = "，。！？、；：《》）（】『』「」,.!?;:)]}>\"'"


@dataclass
class ExtractedVideoLink:
    raw_url: str
    normalized_url: str
    source_type: str
    url_type: str
    video_id: str
    index: int


@dataclass
class ParsedMaterialInput:
    raw_input: str
    candidate_url: str
    normalized_url: str
    source_type: str
    url_type: str
    urls: list[str]

    @property
    def url(self) -> str:
        return self.normalized_url


def _trim_url(value: str) -> str:
    trimmed = str(value or "").strip()
    while trimmed and trimmed[-1] in TRAILING_CHARS:
        trimmed = trimmed[:-1]
    return trimmed


def _ensure_scheme(value: str) -> str:
    lowered = value.lower()
    if lowered.startswith(("http://", "https://")):
        return value
    if BARE_BILIBILI_BVID_RE.fullmatch(value.strip()):
        return f"https://www.bilibili.com/video/{value.strip()}"
    if re.match(r"^(?:v\.douyin\.com|(?:www\.)?douyin\.com|(?:www\.)?tiktok\.com|(?:m\.)?(?:www\.)?bilibili\.com|b23\.tv)", lowered):
        return f"https://{value}"
    return value


def normalize_url(url: str) -> str:
    value = _ensure_scheme(_trim_url(url))
    if not value:
        return ""

    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        return ""

    scheme = parsed.scheme.lower()
    host = parsed.netloc.lower()
    path = parsed.path or ""
    query = ""
    fragment = ""

    if host == "v.douyin.com":
        code = next((segment for segment in path.split("/") if segment), "")
        if not code:
            return ""
        path = f"/{code}/"
    elif host.endswith("douyin.com"):
        if path == "/discover":
            modal_id = (parse_qs(parsed.query).get("modal_id") or [""])[0].strip()
            if modal_id:
                path = f"/video/{modal_id}"
            else:
                path = "/discover"
        else:
            match = re.search(r"/video/(\d+)", path)
            if match:
                path = f"/video/{match.group(1)}"
            elif path and path != "/":
                path = path.rstrip("/")
    elif host.endswith("tiktok.com"):
        short_match = re.search(r"/t/([^/?#]+)/?", path)
        video_match = re.search(r"/@([^/]+)/video/(\d+)", path)
        if short_match:
            path = f"/t/{short_match.group(1)}/"
        elif video_match:
            path = f"/@{video_match.group(1)}/video/{video_match.group(2)}"
        elif path and path != "/":
            path = path.rstrip("/")
    elif host == "b23.tv":
        code = next((segment for segment in path.split("/") if segment), "")
        if not code:
            return ""
        path = f"/{code}"
    elif host.endswith("bilibili.com"):
        host = "www.bilibili.com"
        video_match = re.search(r"/video/(BV[0-9A-Za-z]{10})", path, re.IGNORECASE)
        if video_match:
            path = f"/video/{video_match.group(1)}"
            query = ""
        elif path and path != "/":
            path = path.rstrip("/")
            query = parsed.query
        else:
            query = parsed.query
    else:
        query = parsed.query
        fragment = parsed.fragment

    return urlunsplit((scheme, host, path or "/", query, fragment))


def detect_source_type(url: str) -> str:
    value = normalize_url(url).lower()
    if "v.douyin.com" in value or "douyin.com" in value:
        return "douyin"
    if "tiktok.com" in value:
        return "tiktok"
    if "bilibili.com" in value or "b23.tv" in value:
        return "bilibili"
    return "unknown"


def detect_url_type(url: str) -> str:
    normalized = normalize_url(url)
    value = normalized.lower()
    original = str(url or "").lower()
    if "douyin.com/discover" in original and "modal_id=" in original:
        return "douyin_discover"
    if "v.douyin.com/" in value:
        return "douyin_short"
    if "/video/" in value and "douyin.com" in value:
        return "douyin_video"
    if "/t/" in value and "tiktok.com" in value:
        return "tiktok_short"
    if "/video/" in value and "tiktok.com" in value:
        return "tiktok_video"
    if "b23.tv/" in value:
        return "bilibili_short"
    if "/video/" in value and "bilibili.com" in value:
        return "bilibili_video"
    return "unknown"


def _extract_video_id(normalized_url: str, url_type: str) -> str:
    if url_type == "douyin_short":
        parts = [segment for segment in urlsplit(normalized_url).path.split("/") if segment]
        return parts[0] if parts else ""
    if url_type in {"douyin_video", "bilibili_video", "tiktok_video"}:
        match = re.search(r"/video/([^/?#]+)", normalized_url)
        return match.group(1) if match else ""
    if url_type in {"tiktok_short", "bilibili_short"}:
        parts = [segment for segment in urlsplit(normalized_url).path.split("/") if segment]
        return parts[-1] if parts else ""
    return ""


def extract_video_links(raw_input: str) -> list[dict]:
    content = str(raw_input or "")
    matches = list(URL_RE.finditer(content))
    bare_matches = list(BARE_URL_RE.finditer(content))
    bvid_matches = list(BARE_BILIBILI_BVID_RE.finditer(content))
    matches.extend(bare_matches)
    matches.extend(bvid_matches)
    matches.sort(key=lambda item: item.start())

    results: list[dict] = []
    seen: set[str] = set()
    for index, match in enumerate(matches):
        raw_url = match.group(0)
        normalized_url = normalize_url(raw_url)
        if not normalized_url or normalized_url in seen:
            continue
        seen.add(normalized_url)
        source_type = detect_source_type(normalized_url)
        url_type = detect_url_type(raw_url)
        results.append(
            {
                "rawUrl": raw_url,
                "normalizedUrl": normalized_url,
                "sourceType": source_type,
                "urlType": url_type,
                "videoId": _extract_video_id(normalized_url, url_type),
                "index": len(results),
            }
        )
    return results


def extract_first_url(raw_input: str) -> str | None:
    links = extract_video_links(raw_input)
    if not links:
        return None
    return links[0]["normalizedUrl"]


def parse_material_input(raw_input: str, source_type: str = "auto", raw_url: str = "") -> ParsedMaterialInput:
    normalized_input = (raw_input or "").strip()
    candidate_url = (raw_url or "").strip()
    if not normalized_input and not candidate_url:
        raise AppException(
            error_code.BAD_REQUEST,
            "未识别到有效视频链接，请粘贴抖音/B站/TikTok分享链接，或上传本地视频。",
            status_code=400,
            data={"errorType": "url_not_found", "rawInput": normalized_input},
        )

    candidate_links = extract_video_links(candidate_url) if candidate_url else []
    extracted_links = candidate_links or extract_video_links(normalized_input)
    if not extracted_links:
        raise AppException(
            error_code.BAD_REQUEST,
            "未识别到有效视频链接，请粘贴抖音/B站/TikTok分享链接，或上传本地视频。",
            status_code=400,
            data={"errorType": "url_not_found", "rawInput": normalized_input},
        )

    primary = extracted_links[0]
    detected_source_type = detect_source_type(primary["normalizedUrl"])
    if detected_source_type == "unknown":
        raise AppException(
            error_code.BAD_REQUEST,
            "当前平台暂不支持，请粘贴抖音/B站/TikTok链接，或上传本地视频。",
            status_code=400,
            data={
                "errorType": "unsupported_platform",
                "sourceUrl": primary["normalizedUrl"],
                "sourceType": "unknown",
                "rawInput": normalized_input,
            },
        )

    return ParsedMaterialInput(
        raw_input=normalized_input or candidate_url or primary["normalizedUrl"],
        candidate_url=candidate_url,
        normalized_url=primary["normalizedUrl"],
        source_type=detected_source_type,
        url_type=primary["urlType"],
        urls=[item["normalizedUrl"] for item in extracted_links],
    )
