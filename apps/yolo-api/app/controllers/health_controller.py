from __future__ import annotations

from fastapi import APIRouter, Request

from app.clients.yolo_client import enforce_rate_limit
from app.common.result import success
from app.services.vision_service import get_health_payload

router = APIRouter(tags=["health"])


@router.get("/api/v1/health")
def health_check(request: Request):
    enforce_rate_limit(request, "health")
    return success(get_health_payload("INLOOK AI 工作台 backend is running"))


@router.get("/api/health")
def legacy_health_check(request: Request):
    enforce_rate_limit(request, "health")
    return get_health_payload("INLOOK AI 工作台 backend is running")

