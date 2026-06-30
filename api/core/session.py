from datetime import datetime, timedelta, timezone

from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.jwt import create_access_token, generate_refresh_token
from database.models import Account, RefreshToken

_COOKIE = dict(httponly=True, samesite="lax", secure=settings.COOKIE_SECURE)


async def create_session_tokens(account: Account, db: AsyncSession) -> dict:
    """계정에 대한 refresh token을 DB에 저장하고 access/refresh 토큰(plain)을 반환한다.

    반환된 토큰은 호출자가 쿠키로 설정하거나(JSON 응답용) 직접 사용한다.
    issue_session() 과 로컬 부트스트랩 엔드포인트가 이 함수를 공유한다.
    """
    plain, token_hash = generate_refresh_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db.add(RefreshToken(account_id=account.id, token_hash=token_hash, expires_at=expires_at))
    await db.commit()
    return {
        "access_token": create_access_token(account.id),
        "refresh_token": plain,
    }


async def issue_session(account: Account, response: Response, db: AsyncSession):
    """계정에 대한 refresh token을 발급하고 access/refresh 쿠키를 설정한다."""
    tokens = await create_session_tokens(account, db)
    response.set_cookie(
        "access_token",
        tokens["access_token"],
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        **_COOKIE,
    )
    response.set_cookie(
        "refresh_token",
        tokens["refresh_token"],
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        **_COOKIE,
    )
