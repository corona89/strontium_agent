from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.deps import require_permission
from database.connection import get_db
from database.models import Function, Role, RoleFunction
from schemas.admin import (
    FunctionCreate,
    FunctionResponse,
    FunctionUpdate,
    RoleCreate,
    RoleFunctionEntry,
    RoleResponse,
    RoleUpdate,
)

router = APIRouter(tags=["admin"])


# ── Functions ──────────────────────────────────────────────────────────────

@router.get("/functions", response_model=list[FunctionResponse])
async def list_functions(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("roles", "read")),
):
    rows = await db.scalars(select(Function).order_by(Function.name))
    return list(rows)


@router.post("/functions", response_model=FunctionResponse, status_code=status.HTTP_201_CREATED)
async def create_function(
    body: FunctionCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("roles", "create")),
):
    existing = await db.scalar(select(Function).where(Function.name == body.name))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 존재하는 기능명입니다")
    fn = Function(name=body.name, description=body.description)
    db.add(fn)
    await db.commit()
    await db.refresh(fn)
    return fn


@router.patch("/functions/{function_id}", response_model=FunctionResponse)
async def update_function(
    function_id: str,
    body: FunctionUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("roles", "update")),
):
    fn = await db.get(Function, function_id)
    if not fn:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "기능을 찾을 수 없습니다")
    if body.name is not None:
        existing = await db.scalar(
            select(Function).where(Function.name == body.name, Function.id != function_id)
        )
        if existing:
            raise HTTPException(status.HTTP_409_CONFLICT, "이미 존재하는 기능명입니다")
        fn.name = body.name
    if body.description is not None:
        fn.description = body.description
    await db.commit()
    await db.refresh(fn)
    return fn


@router.delete("/functions/{function_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_function(
    function_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("roles", "delete")),
):
    fn = await db.get(Function, function_id)
    if not fn:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "기능을 찾을 수 없습니다")
    await db.delete(fn)
    await db.commit()


# ── Roles ──────────────────────────────────────────────────────────────────


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("roles", "read")),
):
    roles = await db.scalars(select(Role).order_by(Role.name))
    result = []
    for role in roles:
        rfs = (
            await db.execute(
                select(RoleFunction, Function)
                .join(RoleFunction.function)
                .where(RoleFunction.role_id == role.id)
            )
        ).all()
        mappings = []
        for rf, fn in rfs:
            mappings.append(
                {
                    "function_id": rf.function_id,
                    "function_name": fn.name,
                    "can_create": rf.can_create,
                    "can_read": rf.can_read,
                    "can_update": rf.can_update,
                    "can_delete": rf.can_delete,
                }
            )
        result.append(
            RoleResponse(
                id=role.id,
                name=role.name,
                description=role.description,
                is_system=role.is_system,
                created_at=role.created_at,
                updated_at=role.updated_at,
                functions=mappings,
            )
        )
    return result


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    body: RoleCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("roles", "create")),
):
    existing = await db.scalar(select(Role).where(Role.name == body.name))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 존재하는 역할명입니다")
    role = Role(name=body.name, description=body.description, is_system=False)
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        created_at=role.created_at,
        updated_at=role.updated_at,
        functions=[],
    )


@router.patch("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: str,
    body: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("roles", "update")),
):
    role = await db.get(Role, role_id)
    if not role:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "역할을 찾을 수 없습니다")
    if body.name is not None:
        existing = await db.scalar(
            select(Role).where(Role.name == body.name, Role.id != role_id)
        )
        if existing:
            raise HTTPException(status.HTTP_409_CONFLICT, "이미 존재하는 역할명입니다")
        role.name = body.name
    if body.description is not None:
        role.description = body.description
    await db.commit()
    await db.refresh(role)
    rfs = (
        await db.execute(
            select(RoleFunction, Function)
            .join(RoleFunction.function)
            .where(RoleFunction.role_id == role.id)
        )
    ).all()
    mappings = []
    for rf, fn in rfs:
        mappings.append(
            {
                "function_id": rf.function_id,
                "function_name": fn.name,
                "can_create": rf.can_create,
                "can_read": rf.can_read,
                "can_update": rf.can_update,
                "can_delete": rf.can_delete,
            }
        )
    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        created_at=role.created_at,
        updated_at=role.updated_at,
        functions=mappings,
    )


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("roles", "delete")),
):
    role = await db.get(Role, role_id)
    if not role:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "역할을 찾을 수 없습니다")
    if role.is_system:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "시스템 역할은 삭제할 수 없습니다")
    await db.delete(role)
    await db.commit()


@router.put("/roles/{role_id}/functions", response_model=RoleResponse)
async def set_role_functions(
    role_id: str,
    entries: list[RoleFunctionEntry],
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("roles", "update")),
):
    role = await db.get(Role, role_id)
    if not role:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "역할을 찾을 수 없습니다")

    # 기존 매핑 삭제 후 새로 교체
    old_rfs = await db.scalars(select(RoleFunction).where(RoleFunction.role_id == role_id))
    for rf in old_rfs:
        await db.delete(rf)
    await db.flush()

    for entry in entries:
        fn = await db.get(Function, entry.function_id)
        if not fn:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"기능 {entry.function_id}를 찾을 수 없습니다",
            )
        db.add(
            RoleFunction(
                role_id=role_id,
                function_id=entry.function_id,
                can_create=entry.can_create,
                can_read=entry.can_read,
                can_update=entry.can_update,
                can_delete=entry.can_delete,
            )
        )

    await db.commit()
    await db.refresh(role)

    rfs = (
        await db.execute(
            select(RoleFunction, Function)
            .join(RoleFunction.function)
            .where(RoleFunction.role_id == role.id)
        )
    ).all()
    mappings = []
    for rf, fn in rfs:
        mappings.append(
            {
                "function_id": rf.function_id,
                "function_name": fn.name,
                "can_create": rf.can_create,
                "can_read": rf.can_read,
                "can_update": rf.can_update,
                "can_delete": rf.can_delete,
            }
        )
    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        created_at=role.created_at,
        updated_at=role.updated_at,
        functions=mappings,
    )
