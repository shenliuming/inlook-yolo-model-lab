from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError

from app.common import error_code
from app.common.result import failure


class AppException(Exception):
    def __init__(self, code: int, message: str, *, status_code: int = 400, data: object | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.data = data


def register_exception_handlers(app: FastAPI) -> None:
    logger = logging.getLogger("inlook.yolo_api")

    @app.exception_handler(AppException)
    async def handle_app_exception(_: Request, exc: AppException):
        return failure(exc.code, exc.message, data=exc.data, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError):
        message = "; ".join(error["msg"] for error in exc.errors()) or "请求参数不合法"
        return failure(error_code.VALIDATION_ERROR, message, status_code=422)

    @app.exception_handler(HTTPException)
    async def handle_http_exception(_: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, str) else "请求失败"
        code_map = {
            400: error_code.BAD_REQUEST,
            401: error_code.UNAUTHORIZED,
            403: error_code.FORBIDDEN,
            404: error_code.NOT_FOUND,
            429: error_code.RATE_LIMITED,
        }
        mapped_code = code_map.get(exc.status_code, error_code.INTERNAL_ERROR)
        return failure(mapped_code, detail, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(_: Request, exc: Exception):
        logger.exception("Unhandled exception", exc_info=exc)
        return failure(error_code.INTERNAL_ERROR, "服务内部异常", status_code=500)
