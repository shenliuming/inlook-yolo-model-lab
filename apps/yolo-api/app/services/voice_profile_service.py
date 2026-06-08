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

from app.common import error_code
from app.common.exceptions import AppException
from app.config.paths import BACKEND_DIR, CONTENT_LAB_VOICES_RUNTIME_DIR
from app.services.material_service import get_material, get_material_file
from app.services.tts_engines.cosyvoice_engine import cosyvoice_engine
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
REFERENCE_SAMPLE_RATE = 24000
LOW_MEAN_VOLUME_DB = -45.0
LOW_MAX_VOLUME_DB = -35.0
CLEAN_REFERENCE_VERSION = "clean_segment_v1"
MIN_PROMPT_UNITS = 28
MIN_PROMPT_UNITS_PER_SECOND = 3.5
MAX_PROMPT_UNITS_PER_SECOND = 12.0

BUILTIN_VOICES = [
    {
        "voiceId": "cosy_male_01",
        "name": "磁性男声",
        "type": "builtin",
        "engine": "cosyvoice",
        "referenceAudioPath": "builtin/cosy_male_01/reference.wav",
        "promptText": "这是一段用于创建磁性男声音色的参考文本。",
        "sampleRate": REFERENCE_SAMPLE_RATE,
        "status": "ready",
    },
    {
        "voiceId": "cosy_female_01",
        "name": "温柔女声",
        "type": "builtin",
        "engine": "cosyvoice",
        "referenceAudioPath": "builtin/cosy_female_01/reference.wav",
        "promptText": "这是一段用于创建温柔女声音色的参考文本。",
        "sampleRate": REFERENCE_SAMPLE_RATE,
        "status": "ready",
    },
    {
        "voiceId": "cosy_teacher_01",
        "name": "知识老师",
        "type": "builtin",
        "engine": "cosyvoice",
        "referenceAudioPath": "builtin/cosy_teacher_01/reference.wav",
        "promptText": "这是一段用于创建知识讲解音色的参考文本。",
        "sampleRate": REFERENCE_SAMPLE_RATE,
        "status": "ready",
    },
    {
        "voiceId": "cosy_natural_01",
        "name": "普通人口播",
        "type": "builtin",
        "engine": "cosyvoice",
        "referenceAudioPath": "builtin/cosy_natural_01/reference.wav",
        "promptText": "这是一段用于创建普通人口播音色的参考文本。",
        "sampleRate": REFERENCE_SAMPLE_RATE,
        "status": "ready",
    },
]

VOICE_ALIASES = {
    "磁性男声": "cosy_male_01",
    "温柔女声": "cosy_female_01",
    "知识老师": "cosy_teacher_01",
    "普通人口播": "cosy_natural_01",
    "male_magnetic": "cosy_male_01",
    "female_warm": "cosy_female_01",
    "teacher_knowledge": "cosy_teacher_01",
    "normal_speaker": "cosy_natural_01",
    "preset-junhao": "cosy_male_01",
    "preset-ava": "cosy_female_01",
    "preset-teacher": "cosy_teacher_01",
    "preset-normal": "cosy_natural_01",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_voice_id() -> str:
    return f"voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"


def voice_dir(voice_id: str) -> Path:
    return VOICES_ROOT / voice_id


def voice_json_path(voice_id: str) -> Path:
    return voice_dir(voice_id) / "voice.json"


def builtin_voice_dir(voice_id: str) -> Path:
    return VOICES_ROOT / "builtin" / voice_id


def builtin_reference_path(voice: dict[str, Any]) -> Path:
    relative_path = str(voice.get("referenceAudioPath") or "").strip()
    if relative_path:
        return VOICES_ROOT / relative_path
    return builtin_voice_dir(str(voice.get("voiceId") or "")) / "reference.wav"


def voice_index_path() -> Path:
    return VOICE_INDEX_PATH


def _relative_runtime_path(path: Path) -> str:
    try:
        return str(path.relative_to(BACKEND_DIR))
    except ValueError:
        return str(path)


def _resolve_runtime_path(path_text: str) -> Path:
    path = Path(str(path_text or "").strip()).expanduser()
    if not path.is_absolute():
        path = BACKEND_DIR / path
    return path


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
        "engine": profile.get("engine", "cosyvoice"),
        "source": source,
        "materialId": profile.get("materialId"),
        "materialKey": profile.get("materialKey"),
        "referenceAudioPath": profile.get("referenceAudioPath"),
        "promptText": profile.get("promptText", ""),
        "status": profile.get("status", "ready"),
        "errorType": profile.get("errorType", ""),
        "errorReason": profile.get("errorReason", ""),
        "validation": profile.get("validation") or {},
        "createdAt": profile.get("createdAt"),
        "updatedAt": profile.get("updatedAt"),
        "lastUsedAt": profile.get("lastUsedAt"),
    }


