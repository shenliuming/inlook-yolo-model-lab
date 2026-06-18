from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.config.paths import STUDIO_ALPHA_DB_PATH

DB_PATH = Path(STUDIO_ALPHA_DB_PATH)


def init_database() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS digital_human_template (
                template_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                source TEXT NOT NULL,
                provider_code TEXT NOT NULL,
                provider_template_id TEXT NOT NULL DEFAULT '',
                provider_audio_profile_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                training_type TEXT NOT NULL DEFAULT 'full',
                resolution_label TEXT NOT NULL DEFAULT '1080p',
                width INTEGER NOT NULL DEFAULT 0,
                height INTEGER NOT NULL DEFAULT 0,
                cover_url TEXT NOT NULL DEFAULT '',
                preview_url TEXT NOT NULL DEFAULT '',
                local_video_path TEXT NOT NULL DEFAULT '',
                local_template_path TEXT NOT NULL DEFAULT '',
                output_path TEXT NOT NULL DEFAULT '',
                sync_record_id TEXT NOT NULL DEFAULT '',
                error_message TEXT NOT NULL DEFAULT '',
                tags_json TEXT NOT NULL DEFAULT '[]',
                provider_payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_dh_template_provider
            ON digital_human_template(provider_code, provider_template_id);

            CREATE TABLE IF NOT EXISTS digital_human_video_task (
                task_id TEXT PRIMARY KEY,
                template_id TEXT NOT NULL,
                workflow_id TEXT NOT NULL DEFAULT '',
                project_id TEXT NOT NULL DEFAULT '',
                provider_code TEXT NOT NULL,
                provider_task_id TEXT NOT NULL DEFAULT '',
                mode TEXT NOT NULL DEFAULT 'auto',
                status TEXT NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0,
                script TEXT NOT NULL DEFAULT '',
                audio_task_id TEXT NOT NULL DEFAULT '',
                audio_path TEXT NOT NULL DEFAULT '',
                audio_url TEXT NOT NULL DEFAULT '',
                output_path TEXT NOT NULL DEFAULT '',
                output_url TEXT NOT NULL DEFAULT '',
                cover_path TEXT NOT NULL DEFAULT '',
                cover_url TEXT NOT NULL DEFAULT '',
                run_log_path TEXT NOT NULL DEFAULT '',
                error_message TEXT NOT NULL DEFAULT '',
                downloads_json TEXT NOT NULL DEFAULT '{}',
                provider_payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                started_at TEXT NOT NULL DEFAULT '',
                completed_at TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(template_id) REFERENCES digital_human_template(template_id)
            );

            CREATE INDEX IF NOT EXISTS idx_dh_video_task_created_at
            ON digital_human_video_task(created_at DESC);

            CREATE TABLE IF NOT EXISTS studio_workflow_task (
                task_id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL DEFAULT '',
                project_id TEXT NOT NULL DEFAULT '',
                task_type TEXT NOT NULL,
                stage TEXT NOT NULL,
                source_type TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0,
                outputs_json TEXT NOT NULL DEFAULT '{}',
                error_message TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_studio_workflow_task_created_at
            ON studio_workflow_task(created_at DESC);

            CREATE TABLE IF NOT EXISTS digital_human_sync_record (
                sync_id TEXT PRIMARY KEY,
                provider_code TEXT NOT NULL,
                direction TEXT NOT NULL,
                status TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                raw_response_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )


def get_connection() -> sqlite3.Connection:
    init_database()
    connection = sqlite3.connect(DB_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


@contextmanager
def connection_scope() -> Iterator[sqlite3.Connection]:
    connection = get_connection()
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()
