from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

from fastapi import HTTPException, UploadFile

from app.clients.browser_client import browser_client
from app.clients.copy_pilot_client import copy_pilot_client
from app.clients.ffmpeg_client import ffmpeg_client
from app.common import error_code
from app.common.exceptions import AppException
from app.config import settings
from app.providers.local_material_provider import LocalMaterialProvider
from app.services.browser_auth_service import ensure_platform_authorized, mark_platform_authorization_expired
from app.services.material_download_service import download_material_video
from app.tasks.task_store import (
    append_log,
    init_material_runtime,
    MATERIAL_ROOT,
    material_cache_dir,
    material_inputs_dir,
    material_json_path,
    material_log_path,
    material_outputs_dir,
    material_raw_extract_response_path,
    read_json,
    read_material,
    write_json,
    write_material,
)
from app.utils.url_util import parse_material_input

_LOCAL_PROVIDER = LocalMaterialProvider()
_TAG_RE = re.compile(r"#([^\s#]+)")
_DOUYIN_FINAL_URL_RE = re.compile(r"/video/(\d+)")
_RENDER_DATA_RE = re.compile(r'<script[^>]+id="RENDER_DATA"[^>]*>(.*?)</script>', re.DOTALL)
_NEXT_DATA_RE = re.compile(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)

def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def build_material_key(source_type: str, normalized_url: str) -> str:
    raw = f"{str(source_type or '').strip().lower()}:{str(normalized_url or '').strip()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"mt_{digest[:16]}"


def _safe_nested(data: dict | list | None, *keys):
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        elif isinstance(current, list) and isinstance(key, int) and 0 <= key < len(current):
            current = current[key]
        else:
            return None
    return current


def _first_non_empty(*values):
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if value not in (None, "", [], {}):
            return value
    return None


def _as_list(value) -> list:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _pick_first_url(node) -> str:
    if isinstance(node, str):
        return node.strip()
    if isinstance(node, list):
        for item in node:
            result = _pick_first_url(item)
            if result:
                return result
        return ""
    if isinstance(node, dict):
        for key in ("url_list", "origin_url_list", "backup_url"):
            result = _pick_first_url(node.get(key))
            if result:
                return result
        for key in ("base_url", "url", "src"):
            result = _pick_first_url(node.get(key))
            if result:
                return result
        for key in ("play_addr", "download_addr", "play_url"):
            result = _pick_first_url(node.get(key))
            if result:
                return result
        uri = str(node.get("uri") or "").strip()
        if uri.startswith("http://") or uri.startswith("https://"):
            return uri
    return ""


def _parse_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _write_runtime_snapshot(material_id: str, payload: dict) -> None:
    write_json(material_outputs_dir(material_id) / "metadata.json", payload)
    write_material(material_id, payload)


def _local_video_path(material_id: str) -> Path:
    return material_inputs_dir(material_id) / "source.mp4"


def _local_video_url(material_id: str) -> str:
    return f"/api/v1/materials/{material_id}/files/source.mp4"


def _extract_resolved_video_id(*urls: str) -> str:
    for url in urls:
        value = str(url or "")
        match = re.search(r"/(?:share/)?video/(\d+)", value)
        if match:
            return match.group(1)
    return ""


