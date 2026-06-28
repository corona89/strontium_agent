"""LLM 위키 서비스 — DB(검색 인덱스)와 파일시스템(진실의 원천) 동기화.

카테고리는 structure.md에만 존재(메타데이터). 페이지는 파일 + DB 인덱스 + structure.md 항목.
모든 쓰기는 두 곳을 함께 갱신한다.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import core.wiki_store as store
from database.models import WikiPage

logger = logging.getLogger(__name__)

_SUMMARY_LEN = 300


def _make_summary(content: str) -> str:
    if not content:
        return ""
    text = content.strip()
    # 첫 문단 우선, 없으면 앞부분
    first_para = text.split("\n\n", 1)[0]
    s = first_para.replace("\n", " ").strip()
    if len(s) > _SUMMARY_LEN:
        s = s[:_SUMMARY_LEN].rstrip() + "…"
    return s


def _category_slug_map(wiki_id: str) -> dict[str, str]:
    """category_id -> slug 매핑을 structure.md에서 읽는다."""
    st = store.read_structure(wiki_id)
    return {c["id"]: c.get("slug") or "_uncategorized" for c in st["categories"]}


def _page_slugs_in_category(wiki_id: str, category_id: str | None) -> set[str]:
    st = store.read_structure(wiki_id)
    cat_match = category_id  # pages with this category
    return {
        p["slug"]
        for p in st["pages"]
        if (p.get("category_id") or None) == (cat_match or None)
    }


async def create_page(
    db: AsyncSession,
    wiki_id: str,
    *,
    category_id: str | None,
    title: str,
    content: str,
    source_type: str = "manual",
    source_ref: str | None = None,
) -> WikiPage:
    """파일 + DB + structure.md에 페이지를 생성한다."""
    slug_map = _category_slug_map(wiki_id)
    cat_slug = slug_map.get(category_id) if category_id else None
    existing = _page_slugs_in_category(wiki_id, category_id)
    slug = store.unique_slug(existing, store.slugify(title) or "page")

    rel_path = await store.write_page_content(wiki_id, cat_slug, slug, content)
    # file_path: 카테고리/페이지.md 형태의 상대 경로
    file_path = f"{cat_slug or '_uncategorized'}/{slug}.md"

    page = WikiPage(
        wiki_id=wiki_id,
        category_id=category_id,
        slug=slug,
        title=title,
        summary=_make_summary(content),
        content=content,
        source_type=source_type,
        source_ref=source_ref,
        file_path=file_path,
    )
    db.add(page)
    await db.flush()

    # structure.md 갱신
    st = store.read_structure(wiki_id)
    st["pages"].append(
        {
            "id": page.id,
            "category_id": category_id,
            "slug": slug,
            "title": title,
            "source_type": source_type,
        }
    )
    store.write_structure(wiki_id, st)
    return page


async def update_page_content(
    db: AsyncSession, page: WikiPage, *, title: str | None, content: str
) -> WikiPage:
    """직접 수정: 파일 + DB 캐시 + structure.md(title 변경 시)."""
    wiki_id = page.wiki_id
    slug_map = _category_slug_map(wiki_id)
    cat_slug = slug_map.get(page.category_id) if page.category_id else None

    await store.write_page_content(wiki_id, cat_slug, page.slug, content)
    page.content = content
    page.summary = _make_summary(content)
    if title and title != page.title:
        page.title = title
        st = store.read_structure(wiki_id)
        for p in st["pages"]:
            if p["id"] == page.id:
                p["title"] = title
                break
        store.write_structure(wiki_id, st)
    await db.flush()
    return page


async def delete_page(db: AsyncSession, page: WikiPage) -> None:
    wiki_id = page.wiki_id
    slug_map = _category_slug_map(wiki_id)
    cat_slug = slug_map.get(page.category_id) if page.category_id else None
    store.delete_page_file(wiki_id, cat_slug, page.slug)

    st = store.read_structure(wiki_id)
    st["pages"] = [p for p in st["pages"] if p["id"] != page.id]
    store.write_structure(wiki_id, st)

    await db.delete(page)
    await db.flush()


def create_category(wiki_id: str, name: str) -> dict:
    st = store.read_structure(wiki_id)
    import uuid

    existing = {c.get("slug") for c in st["categories"]}
    slug = store.unique_slug(existing, store.slugify(name) or "category")
    cat = {"id": str(uuid.uuid4()), "name": name, "slug": slug}
    st["categories"].append(cat)
    store.write_structure(wiki_id, st)
    return cat


def find_or_create_category(wiki_id: str, name: str) -> str:
    """이름이 일치하는 카테고리가 있으면 그 id를, 없으면 새로 만들어 id를 반환한다.

    자동 분류(LLM) 및 웹 폴백 자동 저장 등에서 이름 기반 find-or-create에 사용.
    """
    st = store.read_structure(wiki_id)
    for c in st["categories"]:
        if c["name"] == name:
            return c["id"]
    cat = create_category(wiki_id, name)
    return cat["id"]


def update_category(wiki_id: str, category_id: str, name: str) -> dict | None:
    """카테고리 이름 변경. slug/id는 유지(파일시스템 경로 보존)."""
    st = store.read_structure(wiki_id)
    for c in st["categories"]:
        if c["id"] == category_id:
            c["name"] = name
            store.write_structure(wiki_id, st)
            return c
    return None


def delete_category(wiki_id: str, category_id: str) -> bool:
    """카테고리 삭제: 디렉토리 + 하위 페이지(파일) 제거. DB 행은 호출자가 처리."""
    st = store.read_structure(wiki_id)
    cat = next((c for c in st["categories"] if c["id"] == category_id), None)
    if not cat:
        return False
    cat_slug = cat.get("slug") or "_uncategorized"
    # 디렉토리 통째로 삭제
    d = store.category_dir(wiki_id, cat_slug)
    if d.exists():
        import shutil

        shutil.rmtree(d, ignore_errors=True)
    # structure.md에서 카테고리 + 소속 페이지 제거
    st["categories"] = [c for c in st["categories"] if c["id"] != category_id]
    st["pages"] = [p for p in st["pages"] if p.get("category_id") != category_id]
    store.write_structure(wiki_id, st)
    return True


async def resync_pages_db(db: AsyncSession, wiki_id: str) -> None:
    """structure.md를 진실의 원천으로 DB 페이지 인덱스를 재구축한다(시작/복구용).

    파일이 존재하는 페이지는 content/summary를 다시 캐시하고, structure.md에 없는
    DB 행은 삭제한다. 누락된 파일을 가진 행도 정리한다.
    """
    st = store.read_structure(wiki_id)
    manifest_page_ids = {p["id"] for p in st["pages"]}
    slug_map = _category_slug_map(wiki_id)

    rows = await db.scalars(select(WikiPage).where(WikiPage.wiki_id == wiki_id))
    db_pages = {p.id: p for p in rows}

    # 매니페스트 기준 동기화
    for entry in st["pages"]:
        pid = entry["id"]
        cat_slug = slug_map.get(entry.get("category_id")) if entry.get("category_id") else None
        content = await store.read_page_content(wiki_id, cat_slug, entry["slug"])
        row = db_pages.get(pid)
        if row:
            row.title = entry["title"]
            row.category_id = entry.get("category_id")
            row.slug = entry["slug"]
            row.content = content
            row.summary = _make_summary(content)
            row.source_type = entry.get("source_type") or row.source_type
            row.file_path = f"{cat_slug or '_uncategorized'}/{entry['slug']}.md"
            db_pages.pop(pid)
        else:
            db.add(
                WikiPage(
                    id=pid,
                    wiki_id=wiki_id,
                    category_id=entry.get("category_id"),
                    slug=entry["slug"],
                    title=entry["title"],
                    summary=_make_summary(content),
                    content=content,
                    source_type=entry.get("source_type", "manual"),
                    file_path=f"{cat_slug or '_uncategorized'}/{entry['slug']}.md",
                )
            )

    # 매니페스트에 없는 남은 DB 행 삭제
    for orphan in db_pages.values():
        await db.delete(orphan)
    await db.flush()
