from datetime import datetime, timedelta, timezone

from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.jwt import create_access_token, generate_refresh_token
from database.models import Account, RefreshToken

_COOKIE = dict(httponly=True, samesite="lax", secure=settings.COOKIE_SECURE)


async def issue_session(account: Account, response: Response, db: AsyncSession):
    """계정에 대한 refresh token을 발급하고 access/refresh 쿠키를 설정한다."""
    plain, token_hash = generate_refresh_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db.add(RefreshToken(account_id=account.id, token_hash=token_hash, expires_at=expires_at))
    await db.commit()

    response.set_cookie(
        "access_token",
        create_access_token(account.id),
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        **_COOKIE,
    )
    response.set_cookie(
        "refresh_token",
        plain,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        **_COOKIE,
    )
