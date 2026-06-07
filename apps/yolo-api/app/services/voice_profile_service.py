from __future__ import annotations

import json
import logging
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile

from app.clients.moss_tts_client import moss_tts_client
from app.common import error_code
from app.common.exceptions import AppException
from app.config.paths import BACKEND_DIR, CONTENT_LAB_VOICES_RUNTIME_DIR
from app.services.material_service import get_material, get_material_file
from app.config.settings import get_moss_tts_execution_provider
from app.utils.file_utils import safe_filename
from app.utils.subprocess_utils import run_command

logger = logging.getLogger("inlook.yolo_api")

VOICES_ROOT = CONTENT_LAB_VOICES_RUNTIME_DIR
VOICES_ROOT.mkdir(parents=True, exist_ok=True)
VOICE_INDEX_PATH = VOICES_ROOT.parent / "index" / "voices.json"

MAX_REFERENCE_AUDIO_BYTES = 100 * 1024 * 1024
MIN_REFERENCE_SECONDS = 10.0
RECOMMENDED_REFERENCE_SECONDS = 30.0
MAX_REFERENCE_SECONDS = 300.0
MAX_VIDEO_REFERENCE_SCAN_SECONDS = 180.0
TARGET_VIDEO_REFERENCE_SECONDS = 30.0
MIN_VIDEO_SPEECH_SECONDS = 8.0
REFERENCE_SAMPLE_RATE = 16000
LOW_MEAN_VOLUME_DB = -45.0
LOW_MAX_VOLUME_DB = -35.0
CLEAN_REFERENCE_VERSION = "clean_segment_v1"

BUILTIN_VOICES = [
    {"voiceId": "male_magnetic", "name": "磁性男声", "type": "builtin", "mossVoice": "Junhao"},
    {"voiceId": "female_warm", "name": "温柔女声", "type": "builtin", "mossVoice": "Ava"},
    {"voiceId": "teacher_knowledge", "name": "知识老师", "type": "builtin", "mossVoice": "Junhao"},
    {"voiceId": "normal_speaker", "name": "普通人口播", "type": "builtin", "mossVoice": "Junhao"},
]

