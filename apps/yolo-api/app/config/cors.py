from __future__ import annotations

from app.config.settings import get_allowed_origins


def build_cors_config() -> dict[str, object]:
    return {
        "allow_origins": get_allowed_origins(),
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }

