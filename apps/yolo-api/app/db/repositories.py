from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Select, func, select

from app.db.database import session_scope
from app.db.models import DigitalHumanJob, DigitalHumanPerson, DigitalHumanSetting


def _json_dumps(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return json.dumps(str(value), ensure_ascii=False)


def upsert_digital_human_person(payload: dict[str, Any]) -> dict[str, Any]:
    engine = str(payload.get("engine") or "chanjing")
    person_id = str(payload.get("person_id") or "")
    with session_scope() as session:
        entity = session.scalar(
            select(DigitalHumanPerson).where(
                DigitalHumanPerson.engine == engine,
                DigitalHumanPerson.person_id == person_id,
            )
        )
        if entity is None:
            entity = DigitalHumanPerson(engine=engine, person_id=person_id)
            session.add(entity)
        entity.name = str(payload.get("name") or "")
        entity.status = str(payload.get("status") or "training")
        entity.audio_man_id = str(payload.get("audio_man_id") or "")
        entity.pic_url = str(payload.get("pic_url") or "")
        entity.preview_url = str(payload.get("preview_url") or "")
        entity.width = int(payload.get("width") or 0)
        entity.height = int(payload.get("height") or 0)
        entity.support_4k = bool(payload.get("support_4k", False))
        entity.train_type = str(payload.get("train_type") or "both")
        entity.source = str(payload.get("source") or "api")
        entity.raw_response_json = _json_dumps(payload.get("raw_response_json") or {})
        session.flush()
        return {
            "id": entity.id,
            "engine": entity.engine,
            "person_id": entity.person_id,
            "name": entity.name,
            "status": entity.status,
            "audio_man_id": entity.audio_man_id,
            "pic_url": entity.pic_url,
            "preview_url": entity.preview_url,
            "width": entity.width,
            "height": entity.height,
            "support_4k": entity.support_4k,
            "train_type": entity.train_type,
            "source": entity.source,
        }


def list_digital_human_persons(*, engine: str = "chanjing", page: int = 1, page_size: int = 20) -> dict[str, Any]:
    offset = max(page - 1, 0) * max(page_size, 1)
    with session_scope() as session:
        total = session.scalar(select(func.count()).select_from(DigitalHumanPerson).where(DigitalHumanPerson.engine == engine)) or 0
        stmt: Select[tuple[DigitalHumanPerson]] = (
            select(DigitalHumanPerson)
            .where(DigitalHumanPerson.engine == engine)
            .order_by(DigitalHumanPerson.updated_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = session.scalars(stmt).all()
        return {
            "page": page,
            "page_size": page_size,
            "total": int(total),
            "items": [
                {
                    "engine": item.engine,
                    "person_id": item.person_id,
                    "name": item.name,
                    "status": item.status,
                    "audio_man_id": item.audio_man_id,
                    "pic_url": item.pic_url,
                    "preview_url": item.preview_url,
                    "width": item.width,
                    "height": item.height,
                    "support_4k": item.support_4k,
                    "train_type": item.train_type,
                    "source": item.source,
                    "created_at": item.created_at.isoformat(),
                    "updated_at": item.updated_at.isoformat(),
                }
                for item in items
            ],
        }


def upsert_digital_human_job(payload: dict[str, Any]) -> dict[str, Any]:
    job_id = str(payload.get("job_id") or "")
    with session_scope() as session:
        entity = session.scalar(select(DigitalHumanJob).where(DigitalHumanJob.job_id == job_id))
        if entity is None:
            entity = DigitalHumanJob(job_id=job_id)
            session.add(entity)
        entity.engine = str(payload.get("engine") or "chanjing")
        entity.job_type = str(payload.get("job_type") or "training")
        entity.status = str(payload.get("status") or "created")
        entity.person_id = str(payload.get("person_id") or "")
        entity.person_name = str(payload.get("person_name") or "")
        entity.audio_man_id = str(payload.get("audio_man_id") or "")
        entity.local_video_path = str(payload.get("local_video_path") or "")
        entity.wav_url = str(payload.get("wav_url") or "")
        entity.text = str(payload.get("text") or "")
        entity.chanjing_file_id = str(payload.get("chanjing_file_id") or "")
        entity.chanjing_video_id = str(payload.get("chanjing_video_id") or "")
        entity.video_url = str(payload.get("video_url") or "")
        entity.local_output_path = str(payload.get("local_output_path") or "")
        entity.trace_id = str(payload.get("trace_id") or "")
        entity.error_message = str(payload.get("error_message") or "")
        entity.raw_job_json_path = str(payload.get("raw_job_json_path") or "")
        session.flush()
        return {
            "id": entity.id,
            "job_id": entity.job_id,
            "job_type": entity.job_type,
            "status": entity.status,
            "person_id": entity.person_id,
            "created_at": entity.created_at.isoformat(),
            "updated_at": entity.updated_at.isoformat(),
        }


def get_digital_human_job(job_id: str) -> dict[str, Any] | None:
    with session_scope() as session:
        entity = session.scalar(select(DigitalHumanJob).where(DigitalHumanJob.job_id == job_id))
        if entity is None:
            return None
        return {
            "job_id": entity.job_id,
            "engine": entity.engine,
            "job_type": entity.job_type,
            "status": entity.status,
            "person_id": entity.person_id,
            "person_name": entity.person_name,
            "audio_man_id": entity.audio_man_id,
            "local_video_path": entity.local_video_path,
            "wav_url": entity.wav_url,
            "text": entity.text,
            "chanjing_file_id": entity.chanjing_file_id,
            "chanjing_video_id": entity.chanjing_video_id,
            "video_url": entity.video_url,
            "local_output_path": entity.local_output_path,
            "trace_id": entity.trace_id,
            "error_message": entity.error_message,
            "raw_job_json_path": entity.raw_job_json_path,
            "created_at": entity.created_at.isoformat(),
            "updated_at": entity.updated_at.isoformat(),
        }


def list_digital_human_jobs(
    *,
    engine: str = "chanjing",
    job_type: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    offset = max(page - 1, 0) * max(page_size, 1)
    with session_scope() as session:
        conditions = [DigitalHumanJob.engine == engine]
        if job_type:
            conditions.append(DigitalHumanJob.job_type == job_type)
        if status:
            conditions.append(DigitalHumanJob.status == status)
        total = session.scalar(select(func.count()).select_from(DigitalHumanJob).where(*conditions)) or 0
        stmt: Select[tuple[DigitalHumanJob]] = (
            select(DigitalHumanJob)
            .where(*conditions)
            .order_by(DigitalHumanJob.updated_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = session.scalars(stmt).all()
        return {
            "page": page,
            "page_size": page_size,
            "total": int(total),
            "items": [
                {
                    "job_id": item.job_id,
                    "engine": item.engine,
                    "job_type": item.job_type,
                    "status": item.status,
                    "person_id": item.person_id,
                    "person_name": item.person_name,
                    "audio_man_id": item.audio_man_id,
                    "local_video_path": item.local_video_path,
                    "wav_url": item.wav_url,
                    "text": item.text,
                    "chanjing_file_id": item.chanjing_file_id,
                    "chanjing_video_id": item.chanjing_video_id,
                    "video_url": item.video_url,
                    "local_output_path": item.local_output_path,
                    "trace_id": item.trace_id,
                    "error_message": item.error_message,
                    "raw_job_json_path": item.raw_job_json_path,
                    "created_at": item.created_at.isoformat(),
                    "updated_at": item.updated_at.isoformat(),
                }
                for item in items
            ],
        }


def upsert_digital_human_setting(key: str, value: str) -> None:
    with session_scope() as session:
        entity = session.scalar(select(DigitalHumanSetting).where(DigitalHumanSetting.key == key))
        if entity is None:
            entity = DigitalHumanSetting(key=key)
            session.add(entity)
        entity.value = value


def seed_default_digital_human_settings(defaults: dict[str, str]) -> None:
    for key, value in defaults.items():
        upsert_digital_human_setting(key, value)