VOICE_ALIASES = {
    "磁性男声": "male_magnetic",
    "温柔女声": "female_warm",
    "知识老师": "teacher_knowledge",
    "普通人口播": "normal_speaker",
    "preset-junhao": "male_magnetic",
    "preset-ava": "female_warm",
    "preset-teacher": "teacher_knowledge",
    "preset-normal": "normal_speaker",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_voice_id() -> str:
    return f"voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"


def voice_dir(voice_id: str) -> Path:
    return VOICES_ROOT / voice_id


def voice_json_path(voice_id: str) -> Path:
    return voice_dir(voice_id) / "voice.json"


def voice_index_path() -> Path:
    return VOICE_INDEX_PATH


def _relative_runtime_path(path: Path) -> str:
    try:
        return str(path.relative_to(BACKEND_DIR))
    except ValueError:
        return str(path)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_voice_index() -> list[dict[str, Any]]:
    path = voice_index_path()
    if not path.exists():
        return []
    try:
        payload = read_json(path)
    except Exception:
        logger.warning("voice index read failed: %s", path, exc_info=True)
        return []
    voices = payload.get("voices") if isinstance(payload, dict) else payload
    return voices if isinstance(voices, list) else []


def write_voice_index(voices: list[dict[str, Any]]) -> None:
    write_json(
        voice_index_path(),
        {
            "voices": voices,
            "updatedAt": now(),
        },
    )


def normalize_voice_source(profile: dict[str, Any]) -> str:
    source = str(profile.get("source") or "").strip()
    # Older "current video voice" profiles were persisted as source="material".
    # Treat them as current_video so one material cannot keep creating duplicates.
    if source == "material":
        return "current_video"
    return source


def normalize_legacy_current_video_profile(profile: dict[str, Any], material_key: str = "") -> dict[str, Any]:
    next_profile = dict(profile)
    changed = False
    if normalize_voice_source(next_profile) == "current_video" and next_profile.get("source") != "current_video":
        next_profile["source"] = "current_video"
        changed = True
    if material_key and not next_profile.get("materialKey"):
        next_profile["materialKey"] = material_key
        changed = True
    if changed:
        next_profile["updatedAt"] = now()
    return next_profile


def voice_index_entry(profile: dict[str, Any]) -> dict[str, Any]:
    source = normalize_voice_source(profile)
    return {
        "voiceId": profile.get("voiceId"),
        "name": profile.get("name"),
        "type": profile.get("type", "custom"),
        "source": source,
        "materialId": profile.get("materialId"),
        "materialKey": profile.get("materialKey"),
        "referenceAudioPath": profile.get("referenceAudioPath"),
        "status": profile.get("status", "ready"),
        "createdAt": profile.get("createdAt"),
        "updatedAt": profile.get("updatedAt"),
    }


def upsert_voice_index(profile: dict[str, Any]) -> None:
    entry = voice_index_entry(profile)
    voice_id = str(entry.get("voiceId") or "")
    if not voice_id:
        return
    existing = [item for item in read_voice_index() if item.get("voiceId") != voice_id]
    existing.append(entry)
    write_voice_index(existing)


def find_current_video_voice(material_id: str, material_key: str = "") -> dict[str, Any] | None:
    for item in read_voice_index():
        if normalize_voice_source(item) != "current_video":
            continue
        if item.get("status") != "ready":
            continue
        if item.get("materialId") == material_id or (material_key and item.get("materialKey") == material_key):
            voice_id = str(item.get("voiceId") or "")
            if not voice_id:
                continue
            path = voice_json_path(voice_id)
            if path.exists():
                profile = read_json(path)
                return normalize_legacy_current_video_profile(profile, material_key)

    for path in sorted(VOICES_ROOT.glob("voice_*/voice.json")):
        try:
            profile = read_json(path)
        except Exception:
            continue
        if normalize_voice_source(profile) != "current_video":
            continue
        if profile.get("status") != "ready":
            continue
        if profile.get("materialId") == material_id or (material_key and profile.get("materialKey") == material_key):
            profile = normalize_legacy_current_video_profile(profile, material_key)
            write_json(voice_json_path(profile["voiceId"]), profile)
            upsert_voice_index(profile)
            return profile
    return None


def _save_upload(upload: UploadFile, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with destination.open("wb") as file:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_REFERENCE_AUDIO_BYTES:
                raise AppException(
                    error_code.BAD_REQUEST,
                    "音频文件过大，请上传 5 分钟以内的清晰人声。",
                    data={"errorType": "voice_audio_too_large"},
                    status_code=400,
                )
            file.write(chunk)
    if total <= 0:
        raise AppException(
            error_code.BAD_REQUEST,
            "未读取到有效音频，请重新上传。",
            data={"errorType": "voice_audio_empty"},
            status_code=400,
        )
    return destination


def _probe_audio(audio_path: Path) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "format=duration,size:stream=sample_rate,channels,duration",
        "-of",
        "json",
        str(audio_path),
    ]
    result = run_command(command)
    if result.returncode != 0:
        raise AppException(
            error_code.BAD_REQUEST,
            "音频读取失败，请上传常见格式的清晰人声文件。",
            data={"errorType": "voice_audio_probe_failed"},
            status_code=400,
        )
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise AppException(
            error_code.BAD_REQUEST,
            "音频读取失败，请重新上传。",
            data={"errorType": "voice_audio_probe_failed"},
            status_code=400,
        ) from exc
    stream = (payload.get("streams") or [{}])[0]
    format_payload = payload.get("format") or {}
    duration = _safe_float(format_payload.get("duration") or stream.get("duration"))
    return {
        "duration": round(duration, 3),
        "sampleRate": int(stream.get("sample_rate") or 0),
        "channels": int(stream.get("channels") or 0),
        "size": int(format_payload.get("size") or audio_path.stat().st_size),
    }


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _normalize_reference_audio(source_path: Path, destination_path: Path) -> Path:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_path),
        "-vn",
        "-af",
        "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.2,"
        "areverse,silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.2,areverse",
        "-t",
        str(int(MAX_REFERENCE_SECONDS)),
        "-ar",
        str(REFERENCE_SAMPLE_RATE),
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(destination_path),
    ]
    result = run_command(command)
    if result.returncode != 0 or not destination_path.exists() or destination_path.stat().st_size <= 44:
        logger.warning("voice normalize failed: %s", result.stdout[-1200:])
        raise AppException(
            error_code.BAD_REQUEST,
            "音频处理失败，请上传清晰人声 wav/mp3/m4a 文件。",
            data={"errorType": "voice_audio_normalize_failed"},
            status_code=400,
        )
    return destination_path


def _extract_video_audio_candidate(source_path: Path, destination_path: Path) -> Path:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_path),
        "-vn",
        "-t",
        str(int(MAX_VIDEO_REFERENCE_SCAN_SECONDS)),
        "-af",
        "highpass=f=80,lowpass=f=7600,afftdn=nf=-25,dynaudnorm=f=75:g=7",
        "-ar",
        str(REFERENCE_SAMPLE_RATE),
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(destination_path),
    ]
    result = run_command(command)
    if result.returncode != 0 or not destination_path.exists() or destination_path.stat().st_size <= 44:
        logger.warning("current video voice candidate extract failed: %s", result.stdout[-1200:])
        raise AppException(
            error_code.BAD_REQUEST,
            "当前视频音频提取失败，请上传单独的清晰人声音频。",
            data={"errorType": "material_voice_audio_extract_failed"},
            status_code=400,
        )
    return destination_path


def _detect_non_silent_segments(audio_path: Path, *, noise_db: int = -35, min_silence: float = 0.35) -> list[dict[str, float]]:
    metadata = _probe_audio(audio_path)
    duration = float(metadata.get("duration") or 0.0)
    if duration <= 0:
        return []
    result = run_command(
        [
            "ffmpeg",
            "-i",
            str(audio_path),
            "-af",
            f"silencedetect=noise={noise_db}dB:d={min_silence}",
            "-f",
            "null",
            "-",
        ]
    )
    output = result.stdout or ""
    events: list[tuple[str, float]] = []
    for line in output.splitlines():
        start_match = re.search(r"silence_start:\s*([0-9.]+)", line)
        if start_match:
            events.append(("start", _safe_float(start_match.group(1))))
            continue
        end_match = re.search(r"silence_end:\s*([0-9.]+)", line)
        if end_match:
            events.append(("end", _safe_float(end_match.group(1))))

    segments: list[dict[str, float]] = []
    cursor = 0.0
    for event, value in events:
        if event == "start":
            if value > cursor:
                segment_duration = value - cursor
                if segment_duration >= 0.5:
                    segments.append({"start": round(cursor, 3), "end": round(value, 3), "duration": round(segment_duration, 3)})
        elif event == "end":
            cursor = min(max(value, 0.0), duration)
    if cursor < duration:
        segment_duration = duration - cursor
        if segment_duration >= 0.5:
            segments.append({"start": round(cursor, 3), "end": round(duration, 3), "duration": round(segment_duration, 3)})
    return segments


def _select_reference_window(segments: list[dict[str, float]], total_duration: float) -> dict[str, float]:
    if total_duration <= 0:
        raise AppException(
            error_code.BAD_REQUEST,
            "当前视频没有可用音频，请上传单独的清晰人声音频。",
            data={"errorType": "material_voice_audio_empty"},
            status_code=400,
        )
    if not segments:
        raise AppException(
            error_code.BAD_REQUEST,
            "当前视频未检测到足够清晰的人声，请上传单独的清晰人声音频。",
            data={"errorType": "material_voice_speech_not_found"},
            status_code=400,
        )

    best_window: dict[str, float] | None = None
    best_speech_duration = 0.0
    for start_index, start_segment in enumerate(segments):
        window_start = float(start_segment["start"])
        speech_duration = 0.0
        window_end = window_start
        for segment in segments[start_index:]:
            segment_start = float(segment["start"])
            segment_end = float(segment["end"])
            if segment_start - window_start > TARGET_VIDEO_REFERENCE_SECONDS:
                break
            window_end = min(segment_end, window_start + TARGET_VIDEO_REFERENCE_SECONDS)
            speech_duration += max(0.0, min(segment_end, window_end) - segment_start)
            window_duration = window_end - window_start
            if speech_duration >= MIN_VIDEO_SPEECH_SECONDS and window_duration >= MIN_REFERENCE_SECONDS:
                return {
                    "start": round(window_start, 3),
                    "duration": round(min(TARGET_VIDEO_REFERENCE_SECONDS, max(MIN_REFERENCE_SECONDS, window_duration)), 3),
                    "speechDuration": round(speech_duration, 3),
                }
        if speech_duration > best_speech_duration:
            best_speech_duration = speech_duration
            best_window = {
                "start": round(window_start, 3),
                "duration": round(min(TARGET_VIDEO_REFERENCE_SECONDS, max(MIN_REFERENCE_SECONDS, total_duration - window_start)), 3),
                "speechDuration": round(speech_duration, 3),
            }

    if not best_window or best_speech_duration < MIN_VIDEO_SPEECH_SECONDS:
        raise AppException(
            error_code.BAD_REQUEST,
            "当前视频人声片段太短或不够清晰，请上传至少 10 秒以上的清晰人声音频。",
            data={"errorType": "material_voice_speech_too_short"},
            status_code=400,
        )
    return best_window


