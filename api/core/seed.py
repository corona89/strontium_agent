import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password
from database.models import Account, AccountRole, Function, Role, RoleFunction

logger = logging.getLogger(__name__)

ADMIN_EMAIL = "cpar2002@gmail.com"

_FUNCTION_DEFS = [
    ("home", "홈 페이지"),
    ("settings", "계정 설정"),
    ("users", "사용자 관리"),
    ("roles", "역할 및 권한 관리"),
    ("audit", "감사 로그"),
    ("deep_research", "딥 리서치 에이전트"),
    ("models", "모델 관리"),
    ("llmwiki", "LLM 위키"),
]

# role_name, is_system, { function_name: (c, r, u, d) }
_ROLE_DEFS = [
    (
        "운영자",
        True,
        "시스템 운영자",
        {
            "home": (True, True, True, True),
            "settings": (True, True, True, True),
            "users": (True, True, True, True),
            "roles": (True, True, True, False),  # roles.delete는 보호
            "audit": (True, True, True, True),
            "deep_research": (True, True, True, True),
            "models": (True, True, True, True),
            "llmwiki": (True, True, True, True),
        },
    ),
    (
        "프리미엄 사용자",
        False,
        "프리미엄 구독 사용자",
        {
            "home": (False, True, False, False),
            "settings": (False, True, True, True),
            "deep_research": (True, True, False, False),
            "llmwiki": (True, True, True, True),
        },
    ),
    (
        "사용자",
        False,
        "일반 사용자",
        {
            "home": (False, True, False, False),
            "settings": (False, True, True, True),
            "deep_research": (True, True, False, False),
            "llmwiki": (True, True, True, True),
        },
    ),
]


async def run_seed(db: AsyncSession) -> None:
    """멱등 시드: 기능, 역할, 역할-기능 매핑, 운영자 계정을 생성한다."""
    functions: dict[str, Function] = {}
    for name, desc in _FUNCTION_DEFS:
        fn = await db.scalar(select(Function).where(Function.name == name))
        if not fn:
            fn = Function(name=name, description=desc)
            db.add(fn)
            await db.flush()
        functions[name] = fn

    roles: dict[str, Role] = {}
    for role_name, is_system, role_desc, perms in _ROLE_DEFS:
        role = await db.scalar(select(Role).where(Role.name == role_name))
        if not role:
            role = Role(name=role_name, description=role_desc, is_system=is_system)
            db.add(role)
            await db.flush()
        roles[role_name] = role

        for fn_name, (c, r, u, d) in perms.items():
            fn = functions[fn_name]
            rf = await db.scalar(
                select(RoleFunction).where(
                    RoleFunction.role_id == role.id,
                    RoleFunction.function_id == fn.id,
                )
            )
            if not rf:
                rf = RoleFunction(
                    role_id=role.id,
                    function_id=fn.id,
                    can_create=c,
                    can_read=r,
                    can_update=u,
                    can_delete=d,
                )
                db.add(rf)
            else:
                rf.can_create = c
                rf.can_read = r
                rf.can_update = u
                rf.can_delete = d
        await db.flush()

    admin_role = roles["운영자"]
    admin_account = await db.scalar(select(Account).where(Account.email == ADMIN_EMAIL))
    if admin_account:
        ar = await db.scalar(
            select(AccountRole).where(
                AccountRole.account_id == admin_account.id,
                AccountRole.role_id == admin_role.id,
            )
        )
        if not ar:
            db.add(AccountRole(account_id=admin_account.id, role_id=admin_role.id))

    await db.commit()
    logger.info("Seed complete: %d functions, %d roles", len(functions), len(roles))


async def ensure_admin_role(db: AsyncSession, account_id: str) -> None:
    """cpar2002@gmail.com 계정에 운영자 역할이 없으면 부여한다 (회원가입/OAuth 시 호출)."""
    admin_role = await db.scalar(select(Role).where(Role.name == "운영자"))
    if not admin_role:
        return
    ar = await db.scalar(
        select(AccountRole).where(
            AccountRole.account_id == account_id,
            AccountRole.role_id == admin_role.id,
        )
    )
    if not ar:
        db.add(AccountRole(account_id=account_id, role_id=admin_role.id))
        await db.flush()


async def ensure_default_role(db: AsyncSession, account_id: str) -> None:
    """모든 신규 계정에 기본 '사용자' 역할을 부여한다 (FR-F26). 회원가입/OAuth 시 호출."""
    default_role = await db.scalar(select(Role).where(Role.name == "사용자"))
    if not default_role:
        return
    ar = await db.scalar(
        select(AccountRole).where(
            AccountRole.account_id == account_id,
            AccountRole.role_id == default_role.id,
        )
    )
    if not ar:
        db.add(AccountRole(account_id=account_id, role_id=default_role.id))
        await db.flush()
