from __future__ import annotations

import json
import shutil
import threading
import uuid
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.clients.ffmpeg_client import ffmpeg_client
from app.common import error_code
from app.common.exceptions import AppException
from app.config.paths import STUDIO_TRANSCRIPTION_RUNTIME_DIR
from app.config.settings import get_asr_provider, get_whisper_vad_filter
from app.services.ocr_subtitle_service import OcrResult, extract_ocr_subtitles
from app.services.subtitle_tool.subtitle_pack import extract_audio, transcribe, write_srt
from app.services.transcription_fusion_service import (
    apply_asr_corrections,
    build_final_text_from_asr_ocr,
    build_hotwords,
    build_initial_prompt,
)
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
        "ocrText": f"/api/v1/files/transcriptions/{task_id}/ocr_text.txt",
        "ocrSubtitles": f"/api/v1/files/transcriptions/{task_id}/ocr_subtitles.json",
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
        "ocr_text.txt": outputs / "ocr_text.txt",
        "ocr_subtitles.json": outputs / "ocr_subtitles.json",
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
        "ocr_text.txt": outputs / "ocr_text.txt",
        "ocr_subtitles.json": outputs / "ocr_subtitles.json",
        "final_transcript.txt": outputs / "final_transcript.txt",
        "transcript.txt": outputs / "transcript.txt",
        "subtitles.srt": outputs / "subtitles.srt",
        "subtitles.vtt": outputs / "subtitles.vtt",
        "transcription_result.json": outputs / "transcription_result.json",
        "metadata.json": outputs / "metadata.json",
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
            raise AppException(
                error_code.INTERNAL_ERROR,
                f"视频文案提取失败：暂不支持该 ASR Provider：{provider}",
                status_code=500,
                data={"errorType": "transcription_failed", "materialId": material_id},
            )

        task.update({"status": "running", "stage": "读取素材元信息", "progress": 10, "message": "正在读取视频信息"})
        write_task(task_id, task)
        source_video, metadata = _validate_local_source_video(material_id)
        try:
            material_payload = read_material(material_id)
        except Exception as exc:
            append_log(material_id, f"[MATERIAL_READ_WARNING] {exc}")
            material_payload = {}
        hotwords = build_hotwords(material_payload)
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
        try:
            extract_audio(source_video, wav_path)
        except SystemExit as exc:
            raise AppException(
                error_code.INTERNAL_ERROR,
                "视频文案提取失败：音频提取失败。",
                status_code=500,
                data={"errorType": "audio_extract_failed", "materialId": material_id},
            ) from exc
        append_log(material_id, f"[ASR_AUDIO] {wav_path}")
        _copy_file(wav_path, outputs / "audio.wav")

        task.update({"stage": "识别语音文本", "progress": 55, "message": "Whisper 正在识别"})
        write_task(task_id, task)
        try:
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
        except SystemExit as exc:
            raise AppException(
                error_code.INTERNAL_ERROR,
                "视频文案提取失败：语音识别失败。",
                status_code=500,
                data={"errorType": "asr_failed", "materialId": material_id},
            ) from exc
        if not raw_segments:
            raise AppException(
                error_code.INTERNAL_ERROR,
                "视频文案提取失败：语音识别失败。",
                status_code=500,
                data={"errorType": "asr_failed", "materialId": material_id},
            )

        segments = [
            {"start": seg.start, "end": seg.end, "text": seg.text}
            for seg in raw_segments
        ]
        asr_text = "\n".join(segment["text"] for segment in segments).strip()
        corrected_asr_text, asr_corrections = apply_asr_corrections(asr_text, hotwords)
        append_log(material_id, f"[ASR_CORRECTIONS] {len(asr_corrections)}")

        task.update({"stage": "识别画面字幕", "progress": 68, "message": "正在识别视频硬字幕"})
        write_task(task_id, task)
        try:
            ocr_result = extract_ocr_subtitles(source_video, material_outputs_dir(material_id))
        except Exception as exc:
            append_log(material_id, f"[OCR_EXCEPTION] {exc}")
            append_log(material_id, traceback.format_exc())
            ocr_result = OcrResult(
                ocrStatus="failed",
                errorMessage=str(exc),
                warnings=["OCR 处理失败，已使用 ASR 结果。"],
            )
        append_log(material_id, f"[OCR_STATUS] {ocr_result.ocrStatus}")
        append_log(material_id, f"[OCR_TEXT_LENGTH] {len(ocr_result.ocrText or '')}")

        fusion_result = build_final_text_from_asr_ocr(
            asr_text=asr_text,
            asr_segments=segments,
            corrected_asr_text=corrected_asr_text,
            ocr_text=ocr_result.ocrText,
            ocr_segments=ocr_result.ocrSegments,
            ocr_status=ocr_result.ocrStatus,
        )
        final_text = fusion_result.finalText or corrected_asr_text or asr_text
        warnings = [*ocr_result.warnings, *fusion_result.warnings]
        corrections_applied: list[dict[str, Any]] = [*asr_corrections, *fusion_result.correctionsApplied]
        append_log(material_id, f"[FUSION_SOURCE] {fusion_result.fusionSource}")
        append_log(material_id, f"[FUSION_CORRECTIONS] {len(corrections_applied)}")
        append_log(material_id, f"[FUSION_WARNINGS] {len(warnings)}")

        task.update({"stage": "生成字幕文件", "progress": 80, "message": "正在写入字幕和 transcript"})
        write_task(task_id, task)

        transcript_json_path = outputs / "transcript.json"
        transcript_txt_path = outputs / "transcript.txt"
        srt_path = outputs / "subtitles.srt"
        vtt_path = outputs / "subtitles.vtt"
        asr_text_path = material_output_files["asr_text.txt"]
        asr_segments_path = material_output_files["asr_segments.json"]
        corrected_asr_text_path = material_output_files["corrected_asr_text.txt"]
        ocr_text_path = material_output_files["ocr_text.txt"]
        ocr_subtitles_path = material_output_files["ocr_subtitles.json"]
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
            "materialKey": material_id,
            "engine": provider,
            "model": model,
            "language": language,
            "asrText": asr_text,
            "correctedAsrText": corrected_asr_text,
            "ocrText": ocr_result.ocrText,
            "finalText": final_text,
            "ocrStatus": ocr_result.ocrStatus,
            "ocrSegments": ocr_result.ocrSegments,
            "ocrFrameCount": ocr_result.frameCount,
            "ocrTextLength": ocr_result.textLength,
            "ocrErrorMessage": ocr_result.errorMessage,
            "fusionSource": fusion_result.fusionSource,
            "fusionStats": fusion_result.fusionStats,
            "warnings": warnings,
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
                "ocrText": ocr_result.ocrText,
                "finalText": final_text,
                "segments": segments,
                "ocrSegments": ocr_result.ocrSegments,
                "ocrStatus": ocr_result.ocrStatus,
                "ocrFrameCount": ocr_result.frameCount,
                "ocrTextLength": ocr_result.textLength,
                "ocrErrorMessage": ocr_result.errorMessage,
                "fusionSource": fusion_result.fusionSource,
                "fusionStats": fusion_result.fusionStats,
                "warnings": warnings,
                "createdAt": now(),
            },
        )
        transcript_txt_path.write_text(final_text + ("\n" if final_text else ""), encoding="utf-8")
        try:
            write_srt(raw_segments, srt_path)
            write_vtt(segments, vtt_path)
        except Exception as exc:
            raise AppException(
                error_code.INTERNAL_ERROR,
                "视频文案提取失败：字幕生成失败。",
                status_code=500,
                data={"errorType": "subtitle_generate_failed", "materialId": material_id},
            ) from exc
        asr_text_path.write_text(asr_text + ("\n" if asr_text else ""), encoding="utf-8")
        corrected_asr_text_path.write_text(corrected_asr_text + ("\n" if corrected_asr_text else ""), encoding="utf-8")
        ocr_text_path.write_text(ocr_result.ocrText + ("\n" if ocr_result.ocrText else ""), encoding="utf-8")
        write_json(ocr_subtitles_path, ocr_result.ocrSegments)
        final_transcript_path.write_text(final_text + ("\n" if final_text else ""), encoding="utf-8")
        write_json(asr_segments_path, asr_segment_payload)
        write_json(transcription_result_path, transcription_result_payload)
        _copy_file(transcript_txt_path, material_output_files["transcript.txt"])
        _copy_file(srt_path, material_output_files["subtitles.srt"])
        _copy_file(vtt_path, material_output_files["subtitles.vtt"])
        _copy_file(asr_text_path, outputs / "asr_text.txt")
        _copy_file(asr_segments_path, outputs / "asr_segments.json")
        _copy_file(corrected_asr_text_path, outputs / "corrected_asr_text.txt")
        _copy_file(ocr_text_path, outputs / "ocr_text.txt")
        _copy_file(ocr_subtitles_path, outputs / "ocr_subtitles.json")
        _copy_file(final_transcript_path, outputs / "final_transcript.txt")
        _copy_file(transcription_result_path, outputs / "transcription_result.json")
        metadata_payload = {
            "taskId": task_id,
            "materialId": material_id,
            "video": metadata,
            "segmentCount": len(segments),
            "ocrStatus": ocr_result.ocrStatus,
            "fusionSource": fusion_result.fusionSource,
            "createdAt": now(),
        }
        write_json(outputs / "metadata.json", metadata_payload)
        write_json(material_output_files["metadata.json"], metadata_payload)

        task.update(
            {
                "status": "success",
                "stage": "完成",
                "progress": 100,
                "message": "文案与字幕提取完成",
                "material_key": material_id,
                "full_text": final_text,
                "transcript": final_text,
                "asr_text": asr_text,
                "corrected_asr_text": corrected_asr_text,
                "ocr_text": ocr_result.ocrText,
                "ocr_status": ocr_result.ocrStatus,
                "ocr_frame_count": ocr_result.frameCount,
                "ocr_text_length": ocr_result.textLength,
                "ocr_error_message": ocr_result.errorMessage,
                "final_text": final_text,
                "segments": segments,
                "engine": provider,
                "model": model,
                "language": language,
                "hotwords": hotwords,
                "corrections_applied": corrections_applied,
                "fusion_source": fusion_result.fusionSource,
                "fusion_stats": fusion_result.fusionStats,
                "warnings": warnings,
                "subtitle_files": _material_subtitle_files(material_id),
                "downloads": build_downloads(task_id),
            }
        )
        write_task(task_id, task)
    except AppException as exc:
        task.update(
            {
                "status": "failed",
                "stage": "失败",
                "message": exc.message,
                "progress": task.get("progress", 0),
            }
        )
        write_task(task_id, task)
    except SystemExit as exc:
        append_log(material_id, f"[TRANSCRIPTION_SYSTEM_EXIT] {exc}")
        task.update(
            {
                "status": "failed",
                "stage": "失败",
                "message": "视频文案提取失败：处理失败。",
                "progress": task.get("progress", 0),
            }
        )
        write_task(task_id, task)
    except Exception as exc:
        append_log(material_id, f"[TRANSCRIPTION_EXCEPTION] {exc}")
        append_log(material_id, traceback.format_exc())
        task.update(
            {
                "status": "failed",
                "stage": "失败",
                "message": "视频文案提取失败：处理失败。",
                "progress": task.get("progress", 0),
            }
        )
        write_task(task_id, task)


