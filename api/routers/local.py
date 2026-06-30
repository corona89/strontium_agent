"""로컬 데스크톱 모드 전용 엔드포인트.

main.py에서 settings.LOCAL_MODE == True 일 때만 마운트된다.
Electron main 프로세스가 서버 기동 후 /local/bootstrap 을 호출해
단일 로컬 관리자 계정으로 자동 로그인하기 위한 access/refresh 토큰을 받는다.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.session import create_session_tokens
from database.connection import get_db
from database.models import Account
from core.seed import LOCAL_ADMIN_EMAIL

router = APIRouter(prefix="/local", tags=["local"])


@router.post("/bootstrap")
async def bootstrap(db: AsyncSession = Depends(get_db)):
    if not settings.LOCAL_MODE:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    account = await db.scalar(select(Account).where(Account.email == LOCAL_ADMIN_EMAIL))
    if not account:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "로컬 관리자 계정이 아직 시드되지 않았습니다. 서버 시작 직후 다시 시도하세요.",
        )

    tokens = await create_session_tokens(account, db)
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "account_id": account.id,
    }
