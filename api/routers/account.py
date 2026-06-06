from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password
from database.connection import get_db
from database.models import Account
from schemas.account import AccountCreate, AccountResponse, AccountUpdate

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(body: AccountCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(Account).where(Account.email == body.email))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 사용 중인 이메일입니다")

    account = Account(
        email=body.email,
        hashed_password=hash_password(body.password),
        nickname=body.nickname,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@router.patch("/{account_id}", response_model=AccountResponse)
async def update_account(account_id: str, body: AccountUpdate, db: AsyncSession = Depends(get_db)):
    account = await db.get(Account, account_id)
    if not account or not account.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="계정을 찾을 수 없습니다")

    updated = False
    if "nickname" in body.model_fields_set:
        account.nickname = body.nickname
        updated = True
    if "password" in body.model_fields_set and body.password is not None:
        account.hashed_password = hash_password(body.password)
        updated = True

    if updated:
        account.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(account)

    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_account(account_id: str, db: AsyncSession = Depends(get_db)):
    account = await db.get(Account, account_id)
    if not account or not account.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="계정을 찾을 수 없습니다")

    account.is_active = False
    account.updated_at = datetime.now(timezone.utc)
    await db.commit()
