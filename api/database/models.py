import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.connection import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    nickname: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # None이면 SSO 전용 계정 (비밀번호 로그인 불가)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship(
        "OAuthAccount", back_populates="account", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="account", cascade="all, delete-orphan"
    )
    account_roles: Mapped[list["AccountRole"]] = relationship(
        "AccountRole", back_populates="account", cascade="all, delete-orphan"
    )


class OAuthAccount(Base):
    __tablename__ = "oauth_accounts"
    __table_args__ = (UniqueConstraint("provider", "provider_user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "google"
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    access_token: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    account: Mapped["Account"] = relationship("Account", back_populates="oauth_accounts")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    account: Mapped["Account"] = relationship("Account", back_populates="refresh_tokens")


class Function(Base):
    __tablename__ = "functions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    role_functions: Mapped[list["RoleFunction"]] = relationship(
        "RoleFunction", back_populates="function", cascade="all, delete-orphan"
    )


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    role_functions: Mapped[list["RoleFunction"]] = relationship(
        "RoleFunction", back_populates="role", cascade="all, delete-orphan"
    )
    account_roles: Mapped[list["AccountRole"]] = relationship(
        "AccountRole", back_populates="role", cascade="all, delete-orphan"
    )


class RoleFunction(Base):
    __tablename__ = "role_functions"
    __table_args__ = (UniqueConstraint("role_id", "function_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    role_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    function_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("functions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    can_create: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_update: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_delete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    role: Mapped["Role"] = relationship("Role", back_populates="role_functions")
    function: Mapped["Function"] = relationship("Function", back_populates="role_functions")


class AccountRole(Base):
    __tablename__ = "account_roles"
    __table_args__ = (UniqueConstraint("account_id", "role_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    account: Mapped["Account"] = relationship("Account", back_populates="account_roles")
    role: Mapped["Role"] = relationship("Role", back_populates="account_roles")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    actor_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    target_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
