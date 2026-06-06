from __future__ import annotations

from fastapi import APIRouter

from app.clients.llm_client import create_llm_client
from app.common.result import success
from app.dto.ai_dto import AiTestRequestDTO, CopyRewriteRequestDTO
from app.services.copy_rewrite_service import rewrite_copy

router = APIRouter(prefix="/api/v1", tags=["studio-ai"])


@router.get("/ai/status")
def get_ai_status_handler():
    return success(create_llm_client().status())


@router.post("/ai/test")
def test_ai_handler(request: AiTestRequestDTO):
    text = create_llm_client().chat(
        [
            {"role": "system", "content": "你是 INLOOK Studio 的模型连通性测试助手。"},
            {"role": "user", "content": request.prompt},
        ],
        temperature=0.2,
        max_tokens=300,
    )
    return success({"available": True, "text": text})


@router.post("/copy/rewrite")
def rewrite_copy_handler(request: CopyRewriteRequestDTO):
    return success(rewrite_copy(request))
