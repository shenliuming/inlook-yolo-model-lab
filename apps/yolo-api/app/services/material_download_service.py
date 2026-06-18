from __future__ import annotations

import hashlib
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from app.clients.browser_client import browser_client
from app.clients.ffmpeg_client import ffmpeg_client
from app.common import error_code
from app.common.exceptions import AppException
from app.services.browser_auth_service import mark_platform_authorization_expired
from app.tasks.task_store import append_log, material_cache_dir, material_inputs_dir, material_json_path, read_material, write_material

MIN_VIDEO_SIZE_BYTES = 10 * 1024


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _local_video_path(material_id: str) -> Path:
    return material_inputs_dir(material_id) / "source.mp4"


def _local_video_url(material_id: str) -> str:
    return f"/api/v1/materials/{material_id}/files/source.mp4"


def _build_headers(material: dict[str, Any]) -> dict[str, str]:
    source_type = str(material.get("sourceType") or "").strip().lower()
    referer_map = {
        "douyin": "https://www.douyin.com/",
        "tiktok": "https://www.tiktok.com/",
        "bilibili": "https://www.bilibili.com/",
    }
    referer = referer_map.get(source_type) or str(material.get("sourceUrl") or "").strip()
    return {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
        "Referer": referer,
    }


def _collect_video_sources(material: dict[str, Any], source_index: int | None = None) -> list[dict[str, Any]]:
    video = material.get("video") if isinstance(material.get("video"), dict) else {}
    raw_sources: list[dict[str, Any]] = []
    primary_url = str(video.get("remoteUrl") or video.get("url") or "").strip()
    if primary_url.startswith(("http://", "https://")):
        raw_sources.append(
            {
                "label": "主视频",
                "url": primary_url,
                "width": video.get("width"),
                "height": video.get("height"),
                "fileSize": video.get("fileSize"),
            }
        )
    for item in video.get("sources") or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if url.startswith(("http://", "https://")):
            raw_sources.append(item)

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_sources:
        url = str(item.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(
            {
                "label": str(item.get("label") or f"备用源 {len(deduped) + 1}"),
                "url": url,
                "width": int(item.get("width") or 0),
                "height": int(item.get("height") or 0),
                "fileSize": int(item.get("fileSize") or 0),
            }
        )

    if source_index is not None:
        if source_index < 0 or source_index >= len(deduped):
            raise AppException(error_code.BAD_REQUEST, "下载源索引不存在。", status_code=400)
        return [deduped[source_index]]
    return deduped


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _save_material(material_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    current = read_material(material_id)
    merged = {**current, **payload}
    merged["materialId"] = material_id
    merged["materialKey"] = material_id
    merged["updatedAt"] = _now_iso()
    write_material(material_id, merged)
    return merged


def _build_failure_data(material_id: str, material: dict[str, Any], tried_sources: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "errorType": "material_download_failed",
        "materialId": material_id,
        "materialKey": material_id,
        "sourceType": material.get("sourceType"),
        "sourceUrl": material.get("sourceUrl"),
        "cacheStatus": material.get("cacheStatus"),
        "downloadStatus": material.get("downloadStatus"),
        "localFileStatus": material.get("localFileStatus"),
        "triedSources": tried_sources,
    }


def _raise_bilibili_download_error(message: str, *, material_id: str, source_url: str) -> None:
    text = str(message or "").strip()
    lowered = text.lower()
    if "412" in lowered:
        raise AppException(
            error_code.INTERNAL_ERROR,
            "网络或风控导致 412，请稍后重试。",
            status_code=500,
            data={"errorType": "bilibili_http_412", "materialId": material_id, "sourceType": "bilibili", "sourceUrl": source_url},
        )
    if "login required" in lowered or "需要登录" in text:
        mark_platform_authorization_expired("bilibili", "B站授权已过期，请重新授权后再读取素材。")
        raise AppException(
            error_code.INTERNAL_ERROR,
            "B站授权已过期，请重新授权后再读取素材。",
            status_code=400,
            data={"errorType": "platform_auth_expired", "materialId": material_id, "sourceType": "bilibili", "sourceUrl": source_url},
        )
    if "not found" in lowered or "unable to download webpage" in lowered or "视频不存在" in text:
        raise AppException(
            error_code.INTERNAL_ERROR,
            "视频不存在或不可访问。",
            status_code=404,
            data={"errorType": "bilibili_not_found", "materialId": material_id, "sourceType": "bilibili", "sourceUrl": source_url},
        )
    if "extractorerror" in lowered or "extractor error" in lowered or "no module named yt_dlp" in lowered:
        raise AppException(
            error_code.INTERNAL_ERROR,
            "解析失败，请更新 yt-dlp。",
            status_code=500,
            data={"errorType": "bilibili_extractor_error", "materialId": material_id, "sourceType": "bilibili", "sourceUrl": source_url},
        )
    raise AppException(
        error_code.INTERNAL_ERROR,
        "素材下载失败，请稍后重试。",
        status_code=500,
        data={"errorType": "material_download_failed", "materialId": material_id, "sourceType": "bilibili", "sourceUrl": source_url},
    )


def _find_downloaded_video(work_dir: Path) -> Path | None:
    candidates: list[Path] = []
    for ext in ("mp4", "mkv", "webm", "mov", "m4v", "flv"):
        candidates.extend(work_dir.glob(f"source.{ext}"))
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_size)


def _download_bilibili_video(material_id: str, material: dict[str, Any]) -> dict[str, Any]:
    source_url = str(material.get("canonicalUrl") or material.get("sourceUrl") or "").strip()
    cookie_path = material_cache_dir(material_id) / "bilibili.cookies.txt"
    cookie_count = browser_client.export_netscape_cookies("bilibili", cookie_path)
    if cookie_count <= 0:
        mark_platform_authorization_expired("bilibili", "B站授权已过期，请重新授权后再读取素材。")
        raise AppException(
            error_code.INTERNAL_ERROR,
            "B站授权已过期，请重新授权后再读取素材。",
            status_code=400,
            data={"errorType": "platform_auth_expired", "materialId": material_id, "sourceType": "bilibili", "sourceUrl": source_url},
        )

    source_path = _local_video_path(material_id)
    work_dir = source_path.parent
    out_template = str(work_dir / "source.%(ext)s")
    cmd = [
        shutil.which("python3") or "python3",
        "-m",
        "yt_dlp",
        "--no-playlist",
        "--cookies",
        str(cookie_path),
        "--merge-output-format",
        "mp4",
        "-o",
        out_template,
        source_url,
    ]
    append_log(material_id, f"[DOWNLOAD_ENGINE] yt_dlp cookies={cookie_count}")
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or exc.stdout or str(exc)).strip()
        append_log(material_id, f"[BILIBILI_DOWNLOAD_ERROR] {stderr}")
        _raise_bilibili_download_error(stderr, material_id=material_id, source_url=source_url)
    except Exception as exc:
        append_log(material_id, f"[BILIBILI_DOWNLOAD_EXCEPTION] {exc}")
        _raise_bilibili_download_error(str(exc), material_id=material_id, source_url=source_url)

    downloaded = _find_downloaded_video(work_dir)
    if downloaded is None or not downloaded.exists():
        raise AppException(
            error_code.INTERNAL_ERROR,
            "素材下载失败：未生成本地视频文件。",
            status_code=500,
            data={"errorType": "material_download_failed", "materialId": material_id, "sourceType": "bilibili", "sourceUrl": source_url},
        )

    if downloaded.resolve() != source_path.resolve():
        if source_path.exists():
            source_path.unlink()
        downloaded.replace(source_path)

    metadata = ffmpeg_client.probe_video(source_path)
    if int(metadata.get("width") or 0) <= 0 or int(metadata.get("height") or 0) <= 0 or float(metadata.get("duration") or 0) <= 0:
        raise AppException(
            error_code.INTERNAL_ERROR,
            "素材下载失败：本地视频校验失败。",
            status_code=500,
            data={"errorType": "ffprobe_failed", "materialId": material_id, "sourceType": "bilibili", "sourceUrl": source_url},
        )
    file_hash = _sha256_file(source_path)
    updated = _save_material(
        material_id,
        {
            "downloadStatus": "downloaded",
            "localFileStatus": "exists",
            "cacheStatus": "local_ready",
            "localVideoPath": str(source_path),
            "localVideoUrl": _local_video_url(material_id),
            "localFileSize": int(source_path.stat().st_size),
            "videoPath": str(source_path),
            "localFileHash": file_hash,
            "downloadedAt": _now_iso(),
            "lastCheckAt": _now_iso(),
            "lastError": None,
            "triedSources": [{"label": "yt-dlp", "url": source_url, "status": "success"}],
            "status": "ready",
            "video": {
                **(material.get("video") or {}),
                "url": _local_video_url(material_id),
                "remoteUrl": source_url,
                "width": int(metadata.get("width") or 0),
                "height": int(metadata.get("height") or 0),
                "duration": float(metadata.get("duration") or 0.0),
                "fileSize": int(source_path.stat().st_size),
            },
        },
    )
    append_log(material_id, f"[DOWNLOAD_SUCCESS] size={updated.get('localFileSize')} path={source_path.name}")
    return updated