def upsert_voice_index(profile: dict[str, Any]) -> None:
    entry = voice_index_entry(profile)
    voice_id = str(entry.get("voiceId") or "")
    if not voice_id:
        return
    existing = [item for item in read_voice_index() if item.get("voiceId") != voice_id]
    existing.append(entry)
    write_voice_index(existing)


def remove_voice_index_entry(voice_id: str) -> None:
    normalized = normalize_voice_id(voice_id)
    write_voice_index([item for item in read_voice_index() if item.get("voiceId") != normalized])


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
                profile = persist_voice_profile_validation(read_json(path))
                upsert_voice_index(profile)
                if profile.get("status") != "ready":
                    continue
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
            profile = persist_voice_profile_validation(profile)
            if profile.get("status") != "ready":
                upsert_voice_index(profile)
                continue
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
        "format=duration,size,format_name:stream=codec_name,sample_fmt,sample_rate,channels,duration",
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
        "codec": str(stream.get("codec_name") or ""),
        "sampleFormat": str(stream.get("sample_fmt") or ""),
        "format": str(format_payload.get("format_name") or ""),
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


def infer_prompt_text(reference_path: Path) -> str:
    try:
        return cosyvoice_engine.infer_prompt_text(reference_path).strip()
    except Exception:
        logger.warning("voice prompt text infer failed: %s", reference_path, exc_info=True)
        return ""


def ensure_profile_prompt_text(profile: dict[str, Any], reference_path: Path) -> str:
    prompt_text = str(profile.get("promptText") or "").strip()
    if prompt_text:
        return prompt_text
    prompt_text = infer_prompt_text(reference_path)
    if prompt_text:
        profile["promptText"] = prompt_text
        profile["engine"] = "cosyvoice"
        profile["updatedAt"] = now()
        voice_id = str(profile.get("voiceId") or "")
        if voice_id:
            write_json(voice_json_path(voice_id), profile)
            upsert_voice_index(profile)
    return prompt_text


def _prompt_units(prompt_text: str) -> int:
    clean_text = re.sub(r"[\s，。！？、；：,.!?;:'\"“”‘’（）()【】\[\]《》<>—…·-]+", "", prompt_text or "")
    return len(clean_text)


def _voice_validation_result(
    *,
    ok: bool,
    error_type: str = "",
    reason: str = "",
    reference_path: Path | None = None,
    metadata: dict[str, Any] | None = None,
    prompt_units: int = 0,
    min_prompt_units: int = 0,
    max_prompt_units: int = 0,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "errorType": error_type,
        "reason": reason,
        "referenceAudioPath": str(reference_path) if reference_path else "",
        "metadata": metadata or {},
        "promptUnits": prompt_units,
        "minPromptUnits": min_prompt_units,
        "maxPromptUnits": max_prompt_units,
    }


def _profile_reference_path(profile: dict[str, Any]) -> Path:
    reference_text = str(profile.get("referenceAudioPath") or "").strip()
    if reference_text:
        return _resolve_runtime_path(reference_text)
    return voice_dir(str(profile.get("voiceId") or "")) / "reference.wav"


