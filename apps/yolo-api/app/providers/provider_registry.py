from __future__ import annotations

from fastapi import HTTPException

from app.providers.bilibili_provider import BilibiliProvider
from app.providers.douyin_provider import DouyinProvider
from app.providers.local_file_provider import LocalFileProvider
from app.providers.material_provider import MaterialProvider

_PROVIDERS: list[MaterialProvider] = [
    LocalFileProvider(),
    DouyinProvider(),
    BilibiliProvider(),
]


def get_material_provider(source_type: str) -> MaterialProvider:
    for provider in _PROVIDERS:
        if provider.support(source_type):
            return provider
    raise HTTPException(status_code=400, detail=f"暂不支持的 sourceType: {source_type}")


def list_material_source_types() -> list[dict[str, str]]:
    return [
        {"sourceType": "local", "label": "本地上传"},
        {"sourceType": "douyin", "label": "抖音链接"},
        {"sourceType": "bilibili", "label": "B 站链接"},
    ]
