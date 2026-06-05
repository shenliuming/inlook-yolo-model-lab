from __future__ import annotations

import json
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.clients.ffmpeg_client import ffmpeg_client
from app.common import error_code
from app.common.exceptions import AppException
from app.config.paths import STUDIO_TRANSCRIPTION_RUNTIME_DIR
from app.config.settings import get_asr_provider, get_whisper_vad_filter
from app.services.material_intake_service import get_material_file, get_material_task
from app.services.subtitle_tool.subtitle_pack import extract_audio, transcribe, write_srt
from app.tasks.task_store import append_log, material_dir, material_inputs_dir, material_outputs_dir, read_material

RUNTIME_ROOT = STUDIO_TRANSCRIPTION_RUNTIME_DIR
RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
_task_lock = threading.Lock()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_task_id() -> str:
    return f"tr_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"


def task_dir(task_id: str) -> Path:
    return RUNTIME_ROOT / task_id


def task_inputs_dir(task_id: str) -> Path:
    return task_dir(task_id) / "inputs"


def task_outputs_dir(task_id: str) -> Path:
    return task_dir(task_id) / "outputs"


def task_json_path(task_id: str) -> Path:
    return task_dir(task_id) / "task.json"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_task(task_id: str, payload: dict[str, Any]) -> None:
    with _task_lock:
        payload["updated_at"] = now()
        write_json(task_json_path(task_id), payload)


def read_task(task_id: str) -> dict[str, Any]:
    path = task_json_path(task_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="转写任务不存在")
    return read_json(path)


def write_vtt(segments: list[dict[str, Any]], path: Path) -> None:
    def to_vtt_time(raw: float) -> str:
        total_ms = int(max(0.0, raw) * 1000)
        hours = total_ms // 3600000
        total_ms -= hours * 3600000
        minutes = total_ms // 60000
        total_ms -= minutes * 60000
        seconds = total_ms // 1000
        ms = total_ms - seconds * 1000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{ms:03d}"

    lines = ["WEBVTT", ""]
    for index, segment in enumerate(segments, 1):
        lines.append(str(index))
        lines.append(f"{to_vtt_time(segment['start'])} --> {to_vtt_time(segment['end'])}")
        lines.append(segment["text"])
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def build_downloads(task_id: str) -> dict[str, str]:
    return {
        "transcript": f"/api/v1/files/transcriptions/{task_id}/transcript.json",
        "text": f"/api/v1/files/transcriptions/{task_id}/transcript.txt",
        "srt": f"/api/v1/files/transcriptions/{task_id}/subtitles.srt",
        "vtt": f"/api/v1/files/transcriptions/{task_id}/subtitles.vtt",
        "audio": f"/api/v1/files/transcriptions/{task_id}/audio.wav",
        "asrText": f"/api/v1/files/transcriptions/{task_id}/asr_text.txt",
        "asrSegments": f"/api/v1/files/transcriptions/{task_id}/asr_segments.json",
        "correctedAsrText": f"/api/v1/files/transcriptions/{task_id}/corrected_asr_text.txt",
        "finalTranscript": f"/api/v1/files/transcriptions/{task_id}/final_transcript.txt",
        "result": f"/api/v1/files/transcriptions/{task_id}/transcription_result.json",
        "metadata": f"/api/v1/files/transcriptions/{task_id}/metadata.json",
    }


def _output_file_map(task_id: str) -> dict[str, Path]:
    outputs = task_outputs_dir(task_id)
    return {
        "transcript.json": outputs / "transcript.json",
        "transcript.txt": outputs / "transcript.txt",
        "subtitles.srt": outputs / "subtitles.srt",
        "subtitles.vtt": outputs / "subtitles.vtt",
        "audio.wav": outputs / "audio.wav",
        "asr_text.txt": outputs / "asr_text.txt",
        "asr_segments.json": outputs / "asr_segments.json",
        "corrected_asr_text.txt": outputs / "corrected_asr_text.txt",
        "final_transcript.txt": outputs / "final_transcript.txt",
        "transcription_result.json": outputs / "transcription_result.json",
        "metadata.json": outputs / "metadata.json",
    }


def get_transcription_file(task_id: str, filename: str) -> Path:
    target = _output_file_map(task_id).get(filename)
    if target is None or not target.exists():
        raise HTTPException(status_code=404, detail="转写文件不存在")
    return target


def _material_output_files(material_id: str) -> dict[str, Path]:
    outputs = material_outputs_dir(material_id)
    return {
        "audio.wav": outputs / "audio.wav",
        "asr_text.txt": outputs / "asr_text.txt",
        "asr_segments.json": outputs / "asr_segments.json",
        "corrected_asr_text.txt": outputs / "corrected_asr_text.txt",
        "final_transcript.txt": outputs / "final_transcript.txt",
        "transcription_result.json": outputs / "transcription_result.json",
    }


