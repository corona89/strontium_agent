from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator


ProviderType = Literal["ollama_cloud", "opencode_zen", "abclab"]


def _validate_base_url(v: str | None) -> str | None:
    """base_url은 http(s) URL이거나 null(기본값 사용). 빈 문자열은 null로 정규화."""
    if v is None or v.strip() == "":
        return None
    v = v.strip()
    if not (v.startswith("http://") or v.startswith("https://")):
        raise ValueError("base_url은 http:// 또는 https:// 로 시작하는 URL이어야 합니다")
    return v


class ProviderBase(BaseModel):
    provider_type: ProviderType
    display_name: str
    base_url: str | None = None
    models: list[str] = []
    is_active: bool = True

    @field_validator("base_url")
    @classmethod
    def _check_base_url(cls, v: str | None) -> str | None:
        return _validate_base_url(v)


class ProviderCreate(ProviderBase):
    # 평문 API 키 — 쓰기 전용. 암호화해 DB에 저장되고 응답에 절대 노출되지 않는다(NFR-S11).
    api_key: str

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

    @field_validator("api_key")
    @classmethod
    def api_key_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("API 키는 필수입니다")
        return v.strip()


class ProviderUpdate(BaseModel):
    display_name: str | None = None
    base_url: str | None = None
    models: list[str] | None = None
    is_active: bool | None = None
    # 평문 API 키(선택) — 제공 시 기존 키를 교체(재암호화). 응답에 노출되지 않는다(NFR-S11).
    api_key: str | None = None

    @field_validator("base_url")
    @classmethod
    def _check_base_url(cls, v: str | None) -> str | None:
        return _validate_base_url(v)

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

    @field_validator("api_key")
    @classmethod
    def api_key_not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("API 키는 비워둘 수 없습니다(교체하지 않으려면 생략하세요)")
        return v.strip() if v else v


class ProviderResponse(BaseModel):
    id: str
    provider_type: str
    display_name: str
    base_url: str | None
    models: list[str]
    is_active: bool
    # 키 설정 여부(암호문 존재 여부) — 평문 키는 절대 노출하지 않음(NFR-S11)
    api_key_configured: bool
    # 마스킹된 키(예: code-...WE6X) — 식별 목적만, 평문 아님
    api_key_masked: str | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