def _cut_reference_window(candidate_path: Path, destination_path: Path, window: dict[str, float]) -> Path:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-ss",
        str(window["start"]),
        "-t",
        str(window["duration"]),
        "-i",
        str(candidate_path),
        "-af",
        "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.15,"
        "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.15,areverse,"
        "loudnorm=I=-18:TP=-2:LRA=11",
        "-ar",
        str(REFERENCE_SAMPLE_RATE),
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(destination_path),
    ]
    result = run_command(command)
    if result.returncode != 0 or not destination_path.exists() or destination_path.stat().st_size <= 44:
        logger.warning("current video reference cut failed: %s", result.stdout[-1200:])
        raise AppException(
            error_code.BAD_REQUEST,
            "当前视频人声参考音频提取失败，请上传单独的清晰人声音频。",
            data={"errorType": "material_voice_reference_extract_failed"},
            status_code=400,
        )
    return destination_path


def _extract_clean_reference_audio_from_video(source_path: Path, destination_path: Path, samples_dir: Path) -> dict[str, Any]:
    candidate_path = samples_dir / "current_video_voice_candidate.wav"
    _extract_video_audio_candidate(source_path, candidate_path)
    candidate_metadata = _probe_audio(candidate_path)
    segments = _detect_non_silent_segments(candidate_path)
    window = _select_reference_window(segments, float(candidate_metadata.get("duration") or 0.0))
    _cut_reference_window(candidate_path, destination_path, window)
    metadata = _probe_audio(destination_path)
    if float(metadata.get("duration") or 0.0) < MIN_REFERENCE_SECONDS:
        raise AppException(
            error_code.BAD_REQUEST,
            "当前视频可用人声不足 10 秒，请上传单独的清晰人声音频。",
            data={"errorType": "material_voice_reference_too_short"},
            status_code=400,
        )
    return {
        "version": CLEAN_REFERENCE_VERSION,
        "mode": "clean_voice_segment",
        "candidateDuration": candidate_metadata.get("duration"),
        "start": window["start"],
        "duration": metadata.get("duration"),
        "speechDuration": window["speechDuration"],
        "segmentsDetected": len(segments),
    }


def _measure_volume(audio_path: Path) -> dict[str, float]:
    result = run_command(["ffmpeg", "-i", str(audio_path), "-af", "volumedetect", "-f", "null", "-"])
    output = result.stdout or ""
    mean_match = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", output)
    max_match = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", output)
    return {
        "meanVolumeDb": float(mean_match.group(1)) if mean_match else -99.0,
        "maxVolumeDb": float(max_match.group(1)) if max_match else -99.0,
    }


def _build_quality(metadata: dict[str, Any], volume: dict[str, float]) -> dict[str, Any]:
    warnings: list[str] = []
    duration = float(metadata.get("duration") or 0.0)
    if duration < MIN_REFERENCE_SECONDS:
        raise AppException(
            error_code.SOURCE_TEXT_NOT_READY,
            "音频太短，请上传至少 10 秒以上的清晰人声。",
            data={"errorType": "voice_audio_too_short"},
            status_code=400,
        )
    if duration < RECOMMENDED_REFERENCE_SECONDS:
        warnings.append("建议上传 30 秒以上的人声，音色稳定性会更好。")
    if volume["meanVolumeDb"] < LOW_MEAN_VOLUME_DB or volume["maxVolumeDb"] < LOW_MAX_VOLUME_DB:
        raise AppException(
            error_code.SOURCE_TEXT_NOT_READY,
            "音频音量太低，请重新上传更清晰的人声。",
            data={"errorType": "voice_audio_volume_too_low"},
            status_code=400,
        )
    if volume["meanVolumeDb"] < -32.0:
        warnings.append("音量略低，建议使用更靠近麦克风的录音。")
    return {
        "ok": True,
        "warnings": warnings,
        "meanVolumeDb": round(volume["meanVolumeDb"], 2),
        "maxVolumeDb": round(volume["maxVolumeDb"], 2),
    }


