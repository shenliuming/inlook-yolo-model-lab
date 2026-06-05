from __future__ import annotations

from pydantic import BaseModel, Field


class MaterialVideoSourceVO(BaseModel):
    label: str
    url: str
    width: int = 0
    height: int = 0
    fileSize: int = 0


class MaterialVideoVO(BaseModel):
    url: str = ""
    width: int = 0
    height: int = 0
    duration: float = 0.0
    fileSize: int = 0
    sources: list[MaterialVideoSourceVO] = Field(default_factory=list)


class MaterialImageVO(BaseModel):
    url: str
    thumbnailUrl: str = ""
    label: str = ""


class MaterialVO(BaseModel):
    materialId: str
    materialType: str = "video"
    sourceType: str
    sourceUrl: str
    finalUrl: str = ""
    rawInput: str = ""
    title: str
    description: str
    authorName: str = ""
    tags: list[str] = Field(default_factory=list)
    video: MaterialVideoVO = Field(default_factory=MaterialVideoVO)
    images: list[MaterialImageVO] = Field(default_factory=list)
    coverUrl: str = ""
    musicUrl: str = ""
    extractor: str = ""
    cacheHit: bool = False
    status: str
    errorMessage: str | None = None
    createdAt: str | None = None
    updatedAt: str | None = None