def _iter_material_payloads(exclude_material_id: str = ""):
    if not MATERIAL_ROOT.exists():
        return
    paths = sorted(MATERIAL_ROOT.glob("*/material.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in paths:
        candidate_id = path.parent.name
        if candidate_id == exclude_material_id:
            continue
        try:
            payload = read_json(path)
        except Exception:
            continue
        if isinstance(payload, dict):
            yield candidate_id, payload


def _match_cached_material(candidate: dict, *, source_type: str, normalized_url: str, resolved_video_id: str = "") -> bool:
    if str(candidate.get("sourceType") or "").strip().lower() != str(source_type or "").strip().lower():
        return False

    known_urls = {
        str(candidate.get("sourceUrl") or "").strip(),
        str(candidate.get("normalizedUrl") or "").strip(),
    }
    if normalized_url and normalized_url in known_urls:
        return True

    candidate_video_id = _extract_resolved_video_id(
        str(candidate.get("finalUrl") or ""),
        str(candidate.get("sourceUrl") or ""),
        str(candidate.get("normalizedUrl") or ""),
    )
    return bool(resolved_video_id and candidate_video_id and candidate_video_id == resolved_video_id)


def _candidate_source_is_valid(candidate_id: str) -> bool:
    source_path = _local_video_path(candidate_id)
    if not source_path.exists():
        return False
    try:
        if source_path.stat().st_size < 10 * 1024:
            return False
        metadata = ffmpeg_client.probe_video(source_path)
    except Exception:
        return False
    return int(metadata.get("width") or 0) > 0 and int(metadata.get("height") or 0) > 0 and float(metadata.get("duration") or 0) > 0


def _clone_cached_material_source(
    *,
    target_material_id: str,
    parsed,
    cached_material_id: str,
    cached_payload: dict,
    reason: str,
) -> dict | None:
    if not _candidate_source_is_valid(cached_material_id):
        append_log(target_material_id, f"[CACHE_REUSE_SKIP] materialId={cached_material_id} reason=invalid_source")
        return None

    source_path = _local_video_path(cached_material_id)
    target_path = _local_video_path(target_material_id)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if source_path.resolve() != target_path.resolve():
        shutil.copy2(source_path, target_path)

    cached_video = cached_payload.get("video") if isinstance(cached_payload.get("video"), dict) else {}
    payload = {
        **cached_payload,
        "materialId": target_material_id,
        "materialKey": target_material_id,
        "sourceUrl": parsed.normalized_url,
        "normalizedUrl": parsed.normalized_url,
        "rawInput": parsed.raw_input,
        "cacheHit": True,
        "cacheStatus": "local_ready",
        "downloadStatus": "downloaded",
        "localFileStatus": "exists",
        "localVideoPath": str(target_path),
        "localVideoUrl": _local_video_url(target_material_id),
        "localFileSize": int(target_path.stat().st_size),
        "lastCheckAt": _now_iso(),
        "lastError": None,
        "status": "ready",
        "reusedFromMaterialId": cached_material_id,
        "reusedFromReason": reason,
        "video": {
            **cached_video,
            "url": _local_video_url(target_material_id),
            "remoteUrl": str(cached_video.get("remoteUrl") or cached_video.get("url") or ""),
            "fileSize": int(target_path.stat().st_size),
        },
    }
    write_material(target_material_id, payload)
    append_log(target_material_id, f"[CACHE_REUSE_HIT] materialId={cached_material_id} reason={reason}")
    return _hydrate_local_file_state(target_material_id, {**payload, "cacheHit": True})


def _reuse_cached_material_source(
    *,
    target_material_id: str,
    parsed,
    resolved_video_id: str = "",
    reason: str,
) -> dict | None:
    for cached_material_id, cached_payload in _iter_material_payloads(target_material_id):
        if not _match_cached_material(
            cached_payload,
            source_type=parsed.source_type,
            normalized_url=parsed.normalized_url,
            resolved_video_id=resolved_video_id,
        ):
            continue
        reused = _clone_cached_material_source(
            target_material_id=target_material_id,
            parsed=parsed,
            cached_material_id=cached_material_id,
            cached_payload=cached_payload,
            reason=reason,
        )
        if reused is not None:
            return reused
    return None


def _build_material_shell(*, material_id: str, parsed) -> dict:
    timestamp = _now_iso()
    return {
        "materialId": material_id,
        "materialKey": material_id,
        "materialType": "video",
        "sourceType": parsed.source_type,
        "sourceUrl": parsed.normalized_url,
        "normalizedUrl": parsed.normalized_url,
        "rawInput": parsed.raw_input,
        "title": "",
        "description": "",
        "caption": "",
        "authorName": "",
        "tags": [],
        "video": {
            "url": "",
            "width": None,
            "height": None,
            "duration": None,
            "fileSize": None,
            "sources": [],
        },
        "coverUrl": "",
        "images": [],
        "imageUrls": [],
        "musicUrl": "",
        "downloadStatus": "not_downloaded",
        "localFileStatus": "none",
        "localVideoPath": None,
        "localVideoUrl": None,
        "localFileSize": None,
        "localFileHash": None,
        "downloadedAt": None,
        "cacheHit": False,
        "cacheStatus": "created",
        "lastCheckAt": None,
        "lastError": None,
        "triedSources": [],
        "status": "pending",
        "errorMessage": None,
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }


def _save_raw_extract_response(material_id: str, payload: dict) -> None:
    write_json(material_raw_extract_response_path(material_id), payload)


def _save_material_json(material_id: str, payload: dict) -> dict:
    current = read_material(material_id) if material_json_path(material_id).exists() else {}
    merged = {**current, **payload}
    merged["materialId"] = material_id
    merged["materialKey"] = material_id
    merged["createdAt"] = current.get("createdAt") or payload.get("createdAt") or _now_iso()
    merged["updatedAt"] = _now_iso()
    write_material(material_id, merged)
    return merged


def _hydrate_local_file_state(material_id: str, payload: dict) -> dict:
    current = dict(payload or {})
    cache_hit = bool(current.get("cacheHit"))
    local_path = _local_video_path(material_id)
    current["materialId"] = material_id
    current["materialKey"] = material_id
    current["lastCheckAt"] = _now_iso()

    if not local_path.exists():
        downloaded_before = str(current.get("downloadStatus") or "").strip() == "downloaded" or bool(current.get("localVideoPath"))
        if downloaded_before:
            current.update(
                {
                    "cacheHit": cache_hit,
                    "cacheStatus": "local_missing",
                    "downloadStatus": "missing",
                    "localFileStatus": "missing",
                    "localVideoPath": None,
                    "localVideoUrl": None,
                    "localFileSize": None,
                    "lastError": None,
                    "status": "metadata_cached",
                }
            )
        else:
            current.update(
                {
                    "cacheHit": cache_hit,
                    "cacheStatus": "metadata_cached",
                    "downloadStatus": "not_downloaded",
                    "localFileStatus": "none",
                    "localVideoPath": None,
                    "localVideoUrl": None,
                    "localFileSize": None,
                    "status": "metadata_cached",
                }
            )
        return _save_material_json(material_id, current)

    try:
        file_size = int(local_path.stat().st_size)
    except FileNotFoundError:
        file_size = 0
    if file_size < 10 * 1024:
        current.update(
            {
                "cacheHit": cache_hit,
                "cacheStatus": "local_invalid",
                "downloadStatus": "failed",
                "localFileStatus": "invalid",
                "localVideoPath": None,
                "localVideoUrl": None,
                "localFileSize": file_size,
                "lastError": "本地视频文件无效，文件过小",
                "status": "invalid",
            }
        )
        return _save_material_json(material_id, current)

    try:
        metadata = ffmpeg_client.probe_video(local_path)
    except AppException:
        current.update(
            {
                "cacheHit": cache_hit,
                "cacheStatus": "local_invalid",
                "downloadStatus": "failed",
                "localFileStatus": "invalid",
                "localVideoPath": None,
                "localVideoUrl": None,
                "localFileSize": file_size,
                "lastError": "本地视频文件无效，ffprobe 校验失败",
                "status": "invalid",
            }
        )
        return _save_material_json(material_id, current)

    if int(metadata.get("width") or 0) <= 0 or int(metadata.get("height") or 0) <= 0 or float(metadata.get("duration") or 0) <= 0:
        current.update(
            {
                "cacheHit": cache_hit,
                "cacheStatus": "local_invalid",
                "downloadStatus": "failed",
                "localFileStatus": "invalid",
                "localVideoPath": None,
                "localVideoUrl": None,
                "localFileSize": file_size,
                "lastError": "本地视频文件无效，ffprobe 校验失败",
                "status": "invalid",
            }
        )
        return _save_material_json(material_id, current)

    current.update(
        {
            "cacheHit": cache_hit,
            "cacheStatus": "local_ready",
            "downloadStatus": "downloaded",
            "localFileStatus": "exists",
            "localVideoPath": str(local_path),
            "localVideoUrl": _local_video_url(material_id),
            "localFileSize": file_size,
            "lastError": None,
            "status": "ready",
            "video": {
                **(current.get("video") or {}),
                "width": int(metadata.get("width") or 0),
                "height": int(metadata.get("height") or 0),
                "duration": float(metadata.get("duration") or 0.0),
                "fileSize": file_size,
            },
        }
    )
    return _save_material_json(material_id, current)


def _extract_tags(description: str, data: dict) -> list[str]:
    tags: list[str] = []
    for item in _as_list(data.get("text_extra")):
        hashtag = str(item.get("hashtag_name") or "").strip() if isinstance(item, dict) else ""
        if hashtag and hashtag not in tags:
            tags.append(hashtag)
    if tags:
        return tags
    for match in _TAG_RE.findall(description or ""):
        tag = str(match).strip()
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def _walk_match(node, predicate):
    if predicate(node):
        return node
    if isinstance(node, dict):
        for value in node.values():
            result = _walk_match(value, predicate)
            if result is not None:
                return result
    elif isinstance(node, list):
        for item in node:
            result = _walk_match(item, predicate)
            if result is not None:
                return result
    return None


def _build_douyin_video(aweme_detail: dict) -> dict:
    duration = round(_parse_float(aweme_detail.get("duration")) / 1000, 3)
    bit_rates = _as_list(_safe_nested(aweme_detail, "video", "bit_rate"))
    sources: list[dict] = []
    for index, item in enumerate(bit_rates, start=1):
        if not isinstance(item, dict):
            continue
        url = _pick_first_url(item)
        if not url or not url.startswith(("http://", "https://")):
            continue
        width = _parse_int(_safe_nested(item, "play_addr", "width") or item.get("width") or _safe_nested(item, "play_addr_265", "width"))
        height = _parse_int(_safe_nested(item, "play_addr", "height") or item.get("height") or _safe_nested(item, "play_addr_265", "height"))
        file_size = _parse_int(_safe_nested(item, "play_addr", "data_size") or item.get("data_size") or item.get("size"))
        label = str(item.get("gear_name") or "").strip() or (f"{height}P" if height else f"备用源 {index}")
        sources.append(
            {
                "label": label,
                "url": url,
                "width": width,
                "height": height,
                "fileSize": file_size,
            }
        )
    sources.sort(key=lambda source: (source["height"], source["width"], source["fileSize"]), reverse=True)
    primary_url = _pick_first_url(_safe_nested(aweme_detail, "video", "play_addr")) or _pick_first_url(
        _safe_nested(aweme_detail, "video", "download_addr")
    )
    if primary_url and all(source.get("url") != primary_url for source in sources):
        sources.insert(
            0,
            {
                "label": "主视频",
                "url": primary_url,
                "width": _parse_int(_safe_nested(aweme_detail, "video", "width")),
                "height": _parse_int(_safe_nested(aweme_detail, "video", "height")),
                "fileSize": 0,
            },
        )
    primary = sources[0] if sources else {"url": primary_url, "width": 0, "height": 0, "fileSize": 0}
    return {
        "url": primary.get("url") or "",
        "width": _parse_int(primary.get("width")) or _parse_int(_safe_nested(aweme_detail, "video", "width")),
        "height": _parse_int(primary.get("height")) or _parse_int(_safe_nested(aweme_detail, "video", "height")),
        "duration": duration,
        "fileSize": _parse_int(primary.get("fileSize")),
        "sources": sources,
    }


def _build_douyin_images(aweme_detail: dict) -> list[dict]:
    candidates = []
    for key in ("images", "image_list", "image_infos", "original_images"):
        candidates.extend(_as_list(aweme_detail.get(key)))
    images: list[dict] = []
    seen: set[str] = set()
    for item in candidates:
        url = _pick_first_url(item).strip()
        thumbnail = ""
        if isinstance(item, dict):
            thumbnail = (
                _pick_first_url(item.get("thumbnail"))
                or _pick_first_url(item.get("display_image"))
                or _pick_first_url(item.get("download_url"))
            ).strip()
        if not url or url in seen:
            continue
        seen.add(url)
        images.append({"url": url, "thumbnailUrl": thumbnail or url, "label": f"图片素材 {len(images) + 1}"})
    return images


def _parse_douyin_from_html(html: str) -> dict | None:
    for pattern in (_RENDER_DATA_RE, _NEXT_DATA_RE):
        match = pattern.search(html or "")
        if not match:
            continue
        raw = match.group(1).strip()
        try:
            decoded = unquote(raw)
            payload = json.loads(decoded)
        except Exception:
            try:
                payload = json.loads(raw)
            except Exception:
                continue
        result = _walk_match(payload, lambda node: isinstance(node, dict) and "desc" in node and "author" in node and "video" in node)
        if isinstance(result, dict):
            return result
    return None


def _extract_douyin_detail(payloads: list[dict], html: str) -> dict | None:
    for item in payloads:
        payload = item.get("payload")
        if not isinstance(payload, dict):
            continue
        detail = _safe_nested(payload, "aweme_detail")
        if isinstance(detail, dict):
            return detail
        detail = _walk_match(payload, lambda node: isinstance(node, dict) and "desc" in node and "author" in node and "video" in node)
        if isinstance(detail, dict):
            return detail
    return _parse_douyin_from_html(html)


def _extract_bilibili_detail(payloads: list[dict], html: str) -> tuple[dict | None, dict | None]:
    view_payload = None
    play_payload = None
    for item in payloads:
        payload = item.get("payload")
        url = item.get("url") or ""
        if not isinstance(payload, dict):
            continue
        if "view" in url and isinstance(payload.get("data"), dict):
            view_payload = payload["data"]
        if "playurl" in url and isinstance(payload.get("data"), dict):
            play_payload = payload["data"]
    if view_payload:
        return view_payload, play_payload
    match = _NEXT_DATA_RE.search(html or "")
    if match:
        try:
            payload = json.loads(match.group(1).strip())
            result = _walk_match(payload, lambda node: isinstance(node, dict) and "title" in node and "owner" in node)
            if isinstance(result, dict):
                return result, play_payload
        except Exception:
            pass
    return None, play_payload


def _map_douyin_material(
    *,
    material_id: str,
    parsed,
    final_url: str,
    aweme_detail: dict,
    cache_hit: bool,
    extractor: str = "browser_auth",
) -> dict:
    base = _build_material_shell(material_id=material_id, parsed=parsed)
    description = _first_non_empty(
        aweme_detail.get("desc"),
        aweme_detail.get("caption"),
        _safe_nested(aweme_detail, "share_info", "share_desc_info"),
        "",
    )
    raw_title = str(_first_non_empty(aweme_detail.get("item_title"), aweme_detail.get("preview_title"), "") or "").strip()
    title = raw_title
    if not title or title == str(description or "").strip():
        title = "未识别到独立标题"
    video = _build_douyin_video(aweme_detail)
    if not video.get("url") or not str(video.get("url")).startswith(("http://", "https://")):
        raise AppException(
            error_code.INTERNAL_ERROR,
            "已拿到作品信息，但未解析到可用视频地址。",
            status_code=500,
            data={"errorType": "video_url_missing", "sourceType": parsed.source_type, "sourceUrl": parsed.url},
        )
    images = _build_douyin_images(aweme_detail)
    payload = {
        **base,
        "sourceUrl": parsed.url,
        "normalizedUrl": parsed.normalized_url,
        "finalUrl": final_url,
        "title": str(title or "未识别到独立标题"),
        "description": str(description or ""),
        "caption": str(description or ""),
        "authorName": str(_first_non_empty(_safe_nested(aweme_detail, "author", "nickname"), "")),
        "tags": _extract_tags(str(description or ""), aweme_detail),
        "video": video,
        "images": images,
        "imageUrls": [item.get("url") for item in images if str(item.get("url") or "").strip()],
        "coverUrl": str(
            _first_non_empty(
                _pick_first_url(_safe_nested(aweme_detail, "video", "cover")),
                _pick_first_url(_safe_nested(aweme_detail, "author", "avatar_larger")),
                _pick_first_url(_safe_nested(aweme_detail, "author", "avatar_medium")),
                "",
            )
        ),
        "musicUrl": _pick_first_url(_safe_nested(aweme_detail, "music", "play_url")),
        "extractor": extractor,
        "cacheHit": cache_hit,
        "cacheStatus": "metadata_cached",
        "downloadStatus": "not_downloaded",
        "localFileStatus": "none",
        "status": "metadata_cached",
        "errorMessage": None,
        "createdAt": _now_iso(),
        "updatedAt": _now_iso(),
    }
    return payload


def _map_bilibili_material(*, material_id: str, parsed, final_url: str, view_payload: dict, play_payload: dict | None, cache_hit: bool) -> dict:
    base = _build_material_shell(material_id=material_id, parsed=parsed)
    owner = view_payload.get("owner") if isinstance(view_payload.get("owner"), dict) else {}
    tags = [str(tag.get("tag_name")).strip() for tag in _as_list(view_payload.get("tags")) if isinstance(tag, dict) and str(tag.get("tag_name") or "").strip()]
    video_url = ""
    sources: list[dict] = []
    if isinstance(play_payload, dict):
        dash_video = _as_list(_safe_nested(play_payload, "dash", "video"))
        if dash_video:
            dash_video.sort(key=lambda item: (_parse_int(item.get("height")), _parse_int(item.get("width"))), reverse=True)
            for index, item in enumerate(dash_video, start=1):
                source_url = _pick_first_url(item)
                if not source_url:
                    continue
                width = _parse_int(item.get("width"))
                height = _parse_int(item.get("height"))
                sources.append(
                    {
                        "label": f"{height}P" if height else f"备用源 {index}",
                        "url": source_url,
                        "width": width,
                        "height": height,
                        "fileSize": 0,
                    }
                )
            if sources:
                video_url = sources[0]["url"]
    payload = {
        **base,
        "sourceUrl": parsed.url,
        "normalizedUrl": parsed.normalized_url,
        "finalUrl": final_url,
        "title": str(_first_non_empty(view_payload.get("title"), "未识别到独立标题")),
        "description": str(_first_non_empty(view_payload.get("desc"), "")),
        "caption": str(_first_non_empty(view_payload.get("desc"), "")),
        "authorName": str(_first_non_empty(owner.get("name"), "")),
        "tags": tags,
        "video": {
            "url": video_url,
            "width": _parse_int(sources[0]["width"]) if sources else 0,
            "height": _parse_int(sources[0]["height"]) if sources else 0,
            "duration": round(_parse_float(view_payload.get("duration")), 3),
            "fileSize": 0,
            "sources": sources,
        },
        "images": [],
        "coverUrl": str(_first_non_empty(view_payload.get("pic"), "")),
        "musicUrl": "",
        "extractor": "browser_auth",
        "cacheHit": cache_hit,
        "cacheStatus": "metadata_cached",
        "downloadStatus": "not_downloaded",
        "localFileStatus": "none",
        "status": "metadata_cached",
        "errorMessage": None,
        "createdAt": _now_iso(),
        "updatedAt": _now_iso(),
    }
    return payload


def _build_local_material_vo(material_id: str, payload: dict) -> dict:
    timestamp = _now_iso()
    source_path = Path(payload["sourcePath"])
    cover_path = Path(payload["coverPath"])
    duration = float(payload.get("duration") or 0.0)
    width = int(payload.get("width") or 0)
    height = int(payload.get("height") or 0)
    file_size = int(payload.get("fileSize") or 0)
    if duration <= 0 or width <= 0 or height <= 0 or file_size <= 0:
        raise AppException(error_code.INTERNAL_ERROR, "ffprobe 读取失败：未能获取有效的视频时长或分辨率。", status_code=500)
    return {
        "materialId": material_id,
        "materialKey": material_id,
        "materialType": "video",
        "sourceType": payload["sourceType"],
        "sourceUrl": payload.get("sourceUrl") or "",
        "normalizedUrl": payload.get("sourceUrl") or "",
        "finalUrl": "",
        "rawInput": payload.get("title") or source_path.name,
        "title": payload.get("title") or source_path.name,
        "description": payload.get("description") or "",
        "caption": payload.get("description") or "",
        "authorName": "",
        "tags": list(payload.get("tags") or []),
        "video": {
            "url": f"/api/v1/materials/{material_id}/files/{source_path.name}",
            "width": width,
            "height": height,
            "duration": duration,
            "fileSize": file_size,
            "sources": [
                {
                    "label": "本地视频",
                    "url": f"/api/v1/materials/{material_id}/files/{source_path.name}",
                    "width": width,
                    "height": height,
                    "fileSize": file_size,
                }
            ],
        },
        "images": [],
        "imageUrls": [],
        "coverUrl": f"/api/v1/materials/{material_id}/files/{cover_path.name}" if cover_path.exists() else "",
        "musicUrl": "",
        "extractor": "local_upload",
        "downloadStatus": "downloaded",
        "localFileStatus": "exists",
        "localVideoPath": str(source_path),
        "localVideoUrl": f"/api/v1/materials/{material_id}/files/{source_path.name}",
        "localFileSize": file_size,
        "localFileHash": None,
        "downloadedAt": timestamp,
        "cacheHit": False,
        "cacheStatus": "local_ready",
        "lastCheckAt": timestamp,
        "lastError": None,
        "triedSources": [],
        "status": "ready",
        "errorMessage": None,
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }


def _persist_material_metadata(material_id: str, payload: dict) -> dict:
    init_material_runtime(material_id)
    _write_runtime_snapshot(material_id, payload)
    return _hydrate_local_file_state(material_id, payload)


def _has_material_metadata(payload: dict | None) -> bool:
    if not isinstance(payload, dict):
        return False
    video = payload.get("video") if isinstance(payload.get("video"), dict) else {}
    return bool(str(video.get("url") or video.get("remoteUrl") or "").strip() or list(video.get("sources") or []))


def _extract_browser_material(material_id: str, parsed) -> dict:
    ensure_platform_authorized(parsed.source_type)
    append_log(material_id, "[EXTRACTOR] browser_auth")
    browser_payload = browser_client.open_material_page(parsed.source_type, parsed.normalized_url)
    final_url = str(browser_payload.get("finalUrl") or "")
    append_log(material_id, f"[FINAL_URL] {final_url}")
    if any(keyword in final_url for keyword in ("login", "passport")):
        mark_platform_authorization_expired(parsed.source_type, "登录态已失效，请重新授权。")
        raise AppException(
            error_code.INTERNAL_ERROR,
            "平台登录态已失效，请重新授权。",
            status_code=400,
            data={"sourceType": parsed.source_type, "sourceUrl": parsed.url, "errorType": "platform_auth_expired"},
        )

    if parsed.source_type == "douyin":
        detail = _extract_douyin_detail(browser_payload.get("responses") or [], str(browser_payload.get("html") or ""))
        if not isinstance(detail, dict):
            raise AppException(
                error_code.INTERNAL_ERROR,
                "浏览器已打开作品页面，但未解析到作品数据。",
                status_code=500,
                data={"sourceType": parsed.source_type, "sourceUrl": parsed.url, "errorType": "material_parse_failed"},
            )
        payload = _map_douyin_material(
            material_id=material_id,
            parsed=parsed,
            final_url=final_url,
            aweme_detail=detail,
            cache_hit=False,
        )
    elif parsed.source_type == "bilibili":
        view_payload, play_payload = _extract_bilibili_detail(
            browser_payload.get("responses") or [],
            str(browser_payload.get("html") or ""),
        )
        if not isinstance(view_payload, dict):
            raise AppException(
                error_code.INTERNAL_ERROR,
                "浏览器已打开作品页面，但未解析到B站作品数据。",
                status_code=500,
                data={"sourceType": parsed.source_type, "sourceUrl": parsed.url, "errorType": "material_parse_failed"},
            )
        payload = _map_bilibili_material(
            material_id=material_id,
            parsed=parsed,
            final_url=final_url,
            view_payload=view_payload,
            play_payload=play_payload,
            cache_hit=False,
        )
    else:
        raise AppException(
            error_code.BAD_REQUEST,
            "当前仅支持抖音、B站和本地视频。",
            status_code=400,
            data={"sourceType": parsed.source_type, "sourceUrl": parsed.url, "errorType": "unsupported_platform"},
        )

    _save_raw_extract_response(
        material_id,
        {
            "extractor": "browser_auth",
            "sourceType": parsed.source_type,
            "sourceUrl": parsed.normalized_url,
            "finalUrl": final_url,
            "responses": browser_payload.get("responses") or [],
        },
    )
    return _persist_material_metadata(material_id, payload)


def _extract_copy_pilot_material(material_id: str, parsed) -> dict:
    append_log(material_id, "[EXTRACTOR] copy_pilot")
    response_payload = copy_pilot_client.extract(parsed.normalized_url, "auto")
    append_log(material_id, "[COPY_PILOT] ok=true")
    data = response_payload.get("data") if isinstance(response_payload, dict) else None
    aweme_detail = data.get("aweme_detail") if isinstance(data, dict) else None
    if not isinstance(aweme_detail, dict):
        raise AppException(
            error_code.INTERNAL_ERROR,
            "素材提取失败：CopyPilot 返回缺少 aweme_detail。",
            status_code=500,
            data={"errorType": "extractor_failed", "sourceType": parsed.source_type, "sourceUrl": parsed.normalized_url},
        )

    final_url = str(
        _first_non_empty(
            _safe_nested(aweme_detail, "share_info", "share_url"),
            parsed.normalized_url,
        )
    )
    payload = _map_douyin_material(
        material_id=material_id,
        parsed=parsed,
        final_url=final_url,
        aweme_detail=aweme_detail,
        cache_hit=False,
        extractor="copy_pilot",
    )
    payload["video"] = {
        **(payload.get("video") or {}),
        "remoteUrl": str(_safe_nested(payload, "video", "url") or ""),
    }
    _save_raw_extract_response(material_id, response_payload if isinstance(response_payload, dict) else {"data": response_payload})
    return _persist_material_metadata(material_id, payload)


def extract_material(*, source_type: str, raw_input: str, raw_url: str = "") -> dict:
    parsed = parse_material_input(raw_input, source_type, raw_url)
    material_id = build_material_key(parsed.source_type, parsed.normalized_url)
    init_material_runtime(material_id)
    append_log(material_id, f"[RAW_INPUT] {parsed.raw_input}")
    append_log(material_id, f"[CANDIDATE_URL] {parsed.candidate_url}")
    append_log(material_id, f"[NORMALIZED_URL] {parsed.normalized_url}")
    append_log(material_id, f"[SOURCE_TYPE] {parsed.source_type}")
    existing_material = read_material(material_id) if material_json_path(material_id).exists() else None
    if existing_material is not None:
        append_log(material_id, "[CACHE_HIT] true")
        hydrated = _hydrate_local_file_state(material_id, {**existing_material, "cacheHit": True})
        if (
            hydrated.get("cacheStatus") == "local_ready"
            and hydrated.get("downloadStatus") == "downloaded"
            and hydrated.get("localFileStatus") == "exists"
        ):
            return hydrated
        if _has_material_metadata(hydrated):
            resolved_video_id = _extract_resolved_video_id(
                str(hydrated.get("finalUrl") or ""),
                str(hydrated.get("sourceUrl") or ""),
                str(hydrated.get("normalizedUrl") or ""),
            )
            reused_existing = _reuse_cached_material_source(
                target_material_id=material_id,
                parsed=parsed,
                resolved_video_id=resolved_video_id,
                reason="existing_metadata_video_id",
            )
            if reused_existing is not None:
                return reused_existing
            return download_material_video(material_id)
    reused_by_source = _reuse_cached_material_source(
        target_material_id=material_id,
        parsed=parsed,
        reason="source_url",
    )
    if reused_by_source is not None:
        return reused_by_source
    try:
        if parsed.source_type == "douyin" and settings.get_copy_pilot_enabled():
            append_log(material_id, "[COPY_PILOT_ENABLED] true")
            metadata = _extract_copy_pilot_material(material_id, parsed)
        else:
            metadata = _extract_browser_material(material_id, parsed)
        if (
            metadata.get("cacheStatus") == "local_ready"
            and metadata.get("downloadStatus") == "downloaded"
            and metadata.get("localFileStatus") == "exists"
        ):
            return metadata
        resolved_video_id = _extract_resolved_video_id(
            str(metadata.get("finalUrl") or ""),
            str(metadata.get("sourceUrl") or ""),
            str(metadata.get("normalizedUrl") or ""),
        )
        reused_by_video_id = _reuse_cached_material_source(
            target_material_id=material_id,
            parsed=parsed,
            resolved_video_id=resolved_video_id,
            reason="resolved_video_id",
        )
        if reused_by_video_id is not None:
            return reused_by_video_id
        return download_material_video(material_id)
    except AppException as exc:
        error_type = exc.data.get("errorType") if isinstance(exc.data, dict) else None
        if error_type in {"url_not_found", "unsupported_platform", "video_url_missing", "material_download_failed"}:
            raise
        if parsed.source_type == "douyin" and settings.get_copy_pilot_enabled():
            append_log(material_id, f"[EXTRACTOR_WARNING] type={error_type or 'extractor_failed'} message={exc.message}")
            raise AppException(
                error_code.INTERNAL_ERROR,
                exc.message if str(exc.message or "").startswith("素材提取失败：") else f"素材提取失败：{exc.message}",
                status_code=500,
                data={
                    "errorType": "extractor_failed",
                    "sourceType": parsed.source_type,
                    "sourceUrl": parsed.normalized_url,
                },
            ) from exc
        append_log(material_id, f"[EXTRACTOR_WARNING] type={error_type or 'extractor_failed'} message={exc.message}")
        warning_type = error_type or "extractor_failed"
        warning_message = "浏览器授权解析失败，已跳过。"
        if warning_type == "material_download_failed":
            warning_message = "素材视频下载失败，已跳过。"
        elif warning_type == "material_parse_failed":
            warning_message = "素材页面解析失败，已跳过。"
        elif warning_type == "platform_auth_expired":
            warning_message = "登录态已失效，已跳过。"
        elif warning_type == "platform_not_authorized":
            warning_message = "浏览器未完成授权，已跳过。"
        elif warning_type == "browser_open_failed":
            warning_message = "浏览器授权解析失败，已跳过。"
        elif warning_type == "page_load_failed":
            warning_message = "浏览器页面加载失败，已跳过。"
        raise AppException(
            error_code.INTERNAL_ERROR,
            "素材读取失败：浏览器授权解析失败，请重新授权或上传本地视频。",
            status_code=500,
            data={
                "errorType": "extractor_all_failed",
                "sourceType": parsed.source_type,
                "sourceUrl": parsed.normalized_url,
                "rawInput": parsed.raw_input,
                "warnings": [{"type": warning_type, "message": warning_message}],
            },
        ) from exc
    except Exception as exc:
        append_log(material_id, f"[EXTRACTOR_UNHANDLED] {type(exc).__name__}: {exc}")
        if parsed.source_type == "douyin" and settings.get_copy_pilot_enabled():
            raise AppException(
                error_code.INTERNAL_ERROR,
                "素材提取失败：CopyPilot 接口调用失败，请稍后重试。",
                status_code=500,
                data={
                    "errorType": "extractor_failed",
                    "sourceType": parsed.source_type,
                    "sourceUrl": parsed.normalized_url,
                },
            ) from exc
        raise AppException(
            error_code.INTERNAL_ERROR,
            "素材读取失败：所有解析方式均失败，请稍后重试或上传本地视频。",
            status_code=500,
            data={
                "errorType": "extractor_all_failed",
                "sourceType": parsed.source_type,
                "sourceUrl": parsed.normalized_url,
                "rawInput": parsed.raw_input,
                "warnings": [{"type": "extractor_failed", "message": "浏览器授权解析失败，已跳过。"}],
            },
        ) from exc


def upload_material(upload: UploadFile) -> dict:
    if upload is None or not upload.filename:
        raise AppException(error_code.BAD_REQUEST, "请上传本地视频文件。", status_code=400)
    material_id = f"mt_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    init_material_runtime(material_id)
    append_log(material_id, f"[UPLOAD] {upload.filename}")
    payload = _LOCAL_PROVIDER.save(material_id, upload)
    return _persist_material_metadata(material_id, _build_local_material_vo(material_id, payload))


def get_material(material_id: str) -> dict:
    path = material_json_path(material_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="素材不存在")
    return _hydrate_local_file_state(material_id, {**read_material(material_id), "cacheHit": True})


def get_material_file(material_id: str, filename: str) -> Path:
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=404, detail="素材文件不存在")
    material = get_material(material_id)
    video_url = _safe_nested(material, "video", "url") or ""
    cover_url = material.get("coverUrl") or ""
    local_video_url = material.get("localVideoUrl") or ""
    candidates = [
        Path(video_url.split("/")[-1]) if str(video_url).startswith("/api/") else None,
        Path(local_video_url.split("/")[-1]) if str(local_video_url).startswith("/api/") else None,
        Path(cover_url.split("/")[-1]) if str(cover_url).startswith("/api/") else None,
        Path("metadata.json"),
        Path("run.log"),
        Path("transcript.txt"),
        Path("subtitles.srt"),
        Path("subtitles.vtt"),
        Path("asr_text.txt"),
        Path("asr_segments.json"),
        Path("corrected_asr_text.txt"),
        Path("ocr_text.txt"),
        Path("ocr_subtitles.json"),
        Path("final_transcript.txt"),
        Path("transcription_result.json"),
    ]
    valid_names = {item.name for item in candidates if item is not None}
    if filename not in valid_names:
        raise HTTPException(status_code=404, detail="素材文件不存在")

    root = material_json_path(material_id).parent
    if filename == "metadata.json":
        target = root / "outputs" / "metadata.json"
    elif filename == "run.log":
        target = material_log_path(material_id)
    else:
        target = next((path for path in root.rglob(filename) if path.is_file()), None)
        if target is None:
            raise HTTPException(status_code=404, detail="素材文件不存在")
    return target
