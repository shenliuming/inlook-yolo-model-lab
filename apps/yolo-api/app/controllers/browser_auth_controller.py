from __future__ import annotations

from fastapi import APIRouter

from app.common.result import success
from app.services.browser_auth_service import (
    clear_browser_authorization,
    get_browser_auth_status,
    start_browser_authorization,
)

router = APIRouter(prefix="/api/v1/browser-auth", tags=["browser-auth"])


@router.post("/{platform}/start")
def start_browser_auth_handler(platform: str):
    return success(start_browser_authorization(platform))


@router.get("/{platform}/status")
def browser_auth_status_handler(platform: str):
    return success(get_browser_auth_status(platform))


@router.delete("/{platform}")
def clear_browser_auth_handler(platform: str):
    return success(clear_browser_authorization(platform))
