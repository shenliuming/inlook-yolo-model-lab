from __future__ import annotations

from pydantic import BaseModel, Field


class MaterialExtractRequestDTO(BaseModel):
    sourceType: str = Field(default="auto")
    type: str | None = None
    input: str = ""
    url: str = ""
    urls: list[str] = Field(default_factory=list)

    @property
    def resolved_source_type(self) -> str:
        return (self.sourceType or self.type or "auto").strip() or "auto"

    @property
    def raw_input(self) -> str:
        return (self.input or "").strip()

    @property
    def candidate_url(self) -> str:
        return (self.url or "").strip()

    @property
    def normalized_url(self) -> str:
        return self.candidate_url

    @property
    def candidate_urls(self) -> list[str]:
        return [str(item or "").strip() for item in self.urls if str(item or "").strip()]


class MaterialDownloadRequestDTO(BaseModel):
    sourceIndex: int | None = None