def create_transcription_task(
    *,
    material_id: str,
    model: str,
    language: str,
    device: str,
    compute_type: str,
    beam_size: int,
) -> dict[str, Any]:
    _validate_local_source_video(material_id)

    task_id = build_task_id()
    task_inputs_dir(task_id).mkdir(parents=True, exist_ok=True)
    task_outputs_dir(task_id).mkdir(parents=True, exist_ok=True)
    task = {
        "task_id": task_id,
        "task_type": "transcription.extract",
        "material_id": material_id,
        "material_key": material_id,
        "status": "pending",
        "stage": "等待执行",
        "progress": 0,
        "message": "转写任务已创建",
        "downloads": build_downloads(task_id),
        "created_at": now(),
        "updated_at": now(),
    }
    write_task(task_id, task)
    process_transcription_task(
        task_id,
        material_id=material_id,
        model=model,
        language=language,
        device=device,
        compute_type=compute_type,
        beam_size=beam_size,
    )
    result = get_transcription(task_id)
    if result["status"] == "failed":
        message = result.get("message") or "视频文案提取失败：处理失败。"
        error_type = "transcription_failed"
        if "本地视频不存在" in message:
            error_type = "source_mp4_missing"
        elif "本地视频无效" in message:
            error_type = "source_mp4_invalid"
        elif "音频提取失败" in message:
            error_type = "audio_extract_failed"
        elif "语音识别失败" in message:
            error_type = "asr_failed"
        elif "字幕生成失败" in message:
            error_type = "subtitle_generate_failed"
        raise AppException(
            error_code.INTERNAL_ERROR,
            message,
            status_code=500,
            data={"errorType": error_type, "materialId": material_id},
        )
    return result