def _copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _material_subtitle_files(material_id: str) -> dict[str, str]:
    return {
        "srt": f"/api/v1/materials/{material_id}/files/subtitles.srt",
        "vtt": f"/api/v1/materials/{material_id}/files/subtitles.vtt",
    }


def _validate_local_source_video(material_id: str) -> tuple[Path, dict[str, Any]]:
    material_path = material_dir(material_id) / "material.json"
    if not material_path.exists():
        raise AppException(
            error_code.INTERNAL_ERROR,
            "视频文案提取失败：素材不存在，请先读取素材或上传本地视频。",
            status_code=500,
            data={"errorType": "material_not_found", "materialId": material_id},
        )

    source_path = material_inputs_dir(material_id) / "source.mp4"
    if not source_path.exists():
        raise AppException(
            error_code.INTERNAL_ERROR,
            "视频文案提取失败：本地视频不存在，请先读取素材或上传本地视频。",
            status_code=500,
            data={"errorType": "source_mp4_missing", "materialId": material_id},
        )

    try:
        metadata = ffmpeg_client.probe_video(source_path)
    except AppException as exc:
        raise AppException(
            error_code.INTERNAL_ERROR,
            "视频文案提取失败：本地视频无效，请重新读取素材或上传本地视频。",
            status_code=500,
            data={"errorType": "source_mp4_invalid", "materialId": material_id},
        ) from exc

    if int(metadata.get("width") or 0) <= 0 or int(metadata.get("height") or 0) <= 0 or float(metadata.get("duration") or 0) <= 0:
        raise AppException(
            error_code.INTERNAL_ERROR,
            "视频文案提取失败：本地视频无效，请重新读取素材或上传本地视频。",
            status_code=500,
            data={"errorType": "source_mp4_invalid", "materialId": material_id},
        )
    return source_path, metadata