def download_material_video(material_id: str, source_index: int | None = None) -> dict[str, Any]:
    if not material_json_path(material_id).exists():
        raise AppException(error_code.NOT_FOUND, "素材不存在。", status_code=404)

    material = read_material(material_id)
    source_path = _local_video_path(material_id)
    tmp_path = source_path.with_suffix(".mp4.tmp")
    headers = _build_headers(material)
    tried_sources: list[dict[str, Any]] = []
    existing_file_exists = source_path.exists()
    existing_status = str(material.get("localFileStatus") or "").strip()

    if (
        existing_file_exists
        and str(material.get("cacheStatus") or "") == "local_ready"
        and str(material.get("downloadStatus") or "") == "downloaded"
        and existing_status == "exists"
    ):
        return material

    if str(material.get("sourceType") or "").strip().lower() == "bilibili":
        _save_material(material_id, {"downloadStatus": "downloading", "lastCheckAt": _now_iso(), "triedSources": []})
        return _download_bilibili_video(material_id, material)

    sources = _collect_video_sources(material, source_index)
    if not sources:
        updated = _save_material(
            material_id,
            {
                "downloadStatus": "failed",
                "localFileStatus": "missing",
                "cacheStatus": "metadata_cached",
                "localVideoPath": None,
                "localVideoUrl": None,
                "lastCheckAt": _now_iso(),
                "lastError": "未解析到可下载的视频地址",
                "triedSources": [],
            },
        )
        raise AppException(
            error_code.INTERNAL_ERROR,
            "素材下载失败：未解析到可下载的视频地址，请重试或上传本地视频。",
            status_code=500,
            data={
                "errorType": "video_url_missing",
                "materialId": material_id,
                "materialKey": material_id,
                "sourceType": material.get("sourceType"),
                "sourceUrl": material.get("sourceUrl"),
                "cacheStatus": updated.get("cacheStatus"),
                "downloadStatus": updated.get("downloadStatus"),
                "localFileStatus": updated.get("localFileStatus"),
                "triedSources": [],
            },
        )

    _save_material(material_id, {"downloadStatus": "downloading", "lastCheckAt": _now_iso(), "triedSources": []})

    for index, source in enumerate(sources):
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        try:
            append_log(material_id, f"[DOWNLOAD_SOURCE] index={index} label={source['label']} url={source['url']}")
            with httpx.stream(
                "GET",
                source["url"],
                headers=headers,
                timeout=60.0,
                follow_redirects=True,
            ) as response:
                if response.status_code >= 400:
                    error_type = "source_forbidden" if response.status_code == 403 else "material_download_failed"
                    raise AppException(
                        error_code.INTERNAL_ERROR,
                        f"视频源下载失败：HTTP {response.status_code}",
                        status_code=500,
                        data={"errorType": error_type},
                    )
                with tmp_path.open("wb") as file:
                    for chunk in response.iter_bytes():
                        if chunk:
                            file.write(chunk)

            file_size = tmp_path.stat().st_size if tmp_path.exists() else 0
            if file_size < MIN_VIDEO_SIZE_BYTES:
                raise AppException(
                    error_code.INTERNAL_ERROR,
                    "视频源下载失败：文件过小。",
                    status_code=500,
                    data={"errorType": "source_invalid"},
                )

            metadata = ffmpeg_client.probe_video(tmp_path)
            if int(metadata.get("width") or 0) <= 0 or int(metadata.get("height") or 0) <= 0 or float(metadata.get("duration") or 0) <= 0:
                raise AppException(
                    error_code.INTERNAL_ERROR,
                    "视频源下载失败：ffprobe 校验失败。",
                    status_code=500,
                    data={"errorType": "ffprobe_failed"},
                )

            if source_path.exists():
                source_path.unlink()
            tmp_path.replace(source_path)
            file_hash = _sha256_file(source_path)
            updated = _save_material(
                material_id,
                {
                    "downloadStatus": "downloaded",
                    "localFileStatus": "exists",
                    "cacheStatus": "local_ready",
                    "localVideoPath": str(source_path),
                    "localVideoUrl": _local_video_url(material_id),
                    "localFileSize": int(source_path.stat().st_size),
                    "localFileHash": file_hash,
                    "downloadedAt": _now_iso(),
                    "lastCheckAt": _now_iso(),
                    "lastError": None,
                    "triedSources": tried_sources + [{"label": source["label"], "url": source["url"], "status": "success"}],
                    "status": "ready",
                    "video": {
                        **(material.get("video") or {}),
                        "url": _local_video_url(material_id),
                        "remoteUrl": str(material.get("video", {}).get("remoteUrl") or material.get("video", {}).get("url") or source["url"]),
                        "width": int(metadata.get("width") or 0),
                        "height": int(metadata.get("height") or 0),
                        "duration": float(metadata.get("duration") or 0.0),
                        "fileSize": int(source_path.stat().st_size),
                    },
                },
            )
            append_log(material_id, f"[DOWNLOAD_SUCCESS] size={updated.get('localFileSize')} path={source_path.name}")
            return updated
        except httpx.TimeoutException:
            tried_sources.append({"label": source["label"], "url": source["url"], "errorType": "source_timeout", "message": "下载超时"})
        except AppException as exc:
            tried_sources.append(
                {
                    "label": source["label"],
                    "url": source["url"],
                    "errorType": (exc.data or {}).get("errorType") if isinstance(exc.data, dict) else "material_download_failed",
                    "message": exc.message,
                }
            )
        except Exception as exc:
            tried_sources.append({"label": source["label"], "url": source["url"], "errorType": "material_download_failed", "message": str(exc)})
        finally:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    failure_payload = {
        "downloadStatus": "failed",
        "localFileStatus": "invalid" if existing_file_exists or existing_status == "invalid" else "missing",
        "cacheStatus": "local_invalid" if existing_file_exists or existing_status == "invalid" else "metadata_cached",
        "localVideoPath": None,
        "localVideoUrl": None,
        "localFileSize": None,
        "lastCheckAt": _now_iso(),
        "lastError": "本地视频文件无效，重新下载失败" if existing_file_exists or existing_status == "invalid" else "所有视频源下载失败",
        "triedSources": tried_sources,
        "status": "metadata_cached",
    }
    updated = _save_material(material_id, failure_payload)
    append_log(material_id, f"[DOWNLOAD_FAILED] tried={len(tried_sources)}")
    raise AppException(
        error_code.INTERNAL_ERROR,
        "素材下载失败：所有视频源均不可访问，请重试或上传本地视频。",
        status_code=500,
        data=_build_failure_data(material_id, updated, tried_sources),
    )