def validate_voice_profile(profile: dict[str, Any]) -> dict[str, Any]:
    reference_path = _profile_reference_path(profile)
    if not reference_path.exists() or not reference_path.is_file():
        return _voice_validation_result(
            ok=False,
            error_type="reference_audio_missing",
            reason="reference_audio_missing",
            reference_path=reference_path,
        )

    try:
        metadata = _probe_audio(reference_path)
    except AppException as exc:
        error_data = exc.data if isinstance(exc.data, dict) else {}
        return _voice_validation_result(
            ok=False,
            error_type="voice_profile_invalid",
            reason=str(error_data.get("errorType") or "reference_audio_probe_failed"),
            reference_path=reference_path,
        )

    duration = float(metadata.get("duration") or 0.0)
    sample_rate = int(metadata.get("sampleRate") or 0)
    channels = int(metadata.get("channels") or 0)
    codec = str(metadata.get("codec") or "")
    if duration <= 0:
        return _voice_validation_result(
            ok=False,
            error_type="voice_profile_invalid",
            reason="reference_audio_empty",
            reference_path=reference_path,
            metadata=metadata,
        )
    if duration < MIN_REFERENCE_SECONDS:
        return _voice_validation_result(
            ok=False,
            error_type="voice_profile_invalid",
            reason="reference_audio_too_short",
            reference_path=reference_path,
            metadata=metadata,
        )
    if sample_rate != REFERENCE_SAMPLE_RATE or channels != 1 or codec != "pcm_s16le":
        return _voice_validation_result(
            ok=False,
            error_type="voice_profile_invalid",
            reason="reference_audio_format_invalid",
            reference_path=reference_path,
            metadata=metadata,
        )

    prompt_text = str(profile.get("promptText") or "").strip()
    prompt_units = _prompt_units(prompt_text)
    min_prompt_units = max(MIN_PROMPT_UNITS, int(duration * MIN_PROMPT_UNITS_PER_SECOND))
    max_prompt_units = max(min_prompt_units + 1, int(duration * MAX_PROMPT_UNITS_PER_SECOND))
    if not prompt_text:
        return _voice_validation_result(
            ok=False,
            error_type="prompt_text_mismatch",
            reason="prompt_text_missing",
            reference_path=reference_path,
            metadata=metadata,
            prompt_units=prompt_units,
            min_prompt_units=min_prompt_units,
            max_prompt_units=max_prompt_units,
        )
    if prompt_units < min_prompt_units:
        return _voice_validation_result(
            ok=False,
            error_type="prompt_text_mismatch",
            reason="prompt_text_too_short_for_reference",
            reference_path=reference_path,
            metadata=metadata,
            prompt_units=prompt_units,
            min_prompt_units=min_prompt_units,
            max_prompt_units=max_prompt_units,
        )
    if prompt_units > max_prompt_units:
        return _voice_validation_result(
            ok=False,
            error_type="prompt_text_mismatch",
            reason="prompt_text_too_long_for_reference",
            reference_path=reference_path,
            metadata=metadata,
            prompt_units=prompt_units,
            min_prompt_units=min_prompt_units,
            max_prompt_units=max_prompt_units,
        )

    return _voice_validation_result(
        ok=True,
        reference_path=reference_path,
        metadata=metadata,
        prompt_units=prompt_units,
        min_prompt_units=min_prompt_units,
        max_prompt_units=max_prompt_units,
    )


def apply_voice_profile_validation(profile: dict[str, Any]) -> dict[str, Any]:
    next_profile = dict(profile)
    validation = validate_voice_profile(next_profile)
    metadata = validation.get("metadata") or {}
    next_profile["validation"] = validation
    next_profile["errorType"] = "" if validation["ok"] else validation["errorType"]
    next_profile["errorReason"] = "" if validation["ok"] else validation["reason"]
    next_profile["status"] = "ready" if validation["ok"] else "invalid"
    if metadata:
        next_profile["duration"] = metadata.get("duration")
        next_profile["sampleRate"] = metadata.get("sampleRate")
        next_profile["channels"] = metadata.get("channels")
        next_profile["codec"] = metadata.get("codec")
    return next_profile


