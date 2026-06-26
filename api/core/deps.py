import jwt
from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.jwt import decode_access_token
from core.permissions import get_account_permissions
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


def require_permission(function: str, action: str):
    """지정한 기능의 action 권한이 있는 계정만 접근을 허용하는 의존성 팩토리.

    action: "create" | "read" | "update" | "delete"
    """

    async def dependency(
        account: Account = Depends(get_current_account),
        db: AsyncSession = Depends(get_db),
    ) -> Account:
        perm_info = await get_account_permissions(db, account.id)
        fn_perm = perm_info["permissions"].get(function)
        if not fn_perm or not fn_perm.get(action, False):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"'{function}' 기능의 {action} 권한이 없습니다",
            )
        return account

    return dependency
