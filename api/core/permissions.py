from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.config import settings
from database.models import Account, AccountRole, Function, Role, RoleFunction


async def get_account_permissions(db: AsyncSession, account_id: str) -> dict:
    """계정의 권한 매트릭스를 반환한다.
    return: {
        "roles": ["운영자", ...],
        "permissions": { "users": {"create": True, "read": True, ...}, ... }
    }
    여러 역할의 권한은 합집합(OR).
    """
    # LOCAL_MODE(데스크톱 단일 사용자) — 모든 기능에 full 권한 보장.
    # 역할/DB 상태와 무관하게 require_permission(core/deps.py) 과 /auth/me(사이드바) 양쪽에 동일 적용.
    # 시스템 역할 삭제는 routers/roles.py 의 is_system 가드가 별도로 막으므로 안전.
    if settings.LOCAL_MODE:
        fns = (await db.scalars(select(Function))).all()
        permissions = {
            fn.name: {"create": True, "read": True, "update": True, "delete": True}
            for fn in fns
        }
        return {"roles": ["운영자"], "permissions": permissions}

    rows = (
        await db.execute(
            select(RoleFunction, Function, Role)
            .join(RoleFunction.function)
            .join(RoleFunction.role)
            .join(AccountRole, AccountRole.role_id == Role.id)
            .where(AccountRole.account_id == account_id)
        )
    ).all()

    role_names: set[str] = set()
    permissions: dict[str, dict[str, bool]] = {}

    for rf, fn, role in rows:
        role_names.add(role.name)
        if fn.name not in permissions:
            permissions[fn.name] = {
                "create": False,
                "read": False,
                "update": False,
                "delete": False,
            }
        perm = permissions[fn.name]
        perm["create"] = perm["create"] or rf.can_create
        perm["read"] = perm["read"] or rf.can_read
        perm["update"] = perm["update"] or rf.can_update
        perm["delete"] = perm["delete"] or rf.can_delete

    return {"roles": sorted(role_names), "permissions": permissions}


async def get_account_role_ids(db: AsyncSession, account_id: str) -> list[str]:
    rows = await db.scalars(
        select(AccountRole.role_id).where(AccountRole.account_id == account_id)
    )
    return list(rows)


def can(permissions: dict, function: str, action: str) -> bool:
    fn_perm = permissions.get(function)
    if not fn_perm:
        return False
    return fn_perm.get(action, False)
