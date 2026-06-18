from __future__ import annotations

import uuid
from typing import Any
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse

from app.clients.chanjing_client import ChanjingApiError
from app.db.repositories import get_digital_human_job
from app.dto.digital_human_dto import ChanjingFullPocRequestDTO, ChanjingTrainingPocRequestDTO, ChanjingVideoPocRequestDTO
from app.services.digital_human_poc_service import (
    create_chanjing_training_upload_job,
    create_chanjing_full_poc_job,
    create_chanjing_training_poc_job,
    create_chanjing_video_poc_job,
    get_chanjing_config_status,
    get_chanjing_full_poc_job,
    get_chanjing_training_job_detail,
    get_chanjing_video_job_detail,
    list_chanjing_common_audios,
    list_chanjing_common_persons,
    list_chanjing_job_records,
    list_chanjing_persons,
    poll_chanjing_full_poc_job,
)

router = APIRouter(prefix="/api/v1/studio/digital-human/chanjing", tags=["digital-human-chanjing"])


def _response(
    *,
    success: bool,
    data: Any = None,
    message: str = "",
    request_id: str | None = None,
    trace_id: str = "",
    status_code: int = 200,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": success,
            "data": data,
            "message": message,
            "request_id": request_id or uuid.uuid4().hex,
            "trace_id": trace_id,
        },
    )


def _wrap(callback: Any) -> JSONResponse:
    request_id = uuid.uuid4().hex
    try:
        data = callback()
        trace_id = ""
        success = True
        message = ""
        if isinstance(data, dict):
            trace_id = str(data.get("trace_id") or data.get("traceId") or "")
            status = str(data.get("status") or "")
            error = data.get("error") if isinstance(data.get("error"), dict) else None
            if status in {"training_failed", "failed", "failed_param", "failed_server"} or error:
                success = False
                message = str((error or {}).get("message") or status or "request failed")
        return _response(success=success, data=data, message=message, request_id=request_id, trace_id=trace_id, status_code=200)
    except FileNotFoundError as exc:
        return _response(success=False, data=None, message=str(exc), request_id=request_id, status_code=404)
    except ChanjingApiError as exc:
        status_code = 400 if exc.code else 502
        return _response(success=False, data=exc.response_json or None, message=str(exc), request_id=request_id, trace_id=exc.trace_id, status_code=status_code)
    except Exception as exc:
        return _response(success=False, data=None, message=str(exc), request_id=request_id, status_code=500)


@router.get("/common-persons")
def get_common_persons(page: int = 1, size: int = 20):
    return _wrap(lambda: list_chanjing_common_persons(page=page, size=size))


@router.get("/config/status")
def get_config_status():
    return _wrap(get_chanjing_config_status)


@router.get("/common-audios")
def get_common_audios(page: int = 1, size: int = 20):
    return _wrap(lambda: list_chanjing_common_audios(page=page, size=size))


@router.get("/persons")
def get_persons(source: str = "db", page: int = 1, page_size: int = 20):
    return _wrap(lambda: list_chanjing_persons(source=source, page=page, page_size=page_size))


@router.get("/custom-persons")
def get_custom_persons(source: str = "db", page: int = 1, page_size: int = 20):
    return _wrap(lambda: list_chanjing_persons(source=source, page=page, page_size=page_size))


@router.post("/custom-persons/train")
def create_training_job(request: ChanjingTrainingPocRequestDTO):
    return _wrap(lambda: create_chanjing_training_poc_job(request.model_dump()))


@router.post("/custom-persons/train-upload")
async def create_training_job_by_upload(
    file: UploadFile = File(...),
    name: str = Form(...),
    train_type: str = Form("both"),
    resolution_rate: int = Form(0),
    language: str = Form("cn"),
    error_skip: bool = Form(False),
):
    content = await file.read()
    return _wrap(
        lambda: create_chanjing_training_upload_job(
            filename=file.filename or "template.mp4",
            content=content,
            name=name,
            train_type=train_type,
            resolution_rate=resolution_rate,
            language=language,
            error_skip=error_skip,
        )
    )


@router.get("/custom-persons/train/{job_id}")
def get_training_job(job_id: str, auto_poll: bool = True):
    return _wrap(lambda: get_chanjing_training_job_detail(job_id, auto_poll=auto_poll))


@router.post("/videos")
def create_video_job(request: ChanjingVideoPocRequestDTO):
    return _wrap(lambda: create_chanjing_video_poc_job(request.model_dump()))


@router.get("/videos/{job_id}")
def get_video_job(job_id: str, auto_poll: bool = True):
    return _wrap(lambda: get_chanjing_video_job_detail(job_id, auto_poll=auto_poll))


@router.post("/full-poc/jobs")
def create_full_poc_job(request: ChanjingFullPocRequestDTO):
    return _wrap(lambda: create_chanjing_full_poc_job(request.model_dump()))


@router.get("/full-poc/jobs/{job_id}")
def get_full_poc_job(job_id: str, auto_poll: bool = True):
    if auto_poll:
        return _wrap(lambda: poll_chanjing_full_poc_job(job_id))
    return _wrap(lambda: get_chanjing_full_poc_job(job_id))


@router.get("/jobs")
def get_jobs(job_type: str = "", status: str = "", page: int = 1, page_size: int = 20):
    return _wrap(
        lambda: list_chanjing_job_records(
            job_type=job_type or None,
            status=status or None,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/jobs/{job_id}/output")
def open_job_output(job_id: str):
    row = get_digital_human_job(job_id)
    if not row or not row.get("local_output_path"):
        return _response(success=False, data=None, message="本地输出文件不存在", status_code=404)
    path = str(row.get("local_output_path") or "")
    if not Path(path).exists():
        return _response(success=False, data=None, message="本地输出文件不存在", status_code=404)
    return FileResponse(path)
