import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, JSON
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


class LLMProvider(Base):
    __tablename__ = "llm_providers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    # "ollama_cloud" | "opencode_zen"
    provider_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 모델 식별자 문자열 배열
    models: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    sessions: Mapped[list["DeepResearchSession"]] = relationship(
        "DeepResearchSession", back_populates="provider"
    )


class DeepResearchSession(Base):
    __tablename__ = "deep_research_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("llm_providers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # draft | awaiting_approval | approved | rejected | running | completed
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    plan: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    account: Mapped["Account"] = relationship("Account")
    provider: Mapped["LLMProvider | None"] = relationship("LLMProvider", back_populates="sessions")
    messages: Mapped[list["DeepResearchMessage"]] = relationship(
        "DeepResearchMessage", back_populates="session", cascade="all, delete-orphan",
        order_by="DeepResearchMessage.created_at",
    )


class DeepResearchMessage(Base):
    __tablename__ = "deep_research_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("deep_research_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # user | assistant | tool
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    # text | plan | step_progress | search | final
    kind: Mapped[str] = mapped_column(String(20), default="text", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    session: Mapped["DeepResearchSession"] = relationship("DeepResearchSession", back_populates="messages")


class Wiki(Base):
    __tablename__ = "wikis"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    provider_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("llm_providers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    pages: Mapped[list["WikiPage"]] = relationship(
        "WikiPage", back_populates="wiki", cascade="all, delete-orphan",
        order_by="WikiPage.created_at",
    )


class WikiPage(Base):
    __tablename__ = "wiki_pages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    wiki_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("wikis.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    slug: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 파일시스템이 진실의 원천; DB는 검색 인덱스용 콘텐츠 캐시
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    # md | deepresearch | pdf | image | youtube | manual
    source_type: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    wiki: Mapped["Wiki"] = relationship("Wiki", back_populates="pages")


class WikiChatMessage(Base):
    __tablename__ = "wiki_chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    wiki_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("wikis.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # user | assistant
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # [{type: wiki|web, title, ref, ...}]
    sources: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