def process_transcription_task(
    task_id: str,
    *,
    material_id: str,
    model: str,
    language: str,
    device: str,
    compute_type: str,
    beam_size: int,
) -> None:
    task = read_task(task_id)
    try:
        provider = get_asr_provider()
        if provider != "faster_whisper":
            raise RuntimeError(f"暂不支持该 ASR Provider：{provider}")

        task.update({"status": "running", "stage": "读取素材元信息", "progress": 10, "message": "正在读取视频信息"})
        write_task(task_id, task)
        source_video, metadata = resolve_material_video_source(material_id, download_if_needed=True)
        material, extra_keywords = _resolve_material_keywords(material_id)
        hotwords = build_hotwords(material, extra_keywords=extra_keywords)
        initial_prompt = build_initial_prompt(hotwords)
        append_log(material_id, f"[ASR_PROVIDER] {provider}")
        append_log(material_id, f"[WHISPER_MODEL] {model}")
        append_log(material_id, f"[WHISPER_LANGUAGE] {language}")
        append_log(material_id, f"[WHISPER_DEVICE] {device}")
        append_log(material_id, f"[WHISPER_COMPUTE_TYPE] {compute_type}")
        append_log(material_id, f"[WHISPER_VAD_FILTER] {str(get_whisper_vad_filter()).lower()}")
        append_log(material_id, f"[WHISPER_INITIAL_PROMPT] {str(bool(initial_prompt)).lower()}")

        outputs = task_outputs_dir(task_id)
        material_output_files = _material_output_files(material_id)
        wav_path = material_output_files["audio.wav"]
        task.update({"stage": "提取音频", "progress": 25, "message": "正在提取音频"})
        write_task(task_id, task)
        extract_audio(source_video, wav_path)
        append_log(material_id, f"[ASR_AUDIO] {wav_path}")
        _copy_file(wav_path, outputs / "audio.wav")

        task.update({"stage": "识别语音文本", "progress": 55, "message": "Whisper 正在识别"})
        write_task(task_id, task)
        raw_segments = transcribe(
            wav_path,
            model_name=model,
            language=language,
            device=device,
            compute_type=compute_type,
            beam_size=beam_size,
            vad_filter=get_whisper_vad_filter(),
            initial_prompt=initial_prompt,
        )
        if not raw_segments:
            raise RuntimeError("没有识别到有效语音")

        segments = [
            {"start": seg.start, "end": seg.end, "text": seg.text}
            for seg in raw_segments
        ]
        asr_text = "\n".join(segment["text"] for segment in segments).strip()
        corrected_asr_text, corrections_applied = correct_hotwords(asr_text)
        final_text = corrected_asr_text
        append_log(material_id, f"[ASR_CORRECTIONS] {len(corrections_applied)}")

        task.update({"stage": "生成字幕文件", "progress": 80, "message": "正在写入字幕和 transcript"})
        write_task(task_id, task)

        transcript_json_path = outputs / "transcript.json"
        transcript_txt_path = outputs / "transcript.txt"
        srt_path = outputs / "subtitles.srt"
        vtt_path = outputs / "subtitles.vtt"
        asr_text_path = material_output_files["asr_text.txt"]
        asr_segments_path = material_output_files["asr_segments.json"]
        corrected_asr_text_path = material_output_files["corrected_asr_text.txt"]
        final_transcript_path = material_output_files["final_transcript.txt"]
        transcription_result_path = material_output_files["transcription_result.json"]
        asr_segment_payload = {
            "materialId": material_id,
            "engine": provider,
            "model": model,
            "language": language,
            "segments": segments,
            "createdAt": now(),
        }
        transcription_result_payload = {
            "materialId": material_id,
            "engine": provider,
            "model": model,
            "language": language,
            "asrText": asr_text,
            "correctedAsrText": corrected_asr_text,
            "finalText": final_text,
            "hotwords": hotwords,
            "correctionsApplied": corrections_applied,
        }

        write_json(
            transcript_json_path,
            {
                "taskId": task_id,
                "materialId": material_id,
                "text": final_text,
                "transcript": final_text,
                "asrText": asr_text,
                "correctedAsrText": corrected_asr_text,
                "finalText": final_text,
                "segments": segments,
                "createdAt": now(),
            },
        )
        transcript_txt_path.write_text(final_text + ("\n" if final_text else ""), encoding="utf-8")
        write_srt(raw_segments, srt_path)
        write_vtt(segments, vtt_path)
        asr_text_path.write_text(asr_text + ("\n" if asr_text else ""), encoding="utf-8")
        corrected_asr_text_path.write_text(corrected_asr_text + ("\n" if corrected_asr_text else ""), encoding="utf-8")
        final_transcript_path.write_text(final_text + ("\n" if final_text else ""), encoding="utf-8")
        write_json(asr_segments_path, asr_segment_payload)
        write_json(transcription_result_path, transcription_result_payload)
        _copy_file(asr_text_path, outputs / "asr_text.txt")
        _copy_file(asr_segments_path, outputs / "asr_segments.json")
        _copy_file(corrected_asr_text_path, outputs / "corrected_asr_text.txt")
        _copy_file(final_transcript_path, outputs / "final_transcript.txt")
        _copy_file(transcription_result_path, outputs / "transcription_result.json")
        write_json(
            outputs / "metadata.json",
            {
                "taskId": task_id,
                "materialId": material_id,
                "video": metadata,
                "segmentCount": len(segments),
                "createdAt": now(),
            },
        )

        task.update(
            {
                "status": "success",
                "stage": "完成",
                "progress": 100,
                "message": "文案与字幕提取完成",
                "full_text": final_text,
                "transcript": final_text,
                "asr_text": asr_text,
                "corrected_asr_text": corrected_asr_text,
                "final_text": final_text,
                "segments": segments,
                "engine": provider,
                "model": model,
                "language": language,
                "hotwords": hotwords,
                "corrections_applied": corrections_applied,
                "subtitle_files": {
                    "srt": build_downloads(task_id)["srt"],
                    "vtt": build_downloads(task_id)["vtt"],
                },
                "downloads": build_downloads(task_id),
            }
        )
        write_task(task_id, task)
    except SystemExit as exc:
        task.update(
            {
                "status": "failed",
                "stage": "失败",
                "message": str(exc),
                "progress": task.get("progress", 0),
            }
        )
        write_task(task_id, task)
    except Exception as exc:
        task.update(
            {
                "status": "failed",
                "stage": "失败",
                "message": str(exc),
                "progress": task.get("progress", 0),
            }
        )
        write_task(task_id, task)


