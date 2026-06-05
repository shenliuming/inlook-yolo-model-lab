from __future__ import annotations

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse

from app.common.result import success
from app.dto.material_dto import MaterialDownloadRequestDTO, MaterialExtractRequestDTO
from app.services.material_download_service import download_material_video
from app.services.material_service import extract_material, get_material, get_material_file, upload_material

router = APIRouter(prefix="/api/v1/materials", tags=["materials"])


@router.post("/extract")
def extract_material_handler(request: MaterialExtractRequestDTO):
    return success(
        extract_material(
            source_type=request.resolved_source_type,
            raw_input=request.raw_input,
            raw_url=request.normalized_url,
        )
    )


@router.post("/upload")
async def upload_material_handler(file: UploadFile = File(...)):
    return success(upload_material(file))


@router.post("/{material_id}/download")
def download_material_handler(material_id: str, request: MaterialDownloadRequestDTO):
    return success(download_material_video(material_id, source_index=request.sourceIndex))


@router.get("/{material_id}")
def get_material_handler(material_id: str):
    return success(get_material(material_id))


@router.get("/{material_id}/files/{filename}")
def get_material_file_handler(material_id: str, filename: str):
    path = get_material_file(material_id, filename)
    return FileResponse(path, filename=path.name)