def normalize_voice_id(raw_voice_id: str | None) -> str:
    normalized = (raw_voice_id or "").strip()
    return VOICE_ALIASES.get(normalized, normalized)


def get_builtin_voice(voice_id: str | None) -> dict[str, Any] | None:
    normalized = normalize_voice_id(voice_id)
    return next((voice for voice in BUILTIN_VOICES if voice["voiceId"] == normalized), None)


def current_tts_supports_custom_voice() -> bool:
    return True


def is_clean_reference_profile(profile: dict[str, Any]) -> bool:
    extraction = profile.get("referenceExtraction") or {}
    return extraction.get("version") == CLEAN_REFERENCE_VERSION and (voice_dir(str(profile.get("voiceId"))) / "reference.wav").exists()


def create_voice_profile(*, name: str, audio: UploadFile | None, consent: bool) -> dict[str, Any]:
    clean_name = (name or "").strip() or "我的音色"
    if not consent:
        raise AppException(
            error_code.BAD_REQUEST,
            "请先确认该声音属于本人或已获得授权。",
            data={"errorType": "consent_required"},
            status_code=400,
        )
    if audio is None or not audio.filename:
        raise AppException(
            error_code.BAD_REQUEST,
            "请上传参考音频。",
            data={"errorType": "voice_audio_required"},
            status_code=400,
        )

    voice_id = build_voice_id()
    root = voice_dir(voice_id)
    samples_dir = root / "samples"
    root.mkdir(parents=True, exist_ok=True)
    samples_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(safe_filename(audio.filename)).suffix or ".wav"
    source_path = samples_dir / f"source{suffix}"
    reference_path = root / "reference.wav"
    preview_path = root / "preview.wav"

    try:
        _save_upload(audio, source_path)
        original_metadata = _probe_audio(source_path)
        _normalize_reference_audio(source_path, reference_path)
        metadata = _probe_audio(reference_path)
        volume = _measure_volume(reference_path)
        quality = _build_quality(metadata, volume)
        if original_metadata.get("duration", 0.0) > MAX_REFERENCE_SECONDS:
            quality["warnings"].append("原始音频超过 5 分钟，已截取前 5 分钟用于创建音色。")

        created_at = now()
        profile = {
            "voiceId": voice_id,
            "name": clean_name,
            "type": "custom",
            "status": "ready",
            "source": "upload",
            "referenceAudioPath": _relative_runtime_path(reference_path),
            "previewAudioPath": _relative_runtime_path(preview_path),
            "duration": metadata["duration"],
            "sampleRate": metadata["sampleRate"],
            "channels": metadata["channels"],
            "quality": quality,
            "createdAt": created_at,
            "updatedAt": created_at,
        }
        write_json(voice_json_path(voice_id), profile)
        upsert_voice_index(profile)
        return voice_profile_to_vo(profile)
    except AppException:
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
        raise
    except Exception as exc:
        logger.exception("voice profile create failed")
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
        raise AppException(
            error_code.INTERNAL_ERROR,
            "音色创建失败，请重新上传清晰人声。",
            data={"errorType": "voice_create_failed"},
            status_code=500,
        ) from exc