def _resolve_local_material_video(material_id: str, filename: str) -> Path | None:
    candidates = [
        material_inputs_dir(material_id) / filename,
        material_outputs_dir(material_id) / filename,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    for candidate in material_dir(material_id).rglob(filename):
        if candidate.is_file():
            return candidate
    return None


def _download_remote_material_video(material_id: str, *, source_type: str, video_url: str, referer: str) -> Path:
    local_path = material_inputs_dir(material_id) / "source.mp4"
    browser_client.download_file(source_type, target_url=video_url, output_path=local_path, referer=referer)
    append_log(material_id, f"[TRANSCRIPTION_LOCAL_VIDEO] {local_path}")
    return local_path


def resolve_material_video_source(material_id: str, *, download_if_needed: bool = False) -> tuple[str | Path, dict[str, Any]]:
    material_path = material_dir(material_id) / "material.json"
    if material_path.exists():
        material = read_material(material_id)
        video = material.get("video") if isinstance(material, dict) else {}
        video_url = str((video or {}).get("url") or "").strip()
        source_type = str(material.get("sourceType") or "").strip()
        referer = str(material.get("finalUrl") or material.get("sourceUrl") or "").strip()
        for filename in ("source.mp4", "input.mp4"):
            local_video = _resolve_local_material_video(material_id, filename)
            if local_video is not None:
                metadata = ffprobe_metadata(local_video)
                return local_video, metadata
        if video_url.startswith("/api/v1/materials/"):
            filename = video_url.rstrip("/").split("/")[-1]
            for candidate in material_dir(material_id).rglob(filename):
                if candidate.is_file():
                    return candidate, {
                        "width": int((video or {}).get("width") or 0),
                        "height": int((video or {}).get("height") or 0),
                        "duration": float((video or {}).get("duration") or 0.0),
                    }
        remote_url = str((video or {}).get("remoteUrl") or video_url).strip()
        if remote_url.startswith(("http://", "https://")) and download_if_needed:
            local_video = _download_remote_material_video(
                material_id,
                source_type=source_type,
                video_url=remote_url,
                referer=referer,
            )
            return local_video, ffprobe_metadata(local_video)
        if video_url.startswith(("http://", "https://")):
            return video_url, {
                "width": int((video or {}).get("width") or 0),
                "height": int((video or {}).get("height") or 0),
                "duration": float((video or {}).get("duration") or 0.0),
            }
        raise HTTPException(status_code=400, detail="素材未解析出可用视频源，无法提取文案")

    material_task = get_material_task(material_id)
    if material_task.get("status") != "success":
        raise HTTPException(status_code=400, detail="素材尚未准备完成，无法提取文案")
    source_video = get_material_file(material_id, "input.mp4")
    return source_video, ffprobe_metadata(source_video)


def create_transcription_task(
    *,
    background_tasks: BackgroundTasks,
    material_id: str,
    model: str,
    language: str,
    device: str,
    compute_type: str,
    beam_size: int,
) -> dict[str, Any]:
    resolve_material_video_source(material_id, download_if_needed=False)

    task_id = build_task_id()
    task_inputs_dir(task_id).mkdir(parents=True, exist_ok=True)
    task_outputs_dir(task_id).mkdir(parents=True, exist_ok=True)
    task = {
        "task_id": task_id,
        "task_type": "transcription.extract",
        "material_id": material_id,
        "status": "pending",
        "stage": "等待执行",
        "progress": 0,
        "message": "转写任务已创建",
        "downloads": build_downloads(task_id),
        "created_at": now(),
        "updated_at": now(),
    }
    write_task(task_id, task)
    background_tasks.add_task(
        process_transcription_task,
        task_id,
        material_id=material_id,
        model=model,
        language=language,
        device=device,
        compute_type=compute_type,
        beam_size=beam_size,
    )
    return get_transcription(task_id)


def get_transcription(task_id: str) -> dict[str, Any]:
    task = read_task(task_id)
    return {
        "transcriptionId": task["task_id"],
        "taskId": task["task_id"],
        "materialId": task.get("material_id"),
        "status": task.get("status"),
        "stage": task.get("stage"),
        "progress": task.get("progress"),
        "message": task.get("message"),
        "text": task.get("final_text") or task.get("corrected_asr_text") or task.get("asr_text") or task.get("full_text", ""),
        "transcript": task.get("final_text") or task.get("corrected_asr_text") or task.get("asr_text") or task.get("full_text", ""),
        "asrText": task.get("asr_text", ""),
        "correctedAsrText": task.get("corrected_asr_text", ""),
        "finalText": task.get("final_text", ""),
        "segments": task.get("segments") or [],
        "engine": task.get("engine", ""),
        "model": task.get("model", ""),
        "language": task.get("language", ""),
        "hotwords": task.get("hotwords") or [],
        "correctionsApplied": task.get("corrections_applied") or [],
        "subtitleFiles": task.get("subtitle_files") or {},
        "files": task.get("downloads") or {},
        "createdAt": task.get("created_at"),
        "updatedAt": task.get("updated_at"),
    }


def get_subtitle_bundle(task_id: str) -> dict[str, Any]:
    task = get_transcription(task_id)
    return {
        "subtitleId": task_id,
        "transcriptionId": task_id,
        "status": task["status"],
        "stage": task["stage"],
        "files": task["subtitleFiles"],
        "createdAt": task["createdAt"],
        "updatedAt": task["updatedAt"],
    }
