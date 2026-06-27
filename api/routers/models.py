from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.audit import log_action
from core.config import settings
from core.deps import require_permission
from database.connection import get_db
from database.models import Account, LLMProvider
from schemas.models import ProviderCreate, ProviderResponse, ProviderUpdate

router = APIRouter(prefix="/models", tags=["models"])

_PROVIDER_KEY_ATTR = {
    "ollama_cloud": "OLLAMA_API_KEY",
    "opencode_zen": "ZEN_AI_API_KEY",
}


def _key_configured(provider_type: str) -> bool:
    attr = _PROVIDER_KEY_ATTR.get(provider_type)
    if not attr:
        return False
    return bool(getattr(settings, attr, None))


def _to_response(provider: LLMProvider) -> ProviderResponse:
    return ProviderResponse(
        id=provider.id,
        provider_type=provider.provider_type,
        display_name=provider.display_name,
        base_url=provider.base_url,
        models=provider.models or [],
        is_active=provider.is_active,
        api_key_configured=_key_configured(provider.provider_type),
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
