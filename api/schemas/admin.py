from datetime import datetime

from pydantic import BaseModel, field_validator


class FunctionBase(BaseModel):
    name: str
    description: str | None = None


class FunctionCreate(FunctionBase):
    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError("기능명은 공백일 수 없습니다")
        return v.strip()


class FunctionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str | None) -> str | None:
        if v is not None and len(v.strip()) == 0:
            raise ValueError("기능명은 공백일 수 없습니다")
        return v.strip() if v else v


class FunctionResponse(BaseModel):
    id: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class RoleBase(BaseModel):
    name: str
    description: str | None = None


class RoleCreate(RoleBase):
    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError("역할명은 공백일 수 없습니다")
        return v.strip()


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str | None) -> str | None:
        if v is not None and len(v.strip()) == 0:
            raise ValueError("역할명은 공백일 수 없습니다")
        return v.strip() if v else v


class RoleFunctionEntry(BaseModel):
    function_id: str
    can_create: bool = False
    can_read: bool = False
    can_update: bool = False
    can_delete: bool = False


class RoleFunctionMapping(BaseModel):
    function_id: str
    function_name: str
    can_create: bool
    can_read: bool
    can_update: bool
    can_delete: bool


class RoleResponse(BaseModel):
    id: str
    name: str
    description: str | None
    is_system: bool
    created_at: datetime
    updated_at: datetime
    functions: list[RoleFunctionMapping] = []
    model_config = {"from_attributes": True}


class AdminUserResponse(BaseModel):
    id: str
    email: str
    nickname: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    roles: list[dict] = []  # [{id, name}]


class AdminUserListResponse(BaseModel):
    users: list[AdminUserResponse]
    total: int


class UpdateUserRoles(BaseModel):
    role_ids: list[str]


class ResetPasswordResponse(BaseModel):
    temporary_password: str


class AuditLogResponse(BaseModel):
    id: str
    actor_id: str | None
    actor_email: str | None = None
    target_id: str | None
    target_email: str | None = None
    action: str
    detail: str | None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    logs: list[AuditLogResponse]
    total: int
