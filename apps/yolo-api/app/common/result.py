from __future__ import annotations

from fastapi.responses import JSONResponse

from app.common import error_code


def success(data: object | None = None, message: str = "success") -> dict[str, object | None]:
    return {
        "code": error_code.SUCCESS,
        "message": message,
        "data": data,
    }


def failure(
    code: int,
    message: str,
    *,
    data: object | None = None,
    status_code: int = 400,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "data": data,
        },
    )