def persist_voice_profile_validation(profile: dict[str, Any]) -> dict[str, Any]:
    validated = apply_voice_profile_validation(profile)
    voice_id = str(validated.get("voiceId") or "")
    if voice_id and validated != profile:
        validated["updatedAt"] = now()
        write_json(voice_json_path(voice_id), validated)
    return validated


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
        prompt_text = infer_prompt_text(reference_path)
        if original_metadata.get("duration", 0.0) > MAX_REFERENCE_SECONDS:
            quality["warnings"].append("原始音频超过 5 分钟，已截取前 5 分钟用于创建音色。")

        created_at = now()
        profile = {
            "voiceId": voice_id,
            "name": clean_name,
            "type": "custom",
            "engine": "cosyvoice",
            "status": "ready",
            "source": "upload",
            "referenceAudioPath": _relative_runtime_path(reference_path),
            "promptText": prompt_text,
            "previewAudioPath": _relative_runtime_path(preview_path),
            "duration": metadata["duration"],
            "sampleRate": metadata["sampleRate"],
            "channels": metadata["channels"],
            "quality": quality,
            "createdAt": created_at,
            "updatedAt": created_at,
            "lastUsedAt": None,
        }
        profile = apply_voice_profile_validation(profile)
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
        prompt_text = infer_prompt_text(working_reference_path)
        quality["warnings"].append("已从当前视频自动截取一段人声作为参考音频，请先试听确认是否干净。")
        if working_reference_path != reference_path:
            shutil.copyfile(working_reference_path, reference_path)

        created_at = now()
        profile = {
            "voiceId": voice_id,
            "name": clean_name,
            "type": "custom",
            "engine": "cosyvoice",
            "status": "ready",
            "source": "current_video",
            "materialId": material_id,
            "materialKey": material_key,
            "referenceAudioPath": _relative_runtime_path(reference_path),
            "promptText": prompt_text,
            "previewAudioPath": _relative_runtime_path(preview_path),
            "duration": metadata["duration"],
            "sampleRate": metadata["sampleRate"],
            "channels": metadata["channels"],
            "quality": quality,
            "referenceExtraction": reference_extraction,
            "createdAt": created_at,
            "updatedAt": created_at,
            "lastUsedAt": existing.get("lastUsedAt") if existing else None,
        }
        if existing:
            profile["createdAt"] = existing.get("createdAt") or created_at
        profile = apply_voice_profile_validation(profile)
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
        "engine": profile.get("engine", "cosyvoice"),
        "source": normalize_voice_source(profile),
        "materialId": profile.get("materialId"),
        "materialKey": profile.get("materialKey"),
        "status": profile.get("status", "ready"),
        "errorType": profile.get("errorType", ""),
        "errorReason": profile.get("errorReason", ""),
        "previewUrl": f"/api/v1/voices/{voice_id}/preview",
        "referenceAudioUrl": f"/api/v1/voices/{voice_id}/reference.wav" if voice_type == "custom" else "",
        "promptTextConfigured": bool(str(profile.get("promptText") or "").strip()),
        "duration": profile.get("duration"),
        "sampleRate": profile.get("sampleRate"),
        "channels": profile.get("channels"),
        "codec": profile.get("codec"),
        "validation": profile.get("validation") or {},
        "quality": profile.get("quality") or {"ok": True, "warnings": []},
        "referenceExtraction": profile.get("referenceExtraction") or {},
        "createdAt": profile.get("createdAt"),
        "updatedAt": profile.get("updatedAt"),
        "lastUsedAt": profile.get("lastUsedAt"),
    }
    if reused is not None:
        payload["reused"] = reused
    return payload