def get_transcription(task_id: str) -> dict[str, Any]:
    task = read_task(task_id)
    return {
        "transcriptionId": task["task_id"],
        "taskId": task["task_id"],
        "materialId": task.get("material_id"),
        "materialKey": task.get("material_key") or task.get("material_id"),
        "status": task.get("status"),
        "stage": task.get("stage"),
        "progress": task.get("progress"),
        "message": task.get("message"),
        "text": task.get("final_text") or task.get("corrected_asr_text") or task.get("asr_text") or task.get("full_text", ""),
        "transcript": task.get("final_text") or task.get("corrected_asr_text") or task.get("asr_text") or task.get("full_text", ""),
        "asrText": task.get("asr_text", ""),
        "correctedAsrText": task.get("corrected_asr_text", ""),
        "ocrText": task.get("ocr_text", ""),
        "finalText": task.get("final_text", ""),
        "ocrStatus": task.get("ocr_status", ""),
        "ocrFrameCount": task.get("ocr_frame_count", 0),
        "ocrTextLength": task.get("ocr_text_length", 0),
        "ocrErrorMessage": task.get("ocr_error_message"),
        "fusionSource": task.get("fusion_source", ""),
        "fusionStats": task.get("fusion_stats") or {},
        "warnings": task.get("warnings") or [],
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