def create_voice_profile_from_material(*, material_id: str, name: str, consent: bool, force: bool = False) -> dict[str, Any]:
    clean_name = (name or "").strip() or "当前视频音色"
    if not consent:
        raise AppException(
            error_code.BAD_REQUEST,
            "请先确认该声音属于本人或已获得授权。",
            data={"errorType": "consent_required"},
            status_code=400,
        )

    material = get_material(material_id)
    material_key = str(material.get("materialKey") or material_id)
    existing: dict[str, Any] | None = None
    if not force:
        existing = find_current_video_voice(material_id, material_key)
        if existing and is_clean_reference_profile(existing):
            return voice_profile_to_vo(existing, reused=True)

    if not (
        material.get("cacheStatus") == "local_ready"
        and material.get("downloadStatus") == "downloaded"
        and material.get("localFileStatus") == "exists"
    ):
        raise AppException(
            error_code.BAD_REQUEST,
            "请先读取并下载可用的视频素材。",
            data={"errorType": "material_not_ready", "materialId": material_id},
            status_code=400,
        )

    try:
        source_video = get_material_file(material_id, "source.mp4")
    except Exception as exc:
        raise AppException(
            error_code.BAD_REQUEST,
            "当前素材缺少本地视频，请重新读取素材。",
            data={"errorType": "material_video_missing", "materialId": material_id},
            status_code=400,
        ) from exc

    voice_id = str(existing.get("voiceId")) if existing else build_voice_id()
    root = voice_dir(voice_id)
    samples_dir = root / "samples"
    root.mkdir(parents=True, exist_ok=True)
    samples_dir.mkdir(parents=True, exist_ok=True)

    reference_path = root / "reference.wav"
    preview_path = root / "preview.wav"
    try:
        write_json(
            samples_dir / "source_material.json",
            {
                "materialId": material_id,
                "materialKey": material_key,
                "sourceType": material.get("sourceType"),
                "sourceUrl": material.get("sourceUrl"),
                "title": material.get("title"),
                "createdAt": now(),
            },
        )
        working_reference_path = samples_dir / "reference_clean.wav" if existing else reference_path
        reference_extraction = _extract_clean_reference_audio_from_video(source_video, working_reference_path, samples_dir)
        metadata = _probe_audio(working_reference_path)
        volume = _measure_volume(working_reference_path)
        quality = _build_quality(metadata, volume)
        quality["warnings"].append("已从当前视频自动截取一段人声作为参考音频，请先试听确认是否干净。")
        if working_reference_path != reference_path:
            shutil.copyfile(working_reference_path, reference_path)

        created_at = now()
        profile = {
            "voiceId": voice_id,
            "name": clean_name,
            "type": "custom",
            "status": "ready",
            "source": "current_video",
            "materialId": material_id,
            "materialKey": material_key,
            "referenceAudioPath": _relative_runtime_path(reference_path),
            "previewAudioPath": _relative_runtime_path(preview_path),
            "duration": metadata["duration"],
            "sampleRate": metadata["sampleRate"],
            "channels": metadata["channels"],
            "quality": quality,
            "referenceExtraction": reference_extraction,
            "createdAt": created_at,
            "updatedAt": created_at,
        }
        if existing:
            profile["createdAt"] = existing.get("createdAt") or created_at
        write_json(voice_json_path(voice_id), profile)
        upsert_voice_index(profile)
        return voice_profile_to_vo(profile, reused=bool(existing))
    except AppException:
        if root.exists() and not existing:
            shutil.rmtree(root, ignore_errors=True)
        raise
    except Exception as exc:
        logger.exception("voice profile from material failed")
        if root.exists() and not existing:
            shutil.rmtree(root, ignore_errors=True)
        raise AppException(
            error_code.INTERNAL_ERROR,
            "当前视频音色提取失败，请上传单独音频或重新读取素材。",
            data={"errorType": "material_voice_create_failed", "materialId": material_id},
            status_code=500,
        ) from exc


def read_voice_profile(voice_id: str) -> dict[str, Any]:
    normalized = normalize_voice_id(voice_id)
    path = voice_json_path(normalized)
    if not path.exists():
        raise AppException(
            error_code.NOT_FOUND,
            "音色不存在。",
            data={"errorType": "voice_not_found", "voiceId": voice_id},
            status_code=404,
        )
    return read_json(path)


def voice_profile_to_vo(profile: dict[str, Any], *, reused: bool | None = None) -> dict[str, Any]:
    voice_id = profile.get("voiceId")
    voice_type = profile.get("type", "custom")
    payload = {
        "voiceId": voice_id,
        "name": profile.get("name"),
        "type": voice_type,
        "source": normalize_voice_source(profile),
        "materialId": profile.get("materialId"),
        "materialKey": profile.get("materialKey"),
        "status": profile.get("status", "ready"),
        "previewUrl": f"/api/v1/voices/{voice_id}/preview",
        "referenceAudioUrl": f"/api/v1/voices/{voice_id}/reference.wav" if voice_type == "custom" else "",
        "duration": profile.get("duration"),
        "sampleRate": profile.get("sampleRate"),
        "channels": profile.get("channels"),
        "quality": profile.get("quality") or {"ok": True, "warnings": []},
        "referenceExtraction": profile.get("referenceExtraction") or {},
        "createdAt": profile.get("createdAt"),
        "updatedAt": profile.get("updatedAt"),
    }
    if reused is not None:
        payload["reused"] = reused
    return payload


