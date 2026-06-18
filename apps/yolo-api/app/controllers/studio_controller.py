from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, File, UploadFile
from fastapi.responses import FileResponse

from app.common.result import success
from app.dto.ai_dto import CopyRewriteRequestDTO
from app.dto.digital_human_dto import DigitalHumanGenerateRequestDTO
from app.dto.material_dto import MaterialExtractRequestDTO
from app.dto.studio_dto import TtsSynthesisCreateRequestDTO
from app.dto.studio_project_dto import (
    StudioProjectCreateRequestDTO,
    StudioProjectTranscriptionRequestDTO,
)
from app.services.project_runtime_service import read_project_file
from app.services.project_workflow_service import (
    create_studio_project,
    get_studio_project,
    studio_get_digital_human_task,
    list_studio_tasks,
    studio_create_digital_human_task,
    studio_create_synthesis,
    studio_create_transcription,
    studio_extract_material,
    studio_get_synthesis,
    studio_rewrite_copy,
    studio_upload_material,
)

router = APIRouter(prefix="/api/v1/studio", tags=["studio"])


@router.post("/projects")
def create_project_handler(request: StudioProjectCreateRequestDTO):
    return success(create_studio_project(name=request.name))


@router.get("/projects/{project_id}")
def read_project_handler(project_id: str):
    return success(get_studio_project(project_id))


@router.get("/tasks")
def read_studio_tasks_handler(limit: int = 50):
    return success(list_studio_tasks(limit=limit))


@router.post("/projects/{project_id}/materials/extract")
def extract_project_material_handler(project_id: str, request: MaterialExtractRequestDTO):
    return success(studio_extract_material(project_id, request))


@router.post("/projects/{project_id}/materials/upload")
async def upload_project_material_handler(project_id: str, file: UploadFile = File(...)):
    return success(studio_upload_material(project_id, file))


@router.post("/projects/{project_id}/transcriptions")
def create_project_transcription_handler(project_id: str, request: StudioProjectTranscriptionRequestDTO):
    return success(studio_create_transcription(project_id, request))


@router.post("/projects/{project_id}/copy/rewrite")
def rewrite_project_copy_handler(project_id: str, request: CopyRewriteRequestDTO):
    return success(studio_rewrite_copy(project_id, request))


@router.post("/projects/{project_id}/tts/synthesis")
async def create_project_synthesis_handler(
    project_id: str,
    request: TtsSynthesisCreateRequestDTO,
    background_tasks: BackgroundTasks,
):
    return success(studio_create_synthesis(project_id, background_tasks, request))


@router.get("/projects/{project_id}/tts/synthesis/{synthesis_id}")
def read_project_synthesis_handler(project_id: str, synthesis_id: str):
    return success(studio_get_synthesis(project_id, synthesis_id))


@router.post("/projects/{project_id}/digital-human/generate")
def create_project_digital_human_handler(
    project_id: str,
    request: DigitalHumanGenerateRequestDTO,
    background_tasks: BackgroundTasks,
):
    return success(studio_create_digital_human_task(project_id, background_tasks, request))


@router.get("/projects/{project_id}/digital-human/{task_id}")
def read_project_digital_human_handler(project_id: str, task_id: str):
    return success(studio_get_digital_human_task(project_id, task_id))


@router.get("/projects/{project_id}/files/{file_path:path}")
def read_project_file_handler(project_id: str, file_path: str):
    path = read_project_file(project_id, file_path)
    return FileResponse(path, filename=path.name)
