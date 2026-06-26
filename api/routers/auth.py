from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.deps import get_current_account
from core.jwt import hash_refresh_token
from core.limiter import limiter
from core.permissions import get_account_permissions
from core.security import verify_password
from core.session import issue_session
from database.connection import get_db
from database.models import Account, RefreshToken
from schemas.account import AccountResponse
from schemas.auth import LoginRequest

router = APIRouter(prefix="/auth", tags=["auth"])

_COOKIE = dict(httponly=True, samesite="lax", secure=settings.COOKIE_SECURE)


@router.get("/me", response_model=AccountResponse)
async def me(account: Account = Depends(get_current_account), db: AsyncSession = Depends(get_db)):
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


@router.post("/login", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    account = await db.scalar(select(Account).where(Account.email == body.email))
    if not account or not account.is_active or not account.hashed_password:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "이메일 또는 비밀번호가 올바르지 않습니다")
    if not verify_password(body.password, account.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "이메일 또는 비밀번호가 올바르지 않습니다")

    await issue_session(account, response, db)


@router.post("/refresh", status_code=status.HTTP_204_NO_CONTENT)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not refresh_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "refresh token이 없습니다")

    rt = await db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(refresh_token))
    )
    if not rt or rt.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "유효하지 않은 refresh token입니다")

    account = await db.get(Account, rt.account_id)
    if not account or not account.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "계정을 찾을 수 없습니다")

    # Refresh Token Rotation
    await db.delete(rt)
    await issue_session(account, response, db)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if refresh_token:
        rt = await db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(refresh_token))
        )
        if rt:
            await db.delete(rt)
            await db.commit()

    response.delete_cookie("access_token", httponly=True, samesite="lax", secure=settings.COOKIE_SECURE)
    response.delete_cookie("refresh_token", httponly=True, samesite="lax", secure=settings.COOKIE_SECURE)
