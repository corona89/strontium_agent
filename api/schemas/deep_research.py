from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator


SessionStatus = Literal["draft", "awaiting_approval", "approved", "rejected", "running", "completed"]


class PlanStep(BaseModel):
    id: str
    title: str
    query: str | None = None
    done: bool = False


class SessionCreate(BaseModel):
    provider_id: str
    model: str
    title: str | None = None


class SessionResponse(BaseModel):
    id: str
    account_id: str
    provider_id: str | None
    model: str
    title: str | None
    status: str
    plan: list[PlanStep] | None = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: str
    role: str
    kind: str
    content: str
    created_at: datetime
    model_config = {"from_attributes": True}


class SessionDetailResponse(SessionResponse):
    messages: list[MessageResponse] = []


class PlanUpdate(BaseModel):
    steps: list[PlanStep]

    @field_validator("steps")
    @classmethod
    def steps_not_empty(cls, v: list[PlanStep]) -> list[PlanStep]:
        if not v:
            raise ValueError("플랜은 최소 한 개의 스텝이 필요합니다")
        return v


class SendMessage(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError("메시지 내용은 공백일 수 없습니다")
        return v.strip()


class ProviderForSelection(BaseModel):
    id: str
    display_name: str
    provider_type: str
    models: list[str]


class ModelsForSelectionResponse(BaseModel):
    providers: list[ProviderForSelection]