def builtin_voice_to_vo(voice: dict[str, Any]) -> dict[str, Any]:
    voice_id = str(voice.get("voiceId") or "")
    reference_path = builtin_reference_path(voice)
    prompt_text = str(voice.get("promptText") or "").strip()
    return {
        "voiceId": voice_id,
        "name": voice.get("name"),
        "type": "builtin",
        "engine": "cosyvoice",
        "source": "builtin",
        "materialId": None,
        "materialKey": None,
        "status": "ready" if reference_path.exists() and prompt_text else "not_configured",
        "errorType": "" if reference_path.exists() and prompt_text else "cosyvoice_builtin_voice_not_configured",
        "errorReason": "" if reference_path.exists() and prompt_text else "builtin_reference_or_prompt_missing",
        "previewUrl": f"/api/v1/voices/{voice_id}/preview",
        "referenceAudioUrl": f"/api/v1/voices/{voice_id}/reference.wav" if reference_path.exists() else "",
        "promptTextConfigured": bool(prompt_text),
        "duration": None,
        "sampleRate": voice.get("sampleRate"),
        "channels": None,
        "codec": None,
        "validation": {},
        "quality": {"ok": True, "warnings": []},
        "referenceExtraction": {},
        "createdAt": voice.get("createdAt"),
        "updatedAt": voice.get("updatedAt"),
        "lastUsedAt": voice.get("lastUsedAt"),
    }


def list_voice_profiles() -> dict[str, list[dict[str, Any]]]:
    voices_by_id: dict[str, dict[str, Any]] = {}
    for path in sorted(VOICES_ROOT.glob("voice_*/voice.json")):
        try:
            profile = persist_voice_profile_validation(read_json(path))
            payload = voice_profile_to_vo(profile)
            voice_id = str(payload.get("voiceId") or "")
            if voice_id:
                voices_by_id[voice_id] = payload
            upsert_voice_index(profile)
        except Exception:
            logger.warning("skip invalid voice profile: %s", path, exc_info=True)
    return {"voices": list(voices_by_id.values())}


def get_voice_profile(voice_id: str) -> dict[str, Any]:
    normalized = normalize_voice_id(voice_id)
    builtin = get_builtin_voice(normalized)
    if builtin:
        return builtin_voice_to_vo(builtin)
    return voice_profile_to_vo(persist_voice_profile_validation(read_voice_profile(normalized)))


def update_voice_profile(*, voice_id: str, name: str) -> dict[str, Any]:
    normalized = normalize_voice_id(voice_id)
    if get_builtin_voice(normalized):
        raise AppException(
            error_code.BAD_REQUEST,
            "内置音色不可修改。",
            data={"errorType": "builtin_voice_readonly", "voiceId": normalized},
            status_code=400,
        )
    clean_name = str(name or "").strip()
    if not clean_name:
        raise AppException(
            error_code.BAD_REQUEST,
            "音色名称不能为空。",
            data={"errorType": "voice_name_required", "voiceId": normalized},
            status_code=400,
        )
    profile = read_voice_profile(normalized)
    profile["name"] = clean_name
    profile["updatedAt"] = now()
    write_json(voice_json_path(normalized), profile)
    upsert_voice_index(profile)
    return voice_profile_to_vo(profile)


def delete_voice_profile(voice_id: str) -> dict[str, Any]:
    normalized = normalize_voice_id(voice_id)
    if get_builtin_voice(normalized):
        raise AppException(
            error_code.BAD_REQUEST,
            "内置音色不可删除。",
            data={"errorType": "builtin_voice_readonly", "voiceId": normalized},
            status_code=400,
        )
    path = voice_json_path(normalized)
    if not path.exists():
        raise AppException(
            error_code.NOT_FOUND,
            "音色不存在。",
            data={"errorType": "voice_not_found", "voiceId": normalized},
            status_code=404,
        )
    shutil.rmtree(voice_dir(normalized), ignore_errors=True)
    remove_voice_index_entry(normalized)
    return {"voiceId": normalized, "deleted": True}


