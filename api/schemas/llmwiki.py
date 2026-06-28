from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator


SourceType = Literal["md", "deepresearch", "pdf", "image", "youtube", "manual"]


class ProviderForSelection(BaseModel):
    id: str
    display_name: str
    provider_type: str
    models: list[str]


class ModelsForSelectionResponse(BaseModel):
    providers: list[ProviderForSelection]


class WikiCreate(BaseModel):
    title: str
    provider_id: str | None = None
    model: str | None = None

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError("위키 이름은 공백일 수 없습니다")
        return v.strip()


class WikiUpdate(BaseModel):
    title: str

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError("위키 이름은 공백일 수 없습니다")
        return v.strip()


class CategoryOut(BaseModel):
    id: str
    name: str
    slug: str


class PageSummary(BaseModel):
    id: str
    category_id: str | None
    slug: str
    title: str
    summary: str | None
    source_type: str
    source_ref: str | None
    created_at: datetime
    updated_at: datetime


class WikiSummary(BaseModel):
    id: str
    title: str
    provider_id: str | None
    model: str | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class WikiTree(BaseModel):
    categories: list[CategoryOut]
    pages: list[PageSummary]


class WikiDetail(WikiSummary):
    tree: WikiTree


class CategoryCreate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError("카테고리 이름은 공백일 수 없습니다")
        return v.strip()


class CategoryUpdate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError("카테고리 이름은 공백일 수 없습니다")
        return v.strip()


class PageCreate(BaseModel):
    category_id: str | None = None
    title: str
    content: str = ""

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError("페이지 제목은 공백일 수 없습니다")
        return v.strip()


class PageUpdate(BaseModel):
    title: str | None = None
    content: str

    @field_validator("content")
    @classmethod
    def content_any(cls, v: str) -> str:
        return v


class PageDetail(PageSummary):
    content: str
    category_slug: str | None = None


class IngestResult(BaseModel):
    created_pages: list[PageSummary]
    auto_categorized: bool = False
    created_categories: list[CategoryOut] = []


class ChatRequest(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError("질문은 공백일 수 없습니다")
        return v.strip()


class ChatSource(BaseModel):
    type: str  # wiki | web
    title: str
    ref: str | None = None


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    sources: list[dict] | None = None
    created_at: datetime
    model_config = {"from_attributes": True}
