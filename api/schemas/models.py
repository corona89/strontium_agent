from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator


ProviderType = Literal["ollama_cloud", "opencode_zen"]


class ProviderBase(BaseModel):
    provider_type: ProviderType
    display_name: str
    base_url: str | None = None
    models: list[str] = []
    is_active: bool = True


class ProviderCreate(ProviderBase):
    @field_validator("display_name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError("표시명은 공백일 수 없습니다")
        return v.strip()

    @field_validator("models")
    @classmethod
    def models_not_empty(cls, v: list[str]) -> list[str]:
        cleaned = [m.strip() for m in v if m and m.strip()]
        if not cleaned:
            raise ValueError("최소 한 개의 모델 식별자가 필요합니다")
        return cleaned


class ProviderUpdate(BaseModel):
    display_name: str | None = None
    base_url: str | None = None
    models: list[str] | None = None
    is_active: bool | None = None

    @field_validator("display_name")
    @classmethod
    def name_not_blank(cls, v: str | None) -> str | None:
        if v is not None and len(v.strip()) == 0:
            raise ValueError("표시명은 공백일 수 없습니다")
        return v.strip() if v else v

    @field_validator("models")
    @classmethod
    def models_not_empty(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        cleaned = [m.strip() for m in v if m and m.strip()]
        if not cleaned:
            raise ValueError("최소 한 개의 모델 식별자가 필요합니다")
        return cleaned


class ProviderResponse(BaseModel):
    id: str
    provider_type: str
    display_name: str
    base_url: str | None
    models: list[str]
    is_active: bool
    # 환경변수 키가 설정되었는지 여부만 노출 (평문 키는 절대 노출하지 않음, NFR-S11)
    api_key_configured: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
