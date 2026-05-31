#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from scripts.burn_subtitles import burn_ass_video, check_ffmpeg_ass
from scripts.subtitle_pack import (
    burn_video,
    check_ffmpeg,
    extract_audio,
    transcribe,
    write_ass,
    write_srt,
    write_txt,
)


APP_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = APP_ROOT / "web"
JOBS_ROOT = APP_ROOT / "jobs"
JOBS_ROOT.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="INLOOK Local Subtitle Packer", version="0.1.0")
app.mount("/static", StaticFiles(directory=WEB_ROOT), name="static")


def build_job_id() -> str:
    return datetime.now().strftime("job_%Y%m%d_%H%M%S")


def save_upload(upload: UploadFile, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
    return dest


def write_manifest(job_dir: Path, payload: dict[str, Any]) -> None:
    (job_dir / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def read_manifest(job_dir: Path) -> dict[str, Any]:
    manifest_path = job_dir / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="未找到任务记录。")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def build_download_url(job_id: str, filename: str) -> str:
    return f"/api/download/{job_id}/{filename}"


@app.get("/api/health")
def health() -> dict[str, str]:
    subtitle_filter = check_ffmpeg()
    return {
        "status": "ok",
        "subtitle_filter": subtitle_filter,
        "message": "INLOOK local subtitle web is running",
    }


@app.post("/api/subtitle-pack")
def subtitle_pack(
    video: UploadFile = File(...),
    audio: UploadFile | None = File(default=None),
    model: str = Form(default="small"),
    language: str = Form(default="zh"),
    device: str = Form(default="cpu"),
    compute_type: str = Form(default="int8"),
    beam_size: int = Form(default=5),
    width: int = Form(default=1080),
    height: int = Form(default=1920),
    font_size: int = Form(default=62),
    margin_v: int = Form(default=250),
    crf: int = Form(default=20),
    no_audio: bool = Form(default=False),
) -> dict[str, Any]:
    logs: list[str] = []
    subtitle_filter_name = check_ffmpeg()
    logs.append(f"[ffmpeg] subtitle_filter={subtitle_filter_name}")

    job_id = build_job_id()
    job_dir = JOBS_ROOT / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    video_suffix = Path(video.filename or "input.mp4").suffix or ".mp4"
    video_path = job_dir / f"input{video_suffix}"
    save_upload(video, video_path)
    logs.append(f"[input] video={video_path.name}")

    audio_path = None
    if audio and audio.filename:
        audio_suffix = Path(audio.filename).suffix or ".m4a"
        audio_path = job_dir / f"voice{audio_suffix}"
        save_upload(audio, audio_path)
        logs.append(f"[input] audio={audio_path.name}")

    output_path = job_dir / "output_subtitled.mp4"
    srt_path = job_dir / "output_subtitled.srt"
    ass_path = job_dir / "output_subtitled.ass"
    txt_path = job_dir / "output_subtitled.txt"

    try:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory(prefix="inlook_subtitle_web_") as td:
            wav_path = Path(td) / "asr.wav"
            asr_source = audio_path if audio_path else video_path

            logs.append("[step] extracting audio")
            extract_audio(asr_source, wav_path)

            logs.append(f"[step] transcribing with model={model}")
            segments = transcribe(
                wav_path,
                model_name=model,
                language=language,
                device=device,
                compute_type=compute_type,
                beam_size=beam_size,
                vad_filter=True,
            )
            if not segments:
                raise HTTPException(status_code=400, detail="没有识别到有效语音。")

            logs.append(f"[step] writing subtitles ({len(segments)} segments)")
            write_srt(segments, srt_path)
            write_ass(segments, ass_path, width, height, font_size, margin_v)
            write_txt(segments, txt_path)

            logs.append("[step] burning video")
            burn_video(
                video=video_path,
                audio=audio_path,
                ass_file=ass_path,
                output=output_path,
                width=width,
                height=height,
                crf=crf,
                keep_original_audio=not no_audio,
                subtitle_filter_name=subtitle_filter_name,
            )
    except HTTPException:
        raise
    except SystemExit as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"处理失败：{exc}") from exc

    manifest = {
        "job_id": job_id,
        "video_name": video_path.name,
        "audio_name": audio_path.name if audio_path else None,
        "output_name": output_path.name,
        "srt_name": srt_path.name,
        "ass_name": ass_path.name,
        "txt_name": txt_path.name,
        "created_at": datetime.now().isoformat(),
    }
    write_manifest(job_dir, manifest)

    logs.append("[done] subtitle pack completed")
    return {
        "job_id": job_id,
        "logs": logs,
        "downloads": {
            "mp4": build_download_url(job_id, output_path.name),
            "srt": build_download_url(job_id, srt_path.name),
            "ass": build_download_url(job_id, ass_path.name),
            "txt": build_download_url(job_id, txt_path.name),
        },
    }


@app.post("/api/reburn")
def reburn(
    job_id: str = Form(...),
    ass: UploadFile | None = File(default=None),
    crf: int = Form(default=20),
    no_audio: bool = Form(default=False),
) -> dict[str, Any]:
    logs: list[str] = []
    check_ffmpeg_ass()

    job_dir = JOBS_ROOT / job_id
    manifest = read_manifest(job_dir)

    video_path = job_dir / manifest["video_name"]
    ass_path = job_dir / manifest["ass_name"]
    output_path = job_dir / "output_fixed.mp4"

    if ass and ass.filename:
        save_upload(ass, ass_path)
        logs.append(f"[input] updated ass={ass_path.name}")

    try:
        logs.append("[step] reburning edited ASS subtitles")
        burn_ass_video(
            video=video_path,
            ass_file=ass_path,
            output=output_path,
            crf=crf,
            keep_original_audio=not no_audio,
        )
    except SystemExit as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"重新烧录失败：{exc}") from exc

    logs.append("[done] subtitle reburn completed")
    return {
        "job_id": job_id,
        "logs": logs,
        "downloads": {
            "mp4": build_download_url(job_id, output_path.name),
            "ass": build_download_url(job_id, ass_path.name),
        },
    }


@app.get("/api/download/{job_id}/{filename}")
def download(job_id: str, filename: str) -> FileResponse:
    job_dir = JOBS_ROOT / job_id
    file_path = (job_dir / filename).resolve()
    if job_dir.resolve() not in file_path.parents or not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在。")
    return FileResponse(file_path, filename=file_path.name)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_ROOT / "index.html")
