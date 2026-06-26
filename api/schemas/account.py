from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator


class AccountCreate(BaseModel):
    email: EmailStr
    password: str
    nickname: str | None = None

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("비밀번호는 8자 이상이어야 합니다")
        return v

    @field_validator("nickname")
    @classmethod
    def nickname_length(cls, v: str | None) -> str | None:
        if v is not None and len(v.strip()) == 0:
            raise ValueError("닉네임은 공백만으로 이루어질 수 없습니다")
        return v


class AccountUpdate(BaseModel):
    nickname: str | None = None
    password: str | None = None

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) < 8:
            raise ValueError("비밀번호는 8자 이상이어야 합니다")
        return v

    @field_validator("nickname")
    @classmethod
    def nickname_length(cls, v: str | None) -> str | None:
        if v is not None and len(v.strip()) == 0:
            raise ValueError("닉네임은 공백만으로 이루어질 수 없습니다")
        return v


class AccountResponse(BaseModel):
    id: str
    email: str
    nickname: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    roles: list[str] = []
    permissions: dict[str, dict[str, bool]] = {}

    model_config = {"from_attributes": True}
