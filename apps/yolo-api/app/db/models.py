from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class DigitalHumanPerson(Base):
    __tablename__ = "digital_human_persons"
    __table_args__ = (UniqueConstraint("engine", "person_id", name="uq_digital_human_person_engine_person_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    engine: Mapped[str] = mapped_column(String(32), nullable=False, default="chanjing")
    person_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="training")
    audio_man_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    pic_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    preview_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    width: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    height: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    support_4k: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    train_type: Mapped[str] = mapped_column(String(32), nullable=False, default="both")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="api")
    raw_response_json: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)


class DigitalHumanJob(Base):
    __tablename__ = "digital_human_jobs"
    __table_args__ = (UniqueConstraint("job_id", name="uq_digital_human_jobs_job_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(128), nullable=False)
    engine: Mapped[str] = mapped_column(String(32), nullable=False, default="chanjing")
    job_type: Mapped[str] = mapped_column(String(32), nullable=False, default="training")
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="created")
    person_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    person_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    audio_man_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    local_video_path: Mapped[str] = mapped_column(Text, nullable=False, default="")
    wav_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    chanjing_file_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    chanjing_video_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    video_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    local_output_path: Mapped[str] = mapped_column(Text, nullable=False, default="")
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    raw_job_json_path: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)


class DigitalHumanSetting(Base):
    __tablename__ = "digital_human_settings"
    __table_args__ = (UniqueConstraint("key", name="uq_digital_human_settings_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
