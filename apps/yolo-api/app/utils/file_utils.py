from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse


def safe_filename(filename: str) -> str:
    safe_name = Path(filename).name
    if safe_name != filename:
        raise HTTPException(status_code=400, detail="文件名无效")
    return safe_name


def file_response_from_directory(directory: Path, filename: str) -> FileResponse:
    safe_name = safe_filename(filename)
    file_path = directory / safe_name
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(file_path, filename=safe_name)
