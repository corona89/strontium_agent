from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.audit import log_action
from core import crypto
from core.deps import require_permission
from core.llm import resolve_api_key
from database.connection import get_db
from database.models import Account, LLMProvider
from schemas.models import ProviderCreate, ProviderResponse, ProviderUpdate

router = APIRouter(prefix="/models", tags=["models"])


def _to_response(provider: LLMProvider) -> ProviderResponse:
    # 복호화해 마스킹된 값을 만든다. 복호화 실패(키 회전 등) 시 masked=None.
    plaintext = resolve_api_key(provider)
    return ProviderResponse(
        id=provider.id,
        provider_type=provider.provider_type,
        display_name=provider.display_name,
        base_url=provider.base_url,
        models=provider.models or [],
        is_active=provider.is_active,
        api_key_configured=bool(provider.api_key_encrypted),
        api_key_masked=crypto.mask(plaintext),
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )


@router.get("/providers", response_model=list[ProviderResponse])
async def list_providers(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("models", "read")),
):
    rows = await db.scalars(select(LLMProvider).order_by(LLMProvider.created_at))
    return [_to_response(p) for p in rows]


@router.post("/providers", response_model=ProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_provider(
    body: ProviderCreate,
    db: AsyncSession = Depends(get_db),
    admin: Account = Depends(require_permission("models", "create")),
):
    provider = LLMProvider(
        provider_type=body.provider_type,
        display_name=body.display_name,
        base_url=body.base_url,
        api_key_encrypted=crypto.encrypt(body.api_key),
        models=body.models,
        is_active=body.is_active,
    )
    db.add(provider)
    await db.flush()
    await log_action(
        db,
        actor_id=admin.id,
        target_id=provider.id,
        action="models.create_provider",
        # 평문 키는 detail에 절대 기록하지 않는다(NFR-S09/S11)
        detail={"provider_type": provider.provider_type, "display_name": provider.display_name},
    )
    await db.commit()
    await db.refresh(provider)
    return _to_response(provider)


@router.patch("/providers/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: str,
    body: ProviderUpdate,
    db: AsyncSession = Depends(get_db),
    admin: Account = Depends(require_permission("models", "update")),
):
    provider = await db.get(LLMProvider, provider_id)
    if not provider:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "제공자를 찾을 수 없습니다")

    detail: dict = {"id": provider_id}
    if body.display_name is not None:
        detail["display_name_after"] = body.display_name
        provider.display_name = body.display_name
    if body.base_url is not None:
        provider.base_url = body.base_url
        detail["base_url_changed"] = True
    if body.models is not None:
        provider.models = body.models
        detail["models_count"] = len(body.models)
    if body.is_active is not None:
        provider.is_active = body.is_active
        detail["is_active"] = body.is_active
    if body.api_key is not None:
        provider.api_key_encrypted = crypto.encrypt(body.api_key)
        detail["api_key_rotated"] = True  # 평문이 아닌 회전 사실만 기록

    await log_action(
        db,
        actor_id=admin.id,
        target_id=provider.id,
        action="models.update_provider",
        detail=detail,
    )
    await db.commit()
    await db.refresh(provider)
    return _to_response(provider)


@router.delete("/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
    admin: Account = Depends(require_permission("models", "delete")),
):
    provider = await db.get(LLMProvider, provider_id)
    if not provider:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "제공자를 찾을 수 없습니다")
    display_name = provider.display_name
    await db.delete(provider)
    await log_action(
        db,
        actor_id=admin.id,
        target_id=provider_id,
        action="models.delete_provider",
        detail={"display_name": display_name},
    )
    await db.commit()
