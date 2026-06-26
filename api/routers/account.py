from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.audit import log_action
from core.deps import get_current_account
from core.limiter import limiter
from core.seed import ADMIN_EMAIL, ensure_admin_role
from core.security import hash_password
from database.connection import get_db
from database.models import Account
from schemas.account import AccountCreate, AccountResponse, AccountUpdate

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
async def create_account(request: Request, body: AccountCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(Account).where(Account.email == body.email))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 사용 중인 이메일입니다")

    account = Account(
        email=body.email,
        hashed_password=hash_password(body.password),
        nickname=body.nickname,
    )
    db.add(account)
    await db.flush()

    if body.email == ADMIN_EMAIL:
        await ensure_admin_role(db, account.id)

    await log_action(db, actor_id=account.id, target_id=account.id, action="signup",
                     detail={"email": account.email, "nickname": account.nickname})
    await db.commit()
    await db.refresh(account)
    return AccountResponse(
        id=account.id,
        email=account.email,
        nickname=account.nickname,
        is_active=account.is_active,
        created_at=account.created_at,
        updated_at=account.updated_at,
        roles=[],
        permissions={},
    )


@router.patch("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: str,
    body: AccountUpdate,
    db: AsyncSession = Depends(get_db),
    current: Account = Depends(get_current_account),
):
    if current.id != account_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="다른 계정은 수정할 수 없습니다")

    account = await db.get(Account, account_id)
    if not account or not account.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="계정을 찾을 수 없습니다")

    updated = False
    detail: dict = {}
    if "nickname" in body.model_fields_set:
        detail["nickname_before"] = account.nickname
        detail["nickname_after"] = body.nickname
        account.nickname = body.nickname
        updated = True
    if "password" in body.model_fields_set and body.password is not None:
        account.hashed_password = hash_password(body.password)
        detail["password_changed"] = True
        updated = True

    if updated:
        account.updated_at = datetime.now(timezone.utc)
        await log_action(
            db,
            actor_id=account.id,
            target_id=account.id,
            action="change_password" if detail.get("password_changed") and not detail.get("nickname_before") and "nickname_before" not in detail else "update_profile",
            detail=detail,
        )
        await db.commit()
        await db.refresh(account)

    from core.permissions import get_account_permissions
    perm_info = await get_account_permissions(db, account.id)
    return AccountResponse(
        id=account.id,
        email=account.email,
        nickname=account.nickname,
        is_active=account.is_active,
        created_at=account.created_at,
        updated_at=account.updated_at,
        roles=perm_info["roles"],
        permissions=perm_info["permissions"],
    )


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current: Account = Depends(get_current_account),
):
    if current.id != account_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="다른 계정은 삭제할 수 없습니다")

    account = await db.get(Account, account_id)
    if not account or not account.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="계정을 찾을 수 없습니다")

    account.is_active = False
    account.updated_at = datetime.now(timezone.utc)
    await log_action(
        db,
        actor_id=account.id,
        target_id=account.id,
        action="update_profile",
        detail={"deactivated": True},
    )
    await db.commit()
