import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.audit import log_action
from core.deps import require_permission
from core.permissions import get_account_role_ids
from core.security import hash_password
from database.connection import get_db
from database.models import Account, AccountRole, AuditLog, Role
from schemas.admin import (
    AdminUserListResponse,
    AdminUserResponse,
    AuditLogListResponse,
    AuditLogResponse,
    ResetPasswordResponse,
    UpdateUserRoles,
)

router = APIRouter(prefix="/admin", tags=["admin"])


async def _user_with_roles(db: AsyncSession, account: Account) -> AdminUserResponse:
    role_ids = await get_account_role_ids(db, account.id)
    roles = []
    for rid in role_ids:
        role = await db.get(Role, rid)
        if role:
            roles.append({"id": role.id, "name": role.name})
    return AdminUserResponse(
        id=account.id,
        email=account.email,
        nickname=account.nickname,
        is_active=account.is_active,
        created_at=account.created_at,
        updated_at=account.updated_at,
        roles=roles,
    )


@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("users", "read")),
):
    total = await db.scalar(select(func.count(Account.id)))
    offset = (page - 1) * page_size
    accounts = await db.scalars(
        select(Account).order_by(Account.created_at.desc()).offset(offset).limit(page_size)
    )
    users = [await _user_with_roles(db, a) for a in accounts]
    return AdminUserListResponse(users=users, total=total or 0)


@router.patch("/users/{user_id}/roles", response_model=AdminUserResponse)
async def update_user_roles(
    user_id: str,
    body: UpdateUserRoles,
    db: AsyncSession = Depends(get_db),
    admin: Account = Depends(require_permission("users", "update")),
):
    target = await db.get(Account, user_id)
    if not target or not target.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "사용자를 찾을 수 없습니다")

    old_role_ids = await get_account_role_ids(db, user_id)
    old_role_names = []
    for rid in old_role_ids:
        r = await db.get(Role, rid)
        if r:
            old_role_names.append(r.name)

    # 유효한 역할 ID 검증
    new_roles = []
    for rid in body.role_ids:
        r = await db.get(Role, rid)
        if not r:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"역할 {rid}를 찾을 수 없습니다")
        new_roles.append(r)

    # 기존 매핑 삭제
    old_mappings = await db.scalars(
        select(AccountRole).where(AccountRole.account_id == user_id)
    )
    for ar in old_mappings:
        await db.delete(ar)
    await db.flush()

    for r in new_roles:
        db.add(AccountRole(account_id=user_id, role_id=r.id))

    new_role_names = [r.name for r in new_roles]
    await log_action(
        db,
        actor_id=admin.id,
        target_id=user_id,
        action="admin.change_role",
        detail={"roles_before": old_role_names, "roles_after": new_role_names},
    )
    await db.commit()
    await db.refresh(target)
    return await _user_with_roles(db, target)


@router.post("/users/{user_id}/reset-password", response_model=ResetPasswordResponse)
async def reset_user_password(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: Account = Depends(require_permission("users", "update")),
):
    target = await db.get(Account, user_id)
    if not target or not target.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "사용자를 찾을 수 없습니다")

    temp_password = secrets.token_urlsafe(12)[:16]
    target.hashed_password = hash_password(temp_password)
    await log_action(
        db,
        actor_id=admin.id,
        target_id=user_id,
        action="admin.reset_password",
        detail={"email": target.email},
    )
    await db.commit()
    return ResetPasswordResponse(temporary_password=temp_password)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: Account = Depends(require_permission("users", "delete")),
):
    target = await db.get(Account, user_id)
    if not target or not target.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "사용자를 찾을 수 없습니다")
    if admin.id == user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "자기 자신은 비활성화할 수 없습니다")

    target.is_active = False
    await log_action(
        db,
        actor_id=admin.id,
        target_id=user_id,
        action="admin.deactivate_user",
        detail={"email": target.email},
    )
    await db.commit()


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("audit", "read")),
):
    total = await db.scalar(select(func.count(AuditLog.id)))
    offset = (page - 1) * page_size
    logs = await db.scalars(
        select(AuditLog).order_by(AuditLog.created_at.desc()).offset(offset).limit(page_size)
    )

    # actor/target 이메일 일괄 조회
    email_cache: dict[str, str] = {}
    result = []
    for log in logs:
        for aid in (log.actor_id, log.target_id):
            if aid and aid not in email_cache:
                acc = await db.get(Account, aid)
                email_cache[aid] = acc.email if acc else ""
        result.append(
            AuditLogResponse(
                id=log.id,
                actor_id=log.actor_id,
                actor_email=email_cache.get(log.actor_id) if log.actor_id else None,
                target_id=log.target_id,
                target_email=email_cache.get(log.target_id) if log.target_id else None,
                action=log.action,
                detail=log.detail,
                created_at=log.created_at,
            )
        )
    return AuditLogListResponse(logs=result, total=total or 0)
