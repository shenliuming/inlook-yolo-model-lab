from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config.paths import INLOOK_STUDIO_DB_PATH

logger = logging.getLogger("inlook.yolo_api.db")

DATABASE_URL = f"sqlite:///{INLOOK_STUDIO_DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_database() -> bool:
    try:
        INLOOK_STUDIO_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        from app.db.models import Base

        Base.metadata.create_all(bind=engine)
        logger.info("SQLite database ready: %s", INLOOK_STUDIO_DB_PATH)
        return True
    except Exception as exc:
        logger.exception("Failed to initialize SQLite database: %s", exc)
        return False
