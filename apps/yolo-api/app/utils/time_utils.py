from __future__ import annotations

from datetime import datetime, timezone


def now_iso(*, seconds_only: bool = False) -> str:
    if seconds_only:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
    return datetime.now(timezone.utc).isoformat()