def raise_invalid_voice_profile(profile: dict[str, Any], validation: dict[str, Any]) -> None:
    voice_id = str(profile.get("voiceId") or "")
    error_type = str(validation.get("errorType") or "voice_profile_invalid")
    reason = str(validation.get("reason") or error_type)
    message = "当前音色配置无效，请重新创建音色。"
    status_code = 400
    code = error_code.BAD_REQUEST
    if error_type == "reference_audio_missing":
        message = "当前音色缺少参考音频，请重新创建音色。"
        status_code = 500
        code = error_code.INTERNAL_ERROR
    elif error_type == "prompt_text_mismatch":
        message = "当前音色参考文本与参考音频不匹配，请重新创建音色。"
    raise AppException(
        code,
        message,
        data={
            "errorType": error_type,
            "reason": reason,
            "voiceId": voice_id,
            "status": profile.get("status"),
            "validation": validation,
        },
        status_code=status_code,
    )


def resolve_voice_for_synthesis(voice_id: str | None) -> dict[str, Any]:
    normalized = normalize_voice_id(voice_id)
    builtin = get_builtin_voice(normalized)
    if builtin:
        reference_path = builtin_reference_path(builtin)
        prompt_text = str(builtin.get("promptText") or "").strip()
        if not reference_path.exists() or not prompt_text:
            raise AppException(
                error_code.INTERNAL_ERROR,
                "当前内置音色未配置完成。",
                data={
                    "errorType": "cosyvoice_builtin_voice_not_configured",
                    "voiceId": builtin["voiceId"],
                    "referenceAudioPath": _relative_runtime_path(reference_path),
                    "promptTextConfigured": bool(prompt_text),
                },
                status_code=500,
            )
        return {
            "voiceId": builtin["voiceId"],
            "name": builtin["name"],
            "type": "builtin",
            "engine": "cosyvoice",
            "promptAudioPath": str(reference_path),
            "promptText": prompt_text,
            "voiceMode": "clone",
        }
    profile = persist_voice_profile_validation(read_voice_profile(normalized))
    validation = profile.get("validation") or validate_voice_profile(profile)
    if profile.get("status") != "ready" or not validation.get("ok"):
        raise_invalid_voice_profile(profile, validation)
    reference_path = _profile_reference_path(profile)
    prompt_text = str(profile.get("promptText") or "").strip()
    return {
        "voiceId": normalized,
        "name": profile.get("name"),
        "type": "custom",
        "engine": "cosyvoice",
        "promptAudioPath": str(reference_path),
        "promptText": prompt_text,
        "voiceMode": "clone",
    }


def create_voice_preview(*, voice_id: str, text: str) -> dict[str, Any]:
    voice = resolve_voice_for_synthesis(voice_id)
    clean_text = (text or "").strip() or "你好，这是当前音色的一段试听。"
    if len(clean_text) > 160:
        clean_text = clean_text[:160]

    root = voice_dir(voice["voiceId"]) if voice["type"] == "custom" else builtin_voice_dir(voice["voiceId"])
    root.mkdir(parents=True, exist_ok=True)
    output_path = root / "preview.wav"
    health = cosyvoice_engine.health()
    if not health.get("available"):
        raise AppException(
            error_code.INTERNAL_ERROR,
            "CosyVoice 未就绪，请先完成模型配置。",
            data={
                "errorType": "cosyvoice_not_ready",
                "reason": health.get("errorType") or "cosyvoice_not_ready",
                "modelDir": health.get("modelDir"),
            },
            status_code=500,
        )

    try:
        cosyvoice_engine.synthesize(
            text=clean_text,
            output_path=str(output_path),
            reference_audio_path=voice["promptAudioPath"],
            prompt_text=voice["promptText"],
        )
    except AppException:
        raise
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
    if builtin and filename == "reference.wav":
        path = builtin_reference_path(builtin)
    elif builtin:
        path = builtin_voice_dir(normalized) / "preview.wav"
    else:
        path = voice_dir(normalized) / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="音色文件不存在")
    return path
