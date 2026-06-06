from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.deps import get_current_account
from core.jwt import create_access_token, generate_refresh_token, hash_refresh_token
from core.security import verify_password
from database.connection import get_db
from database.models import Account, RefreshToken
from schemas.account import AccountResponse
from schemas.auth import LoginRequest

router = APIRouter(prefix="/auth", tags=["auth"])

_COOKIE = dict(httponly=True, samesite="lax", secure=settings.COOKIE_SECURE)


@router.get("/me", response_model=AccountResponse)
async def me(account: Account = Depends(get_current_account)):
    return account


@router.post("/login", status_code=status.HTTP_204_NO_CONTENT)
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    account = await db.scalar(select(Account).where(Account.email == body.email))
    if not account or not account.is_active or not account.hashed_password:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "이메일 또는 비밀번호가 올바르지 않습니다")
    if not verify_password(body.password, account.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "이메일 또는 비밀번호가 올바르지 않습니다")

    plain, token_hash = generate_refresh_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db.add(RefreshToken(account_id=account.id, token_hash=token_hash, expires_at=expires_at))
    await db.commit()

    response.set_cookie("access_token", create_access_token(account.id),
                        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, **_COOKIE)
    response.set_cookie("refresh_token", plain,
                        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400, **_COOKIE)


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
    plain, token_hash = generate_refresh_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db.add(RefreshToken(account_id=account.id, token_hash=token_hash, expires_at=expires_at))
    await db.commit()

    response.set_cookie("access_token", create_access_token(account.id),
                        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, **_COOKIE)
    response.set_cookie("refresh_token", plain,
                        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400, **_COOKIE)


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
