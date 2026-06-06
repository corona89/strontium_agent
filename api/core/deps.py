import jwt
from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.jwt import decode_access_token
from database.connection import get_db
from database.models import Account


async def get_current_account(
    access_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> Account:
    if not access_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "인증이 필요합니다")
    try:
        account_id = decode_access_token(access_token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "토큰이 만료됐습니다")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "유효하지 않은 토큰입니다")

    account = await db.get(Account, account_id)
    if not account or not account.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "계정을 찾을 수 없습니다")
    return account
