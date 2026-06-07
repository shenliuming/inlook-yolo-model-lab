from __future__ import annotations

import logging

from app.common import error_code
from app.common.exceptions import AppException
from app.dto.digital_human_dto import DigitalHumanGenerateRequestDTO

logger = logging.getLogger("inlook.yolo_api.digital_human")


def create_digital_human_video(request: DigitalHumanGenerateRequestDTO) -> dict[str, object]:
    logger.info(
        "digital_human_generate_requested avatarId=%s mode=%s textLength=%s audioId=%s",
        request.avatarId,
        request.mode,
        len(request.script),
        request.audioId or "",
    )
    raise AppException(
        error_code.INTERNAL_ERROR,
        "数字人引擎暂未接入。",
        status_code=501,
        data={
            "errorType": "digital_human_engine_not_ready",
            "avatarId": request.avatarId,
            "mode": request.mode,
        },
    )
