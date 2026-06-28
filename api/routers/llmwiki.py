"""LLM 위키 라우터.

모든 엔드포인트는 `require_permission("llmwiki", ...)` + 소유자 검증을 적용한다.
파일시스템이 진실의 원천이고 DB는 검색 인덱스. 첨부파일은 권한 보호 FileResponse로 서빙.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

import core.wiki_store as store
from core.config import settings
from core.deps import require_permission
from core.llm import (
    chat_complete,
    is_configured,
    list_enabled_models,
)
from core.search import bm25_search
from core.websearch import format_search_results, web_search
from core.wiki_decompose import decompose_document
from core.wiki_ingest import ingest
from core.wiki_service import (
    create_category,
    create_page,
    delete_category,
    delete_page,
    resync_pages_db,
    update_category,
    update_page_content,
)
from database.connection import AsyncSessionLocal, get_db
from database.models import Account, LLMProvider, Wiki, WikiChatMessage, WikiPage
from schemas.llmwiki import (
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    ChatRequest,
    IngestResult,
    ModelsForSelectionResponse,
    PageCreate,
    PageDetail,
    PageSummary,
    PageUpdate,
    ProviderForSelection,
    WikiCreate,
    WikiDetail,
    WikiTree,
    WikiUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llmwiki", tags=["llm-wiki"])

_AGENT_SYSTEM = (
    "너는 개인 지식 위키의 RAG 어시스턴트다. 제공된 위키 출처를 우선 근거로 사용해 사용자 질문에 답하라.\n"
    "출처에 명확히 없는 내용은 추측하지 말라. 대신 웹 검색 도구를 사용해 추가 정보를 수집할 수 있다.\n\n"
    "[웹 검색 도구 — ReAct]\n"
    "- 위키 출처만으로 답하기 어렵다고 판단되면, 다른 설명 없이 정확히 아래 한 줄만 출력해 검색을 요청하라:\n"
    "    SEARCH: <검색할 키워드>\n"
    "- 시스템이 검색을 수행해 결과를 알려준다. 결과를 받은 뒤에는 그 정보로 답하거나, 더 필요하면 다른 키워드로 다시 SEARCH: 를 출력할 수 있다(최대 5회).\n"
    "- 충분한 정보가 모이면 한국어 마크다운으로 최종 답을 작성하고, 중요한 사실에 출처 번호([1], [2] ...)를 달라. 최종 답변에는 SEARCH: 줄을 포함시키지 말라.\n"
    "- 위키 출처로 충분히 답할 수 있으면 도구 없이 바로 답하라."
)
# ReAct 검색 요청 마커(딥 리서치 에이전트와 동일 컨벤션).
_TOOL_RE = re.compile(r"SEARCH:\s*(.+?)(?:\n|$)")
_MAX_SEARCHES = 5

# 백그라운드 저장 태스크 참조(GC 방지). 완료 시 콜백으로 제거된다.
_bg_tasks: set[asyncio.Task] = set()


def _chunk_text(text: str) -> list[str]:
    """최종 답을 스트리밍처럼 전달하기 위해 라인 단위로 쪼갠다."""
    if not text:
        return []
    lines = text.splitlines(keepends=True)
    return lines if lines else [text]


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _get_owned_wiki(db: AsyncSession, wiki_id: str, account: Account) -> Wiki:
    wiki = await db.get(Wiki, wiki_id)
    if not wiki:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "위키를 찾을 수 없습니다")
    if wiki.owner_account_id != account.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "접근할 수 없는 위키입니다")
    return wiki


async def _get_owned_page(
    db: AsyncSession, wiki_id: str, page_id: str, account: Account
) -> WikiPage:
    await _get_owned_wiki(db, wiki_id, account)
    page = await db.get(WikiPage, page_id)
    if not page or page.wiki_id != wiki_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "페이지를 찾을 수 없습니다")
    return page


async def _build_tree(db: AsyncSession, wiki_id: str) -> WikiTree:
    st = store.read_structure(wiki_id)
    categories = [
        CategoryOut(id=c["id"], name=c["name"], slug=c.get("slug") or "")
        for c in st["categories"]
    ]
    rows = await db.scalars(select(WikiPage).where(WikiPage.wiki_id == wiki_id))
    page_rows = {p.id: p for p in rows}
    pages: list[PageSummary] = []
    # 매니페스트 순서 따르되, DB 행에서 메타데이터/타임스탬프 가져오기
    for entry in st["pages"]:
        row = page_rows.get(entry["id"])
        pages.append(
            PageSummary(
                id=entry["id"],
                category_id=entry.get("category_id"),
                slug=entry["slug"],
                title=entry["title"],
                summary=row.summary if row else None,
                source_type=entry.get("source_type", "manual"),
                source_ref=row.source_ref if row else None,
                created_at=row.created_at if row else _epoch(),
                updated_at=row.updated_at if row else _epoch(),
            )
        )
    # 매니페스트에 없는 DB 행(DB에만 있는)도 포함
    manifest_ids = {p["id"] for p in st["pages"]}
    for pid, row in page_rows.items():
        if pid not in manifest_ids:
            pages.append(
                PageSummary(
                    id=row.id, category_id=row.category_id, slug=row.slug,
                    title=row.title, summary=row.summary, source_type=row.source_type,
                    source_ref=row.source_ref, created_at=row.created_at, updated_at=row.updated_at,
                )
            )
    return WikiTree(categories=categories, pages=pages)


def _epoch():
    from datetime import datetime

    return datetime.now(timezone.utc)


async def _wiki_detail(db: AsyncSession, w: Wiki) -> WikiDetail:
    return WikiDetail(
        id=w.id,
        title=w.title,
        provider_id=w.provider_id,
        model=w.model,
        created_at=w.created_at,
        updated_at=w.updated_at,
        tree=await _build_tree(db, w.id),
    )


# ── 모델 선택 ────────────────────────────────────────────────────────────────


@router.get("/models", response_model=ModelsForSelectionResponse)
async def list_models_for_selection(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("llmwiki", "read")),
):
    """위키용 모델 선택 목록. 활성 + 키 설정된 제공자만."""
    providers = await db.scalars(
        select(LLMProvider)
        .where(LLMProvider.is_active.is_(True))
        .order_by(LLMProvider.created_at)
    )
    result = []
    for p in providers:
        if not is_configured(p.provider_type):
            continue
        registered = list(p.models or [])
        enabled = await list_enabled_models(p.provider_type, p.base_url)
        usable = [m for m in registered if m in enabled] if enabled is not None else registered
        result.append(
            ProviderForSelection(
                id=p.id,
                display_name=p.display_name,
                provider_type=p.provider_type,
                models=usable,
            )
        )
    return ModelsForSelectionResponse(providers=result)


# ── 위키 CRUD ────────────────────────────────────────────────────────────────


@router.get("/wikis")
async def list_wikis(
    db: AsyncSession = Depends(get_db),
    account: Account = Depends(require_permission("llmwiki", "read")),
):
    rows = await db.scalars(
        select(Wiki)
        .where(Wiki.owner_account_id == account.id)
        .order_by(Wiki.created_at.desc())
    )
    return [
        {
            "id": w.id,
            "title": w.title,
            "provider_id": w.provider_id,
            "model": w.model,
            "created_at": w.created_at,
            "updated_at": w.updated_at,
        }
        for w in rows
    ]


@router.post("/wikis", response_model=WikiDetail, status_code=status.HTTP_201_CREATED)
async def create_wiki(
    body: WikiCreate,
    db: AsyncSession = Depends(get_db),
    account: Account = Depends(require_permission("llmwiki", "create")),
):
    provider = None
    if body.provider_id:
        provider = await db.get(LLMProvider, body.provider_id)
        if not provider or not provider.is_active:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "활성 제공자를 찾을 수 없습니다")
        if not is_configured(provider.provider_type):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"{provider.provider_type} API 키가 설정되지 않았습니다",
            )
        if body.model and body.model not in (provider.models or []):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "선택한 모델이 제공자에 없습니다")

    wiki = Wiki(
        owner_account_id=account.id,
        title=body.title,
        provider_id=body.provider_id,
        model=body.model,
    )
    db.add(wiki)
    await db.commit()
    await db.refresh(wiki)
    store.init_wiki_dir(wiki.id)
    return await _wiki_detail(db, wiki)


@router.get("/wikis/{wiki_id}", response_model=WikiDetail)
async def get_wiki(
    wiki_id: str,
    db: AsyncSession = Depends(get_db),
    account: Account = Depends(require_permission("llmwiki", "read")),
):
    wiki = await _get_owned_wiki(db, wiki_id, account)
    # 조회 시 DB 인덱스를 파일시스템과 동기화(외부 편집/복구 대응)
    await resync_pages_db(db, wiki_id)
    await db.commit()
    return await _wiki_detail(db, wiki)


@router.patch("/wikis/{wiki_id}", response_model=WikiDetail)
async def update_wiki(
    wiki_id: str,
    body: WikiUpdate,
    db: AsyncSession = Depends(get_db),
    account: Account = Depends(require_permission("llmwiki", "update")),
):
    wiki = await _get_owned_wiki(db, wiki_id, account)
    wiki.title = body.title
    await db.commit()
    await db.refresh(wiki)
    return await _wiki_detail(db, wiki)


@router.delete("/wikis/{wiki_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wiki(
    wiki_id: str,
    db: AsyncSession = Depends(get_db),
    account: Account = Depends(require_permission("llmwiki", "delete")),
):
    wiki = await _get_owned_wiki(db, wiki_id, account)
    store.delete_wiki_dir(wiki_id)
    await db.delete(wiki)
    await db.commit()


# ── 카테고리 CRUD ────────────────────────────────────────────────────────────


@router.post("/wikis/{wiki_id}/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_wiki_category(
    wiki_id: str,
    body: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    account: Account = Depends(require_permission("llmwiki", "create")),
):
    await _get_owned_wiki(db, wiki_id, account)
    cat = create_category(wiki_id, body.name)
    return CategoryOut(id=cat["id"], name=cat["name"], slug=cat["slug"])


@router.patch("/wikis/{wiki_id}/categories/{category_id}", response_model=CategoryOut)
async def update_wiki_category(
    wiki_id: str,
    category_id: str,
    body: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    account: Account = Depends(require_permission("llmwiki", "update")),
):
    await _get_owned_wiki(db, wiki_id, account)
    cat = update_category(wiki_id, category_id, body.name)
    if not cat:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "카테고리를 찾을 수 없습니다")
    return CategoryOut(id=cat["id"], name=cat["name"], slug=cat["slug"])


@router.delete("/wikis/{wiki_id}/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wiki_category(
    wiki_id: str,
    category_id: str,
    db: AsyncSession = Depends(get_db),
    account: Account = Depends(require_permission("llmwiki", "delete")),
):
    await _get_owned_wiki(db, wiki_id, account)
    removed = delete_category(wiki_id, category_id)
    if not removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "카테고리를 찾을 수 없습니다")
    # 소속 페이지 DB 행 삭제
    pages = await db.scalars(
        select(WikiPage).where(
            WikiPage.wiki_id == wiki_id, WikiPage.category_id == category_id
        )
    )
    for p in pages:
        await db.delete(p)
    await db.commit()


# ── 페이지 CRUD ──────────────────────────────────────────────────────────────


@router.post("/wikis/{wiki_id}/pages", response_model=PageDetail, status_code=status.HTTP_201_CREATED)
async def create_wiki_page(
    wiki_id: str,
    body: PageCreate,
    db: AsyncSession = Depends(get_db),
    account: Account = Depends(require_permission("llmwiki", "create")),
):
    await _get_owned_wiki(db, wiki_id, account)
    page = await create_page(
        db, wiki_id,
        category_id=body.category_id,
        title=body.title,
        content=body.content,
        source_type="manual",
    )
    await db.commit()
    await db.refresh(page)
    return _page_detail(db_wiki=wiki_id, page=page)


def _page_detail(db_wiki: str, page: WikiPage) -> PageDetail:
    slug_map = {c["id"]: c.get("slug") for c in store.read_structure(page.wiki_id)["categories"]}
    cat_slug = slug_map.get(page.category_id) if page.category_id else None
    return PageDetail(
        id=page.id,
        category_id=page.category_id,
        slug=page.slug,
        title=page.title,
        summary=page.summary,
        source_type=page.source_type,
        source_ref=page.source_ref,
        created_at=page.created_at,
        updated_at=page.updated_at,
        content=page.content or "",
        category_slug=cat_slug,
    )


@router.get("/wikis/{wiki_id}/pages/{page_id}", response_model=PageDetail)
async def get_wiki_page(
    wiki_id: str,
    page_id: str,
    db: AsyncSession = Depends(get_db),
    account: Account = Depends(require_permission("llmwiki", "read")),
):
    page = await _get_owned_page(db, wiki_id, page_id, account)
    # 파일에서 최신 본문 로드(직접 편집 반영)
    slug_map = {
        c["id"]: c.get("slug")
        for c in store.read_structure(wiki_id)["categories"]
    }
    cat_slug = slug_map.get(page.category_id) if page.category_id else None
    content = await store.read_page_content(wiki_id, cat_slug, page.slug)
    page.content = content or page.content or ""
    return _page_detail(db_wiki=wiki_id, page=page)


@router.put("/wikis/{wiki_id}/pages/{page_id}", response_model=PageDetail)
async def update_wiki_page(
    wiki_id: str,
    page_id: str,
    body: PageUpdate,
    db: AsyncSession = Depends(get_db),
    account: Account = Depends(require_permission("llmwiki", "update")),
):
    page = await _get_owned_page(db, wiki_id, page_id, account)
    await update_page_content(db, page, title=body.title, content=body.content)
    await db.commit()
    await db.refresh(page)
    return _page_detail(db_wiki=wiki_id, page=page)


@router.delete("/wikis/{wiki_id}/pages/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wiki_page(
    wiki_id: str,
    page_id: str,
    db: AsyncSession = Depends(get_db),
    account: Account = Depends(require_permission("llmwiki", "delete")),
):
    page = await _get_owned_page(db, wiki_id, page_id, account)
    await delete_page(db, page)
    await db.commit()


# ── 주입(multipart) ─────────────────────────────────────────────────────────


@router.post("/wikis/{wiki_id}/ingest", response_model=IngestResult)
async def ingest_into_wiki(
    wiki_id: str,
    db: AsyncSession = Depends(get_db),
    account: Account = Depends(require_permission("llmwiki", "create")),
    category_id: str | None = Form(default=None),
    auto_categorize: bool = Form(default=False),
    deepresearch_session_id: str | None = Form(default=None),
    youtube_url: str | None = Form(default=None),
    files: list[UploadFile] = File(default=[]),
):
    wiki = await _get_owned_wiki(db, wiki_id, account)

    # 파일 크기 검증
    uploaded = []
    for f in files:
        data = await f.read()
        if len(data) > settings.UPLOAD_MAX_BYTES:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                f"{f.filename}이(가) 업로드 한도를 초과합니다",
            )
        f.file.seek(0)
        uploaded.append(f)

    if not uploaded and not deepresearch_session_id and not youtube_url:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "주입할 소스가 없습니다 (파일·딥 리서치 세션·YouTube URL 중 하나 이상)",
        )

    # 딥 리서치 세션 소유권 검증
    if deepresearch_session_id:
        from database.models import DeepResearchSession

        sess = await db.get(DeepResearchSession, deepresearch_session_id)
        if not sess or sess.account_id != account.id:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "접근할 수 없는 딥 리서치 세션입니다"
            )

    provider = None
    if wiki.provider_id:
        provider = await db.get(LLMProvider, wiki.provider_id)
    provider_type = provider.provider_type if provider else None
    base_url = provider.base_url if provider else None

    # 자동 분류에는 위키에 LLM 제공자/모델이 설정되어야 한다.
    if auto_categorize and not category_id:
        if not provider or not wiki.model:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "자동 분류에는 위키에 LLM이 설정되어야 합니다",
            )

    try:
        created, created_categories = await ingest(
            db, wiki_id,
            category_id=category_id,
            files=uploaded,
            deepresearch_session_id=deepresearch_session_id,
            youtube_url=youtube_url,
            provider_type=provider_type,
            base_url=base_url,
            model=wiki.model,
            auto_categorize=auto_categorize,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except RuntimeError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    await db.commit()
    for p in created:
        await db.refresh(p)
    is_auto = bool(auto_categorize and not category_id)
    return IngestResult(
        created_pages=[
            PageSummary(
                id=p.id, category_id=p.category_id, slug=p.slug, title=p.title,
                summary=p.summary, source_type=p.source_type, source_ref=p.source_ref,
                created_at=p.created_at, updated_at=p.updated_at,
            )
            for p in created
        ],
        auto_categorized=is_auto,
        created_categories=[
            CategoryOut(id=c["id"], name=c["name"], slug=c.get("slug") or "")
            for c in created_categories
        ],
    )


# ── 첨부파일 서빙(권한 보호) ─────────────────────────────────────────────────


@router.get("/wikis/{wiki_id}/attachments/{name}")
async def get_attachment(
    wiki_id: str,
    name: str,
    db: AsyncSession = Depends(get_db),
    account: Account = Depends(require_permission("llmwiki", "read")),
):
    await _get_owned_wiki(db, wiki_id, account)
    try:
        p = store.attachment_path(wiki_id, name)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "잘못된 파일명")
    if not p.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "파일을 찾을 수 없습니다")
    return FileResponse(str(p))


# ── 채팅 이력 ────────────────────────────────────────────────────────────────


@router.get("/wikis/{wiki_id}/messages")
async def list_messages(
    wiki_id: str,
    db: AsyncSession = Depends(get_db),
    account: Account = Depends(require_permission("llmwiki", "read")),
):
    await _get_owned_wiki(db, wiki_id, account)
    rows = await db.scalars(
        select(WikiChatMessage)
        .where(WikiChatMessage.wiki_id == wiki_id)
        .order_by(WikiChatMessage.created_at)
    )
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "sources": m.sources,
            "created_at": m.created_at,
        }
        for m in rows
    ]


@router.delete("/wikis/{wiki_id}/messages", status_code=status.HTTP_204_NO_CONTENT)
async def clear_chat_messages(
    wiki_id: str,
    db: AsyncSession = Depends(get_db),
    account: Account = Depends(require_permission("llmwiki", "delete")),
):
    """위키의 채팅 기록을 전체 삭제한다(채팅 초기화). 페이지/카테고리는 영향 없음."""
    await _get_owned_wiki(db, wiki_id, account)
    await db.execute(delete(WikiChatMessage).where(WikiChatMessage.wiki_id == wiki_id))
    await db.commit()


# ── RAG 채팅(SSE) ────────────────────────────────────────────────────────────


async def _collect_pages(db: AsyncSession, wiki_id: str) -> list[dict]:
    rows = await db.scalars(
        select(WikiPage).where(WikiPage.wiki_id == wiki_id)
    )
    return [
        {"id": p.id, "title": p.title, "content": p.content or "", "slug": p.slug,
         "category_id": p.category_id}
        for p in rows
    ]


async def _background_save_to_wiki(
    wiki_id: str,
    question: str,
    answer: str,
    provider_type: str,
    base_url: str | None,
    model: str,
) -> None:
    """웹 보강 답변을 위키에 주제별로 분해해 백그라운드 저장한다(fire-and-forget).

    채팅 응답 지연을 만들지 않도록 스트림 종료 후 별도 태스크로 실행된다.
    요청 스코프 세션이 아닌 자체 세션(AsyncSessionLocal)을 사용하며,
    SQLite 동시 쓰기 잠금 시 짧게 재시도한다. 예외는 로깅만 한다.
    """
    try:
        for attempt in range(3):
            try:
                async with AsyncSessionLocal() as bg_db:
                    created_categories: list[dict] = []
                    sections = await decompose_document(
                        provider_type, base_url, model, wiki_id,
                        title=question, content=answer,
                        created_categories=created_categories,
                    )
                    for sec in sections:
                        await create_page(
                            bg_db, wiki_id,
                            category_id=sec.get("category_id"),
                            title=sec.get("title") or (question[:60] or "웹 검색 결과"),
                            content=sec.get("content") or answer,
                            source_type="manual",
                        )
                    await bg_db.commit()
                logger.info(
                    "background wiki save done: %d sections, %d new categories",
                    len(sections), len(created_categories),
                )
                return
            except OperationalError as e:
                # SQLite "database is locked" — 잠시 대기 후 재시도
                logger.warning("background save DB lock (attempt %d): %s", attempt + 1, e)
                await asyncio.sleep(0.4 * (attempt + 1))
    except Exception:
        logger.exception("background wiki save failed")


def _spawn_background_save(
    wiki_id: str, question: str, answer: str,
    provider_type: str, base_url: str | None, model: str,
) -> None:
    """백그라운드 저장 태스크를 예약하고 GC 방지용 참조를 보관한다."""
    task = asyncio.create_task(
        _background_save_to_wiki(wiki_id, question, answer, provider_type, base_url, model)
    )
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


@router.post("/wikis/{wiki_id}/chat")
async def chat(
    wiki_id: str,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    account: Account = Depends(require_permission("llmwiki", "create")),
):
    wiki = await _get_owned_wiki(db, wiki_id, account)
    provider = await db.get(LLMProvider, wiki.provider_id) if wiki.provider_id else None
    if not provider or not wiki.model:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "위키에 LLM 제공자/모델이 설정되지 않았습니다",
        )

    async def event_stream():
        # 1) 위키 BM25 검색 — 히트가 있으면 컨텍스트에 포함(임계치 판단은 LLM이 수행).
        pages = await _collect_pages(db, wiki_id)
        hits = bm25_search(body.question, pages, top_k=5)
        wiki_sources: list[dict] = []
        context_blocks: list[str] = []
        if hits:
            id_to_page = {p["id"]: p for p in pages}
            for i, (pid, score) in enumerate(hits, 1):
                p = id_to_page.get(pid)
                if not p:
                    continue
                wiki_sources.append({"type": "wiki", "title": p["title"], "ref": pid})
                context_blocks.append(
                    f"[{i}] (위키 페이지: {p['title']})\n{p['content']}"
                )
        wiki_context = "\n\n".join(context_blocks) if context_blocks else "(위키에 관련 페이지가 없습니다)"

        # 사용자 메시지 영속화
        db.add(WikiChatMessage(wiki_id=wiki_id, role="user", content=body.question))
        await db.commit()

        # 2) ReAct 멀티턴 루프 — LLM이 SEARCH: 마커로 웹 검색을 요청하면 Tavily 실행 후 결과 주입.
        messages: list[dict] = [
            {"role": "system", "content": _AGENT_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"[위키 출처]\n{wiki_context}\n\n[질문] {body.question}\n\n"
                    "위키 출처로 답할 수 있으면 바로 답하라. 부족하면 SEARCH: <키워드> 로 웹 검색을 요청하라."
                ),
            },
        ]
        web_sources: list[dict] = []
        full_answer = ""
        try:
            searches = 0
            while True:
                raw = await chat_complete(
                    provider.provider_type, provider.base_url, wiki.model, messages
                )
                m = _TOOL_RE.search(raw)
                if m and searches < _MAX_SEARCHES:
                    query = m.group(1).strip()
                    yield _sse("searching", {"query": query, "iteration": searches + 1})
                    results = await web_search(query, max_results=5)
                    if results:
                        for r in results:
                            web_sources.append(
                                {"type": "web", "title": r.get("title") or "웹 문서",
                                 "ref": r.get("url") or ""}
                            )
                    messages.append({"role": "assistant", "content": raw})
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"검색 결과 for '{query}':\n{format_search_results(results)}\n\n"
                                "이 결과를 활용해 답을 계속 작성하라. 여전히 부족하면 다른 키워드로 "
                                "SEARCH: 를 다시 요청할 수 있고, 충분하면 최종 답을 한국어 마크다운으로 작성하라."
                            ),
                        }
                    )
                    searches += 1
                    continue
                # 검색 마커 없음(또는 상한 도달) → 최종 답
                full_answer = raw
                break

            # 상한 도달 후에도 마지막 응답에 SEARCH: 가 남아있으면 수집 정보로 강제 최종 답.
            if _TOOL_RE.search(full_answer) or not full_answer.strip():
                messages.append(
                    {
                        "role": "user",
                        "content": "더 이상 검색하지 말고 지금까지 수집한 정보로 최종 답을 한국어 마크다운으로 작성하라.",
                    }
                )
                full_answer = await chat_complete(
                    provider.provider_type, provider.base_url, wiki.model, messages
                )
        except RuntimeError as e:
            yield _sse("error", {"message": str(e)})
            return

        used_web = bool(web_sources)
        sources = wiki_sources + web_sources

        # 3) 출처 → 최종 답 라인 청크 전송
        yield _sse("sources", {"sources": sources, "is_web_fallback": used_web})
        for chunk in _chunk_text(full_answer):
            yield _sse("delta", {"delta": chunk})

        # 4) 어시스턴트 메시지 영속화
        db.add(
            WikiChatMessage(
                wiki_id=wiki_id, role="assistant", content=full_answer, sources=sources
            )
        )
        await db.commit()

        # 5) 웹 보강 답변이면 백그라운드에서 위키에 분해 저장(FR-K07).
        #    채팅 응답 지연을 만들지 않도록 태스크를 예약만 하고 즉시 done을 보낸다.
        saving_in_background = False
        if used_web and full_answer.strip():
            _spawn_background_save(
                wiki_id, body.question, full_answer,
                provider.provider_type, provider.base_url, wiki.model,
            )
            saving_in_background = True

        yield _sse(
            "done",
            {"is_web_fallback": used_web, "saving_in_background": saving_in_background},
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