def list_voice_profiles() -> dict[str, list[dict[str, Any]]]:
    custom_voices: list[dict[str, Any]] = []
    for path in sorted(VOICES_ROOT.glob("voice_*/voice.json")):
        try:
            profile = read_json(path)
            custom_voices.append(voice_profile_to_vo(profile))
            upsert_voice_index(profile)
        except Exception:
            logger.warning("skip invalid voice profile: %s", path, exc_info=True)
    builtin = [
        {"voiceId": voice["voiceId"], "name": voice["name"], "type": "builtin", "status": "ready"}
        for voice in BUILTIN_VOICES
    ]
    return {"voices": [*builtin, *custom_voices]}


def resolve_voice_for_synthesis(voice_id: str | None) -> dict[str, Any]:
    normalized = normalize_voice_id(voice_id)
    builtin = get_builtin_voice(normalized)
    if builtin:
        return {
            "voiceId": builtin["voiceId"],
            "name": builtin["name"],
            "type": "builtin",
            "mossVoice": builtin["mossVoice"],
            "promptAudioPath": "",
            "voiceMode": "preset",
        }
    profile = read_voice_profile(normalized)
    if not current_tts_supports_custom_voice():
        raise AppException(
            error_code.INTERNAL_ERROR,
            "当前 TTS 引擎暂不支持自定义音色，请先使用内置音色。",
            data={"errorType": "custom_voice_not_supported", "voiceId": normalized},
            status_code=500,
        )
    if profile.get("status") != "ready":
        raise AppException(
            error_code.BAD_REQUEST,
            "音色尚未创建完成，请稍后再试。",
            data={"errorType": "voice_not_ready", "voiceId": normalized},
            status_code=400,
        )
    reference_path = voice_dir(normalized) / "reference.wav"
    if not reference_path.exists():
        raise AppException(
            error_code.INTERNAL_ERROR,
            "自定义音色缺少参考音频，请重新创建音色。",
            data={"errorType": "voice_reference_missing", "voiceId": normalized},
            status_code=500,
        )
    return {
        "voiceId": normalized,
        "name": profile.get("name"),
        "type": "custom",
        "mossVoice": "Junhao",
        "promptAudioPath": str(reference_path),
        "voiceMode": "clone",
    }


def create_voice_preview(*, voice_id: str, text: str) -> dict[str, Any]:
    voice = resolve_voice_for_synthesis(voice_id)
    clean_text = (text or "").strip() or "你好，这是当前音色的一段试听。"
    if len(clean_text) > 160:
        clean_text = clean_text[:160]

    root = voice_dir(voice["voiceId"]) if voice["type"] == "custom" else VOICES_ROOT / "_builtin_previews" / voice["voiceId"]
    root.mkdir(parents=True, exist_ok=True)
    text_path = root / "preview_text.txt"
    output_path = root / "preview.wav"
    text_path.write_text(clean_text, encoding="utf-8")

    try:
        moss_tts_client.generate(
            text_path=text_path,
            output_path=output_path,
            prompt_audio_path=Path(voice["promptAudioPath"]) if voice["promptAudioPath"] else None,
            execution_provider=get_moss_tts_execution_provider(),
            voice=voice["mossVoice"],
            model_dir=None,
            on_log=lambda line: logger.info("voice preview %s: %s", voice["voiceId"], line.strip()),
        )
    except Exception as exc:
        logger.exception("voice preview failed")
        raise AppException(
            error_code.INTERNAL_ERROR,
            "音色试听生成失败，请检查 TTS 引擎配置。",
            data={"errorType": "voice_preview_failed", "voiceId": voice["voiceId"]},
            status_code=500,
        ) from exc

    return {
        "voiceId": voice["voiceId"],
        "audioUrl": f"/api/v1/voices/{voice['voiceId']}/preview.wav",
    }


def get_voice_file(voice_id: str, filename: str) -> Path:
    normalized = normalize_voice_id(voice_id)
    if filename not in {"preview.wav", "reference.wav"}:
        raise HTTPException(status_code=404, detail="音色文件不存在")
    builtin = get_builtin_voice(normalized)
    if filename == "reference.wav" and builtin:
        raise HTTPException(status_code=404, detail="音色文件不存在")
    path = (
        VOICES_ROOT / "_builtin_previews" / normalized / "preview.wav"
        if builtin
        else voice_dir(normalized) / filename
    )
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="音色文件不存在")
    return path
