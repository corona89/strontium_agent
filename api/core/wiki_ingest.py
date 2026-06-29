"""LLM 위키 주입 파이프라인.

각 소스(MD·Deepresearch·PDF·이미지·YouTube)를 마크다운 페이지로 변환해 위키에 추가한다.
원본(pdf/이미지)은 attachments/에 보관하고, 페이지는 core/wiki_service.create_page로 기록한다.

자동 분류(auto_categorize)가 켜진 경우, 각 소스의 제목/본문이 준비된 직후 decomposer(LLM 주제별
분해)를 호출한다. 분해기는 소스를 주제별로 여러 섹션으로 쪼개어 각각 별도 페이지+카테고리로 생성한다.
단일 주제면 섹션 1개=페이지 1개가 된다. 수동 category_id가 주어지면 분해 없이 그 카테고리로 단일 페이지.
"""
from __future__ import annotations

import asyncio
import io
import logging
import re
from typing import Awaitable, Callable
from urllib.parse import parse_qs, urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import core.wiki_store as store
from core.wiki_service import create_page
from database.models import DeepResearchMessage, DeepResearchSession, WikiPage

logger = logging.getLogger(__name__)

# (title, content) -> [{title, content, category_id}, ...]
Decomposer = Callable[[str, str], Awaitable[list[dict]]]

_YT_RE = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|embed/|v/|shorts/))([\w\-]{11})"
)

_IMAGE_PROMPT = (
    "이 이미지를 분석해 위키 페이지 본문으로 사용할 마크다운을 작성하라. "
    "첫 줄에 '# ' 로 시작하는 제목을, 이후에 이미지의 내용·주요 객체·맥락을 상세히 설명하라."
)


def _title_from_md(content: str, fallback: str) -> str:
    for line in content.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip()
    return fallback


async def _sections(
    decomposer: Decomposer | None,
    category_id: str | None,
    title: str,
    content: str,
) -> list[dict]:
    """분해 결과 섹션 리스트를 반환한다.

    - 수동 category_id가 있으면 분해 없이 단일 섹션.
    - decomposer가 있으면 호출해 다중 섹션. 예외/빈 결과면 단일 섹션(미분류) 폴백.
    - 둘 다 없으면 단일 섹션(미분류).
    """
    if category_id:
        return [{"title": title, "content": content, "category_id": category_id}]
    if decomposer is None:
        return [{"title": title, "content": content, "category_id": None}]
    try:
        secs = await decomposer(title, content)
    except Exception as e:
        logger.warning("decomposer failed (%s); single-page fallback", e)
        return [{"title": title, "content": content, "category_id": None}]
    if not secs:
        return [{"title": title, "content": content, "category_id": None}]
    return secs


async def _create_sections(
    db: AsyncSession,
    wiki_id: str,
    sections: list[dict],
    *,
    source_type: str,
    source_ref: str | None,
) -> list[WikiPage]:
    pages: list[WikiPage] = []
    for sec in sections:
        pages.append(
            await create_page(
                db, wiki_id,
                category_id=sec.get("category_id"),
                title=sec.get("title") or "문서",
                content=sec.get("content") or "",
                source_type=source_type,
                source_ref=source_ref,
            )
        )
    return pages


def parse_youtube_id(url: str) -> str | None:
    if not url:
        return None
    m = _YT_RE.search(url)
    if m:
        return m.group(1)
    # 순수 ID 형태
    if re.fullmatch(r"[\w\-]{11}", url.strip()):
        return url.strip()
    try:
        q = parse_qs(urlparse(url).query)
        v = q.get("v")
        if v:
            return v[0]
    except Exception:
        pass
    return None


async def _ingest_md(
    db: AsyncSession,
    wiki_id: str,
    category_id: str | None,
    filename: str,
    data: bytes,
    decomposer: Decomposer | None = None,
) -> list[WikiPage]:
    content = data.decode("utf-8", errors="replace")
    title = _title_from_md(content, store.slugify(filename) or "문서")
    sections = await _sections(decomposer, category_id, title, content)
    return await _create_sections(
        db, wiki_id, sections, source_type="md", source_ref=filename
    )


async def _ingest_pdf(
    db: AsyncSession,
    wiki_id: str,
    category_id: str | None,
    filename: str,
    data: bytes,
    decomposer: Decomposer | None = None,
) -> list[WikiPage]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data), strict=False)
    parts: list[str] = []
    for page in reader.pages:
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        if t.strip():
            parts.append(t.strip())
    body = "\n\n".join(parts) or "(텍스트를 추출할 수 없는 PDF입니다)"
    stored = await store.save_attachment(wiki_id, filename, data)
    title = store.slugify(filename) or "PDF 문서"
    full = f"# {title}\n\n> 원본: {filename} (attachments/{stored})\n\n{body}"
    sections = await _sections(decomposer, category_id, title, full)
    return await _create_sections(
        db, wiki_id, sections, source_type="pdf", source_ref=stored
    )


async def _ingest_image(
    db: AsyncSession,
    wiki_id: str,
    category_id: str | None,
    filename: str,
    data: bytes,
    mime: str,
    provider_type: str,
    base_url: str | None,
    model: str,
    api_key: str,
    decomposer: Decomposer | None = None,
) -> list[WikiPage]:
    from core.llm import describe_image

    description = await describe_image(
        provider_type, base_url, model, _IMAGE_PROMPT, data, mime, api_key
    )
    title = _title_from_md(description, store.slugify(filename) or "이미지")
    stored = await store.save_attachment(wiki_id, filename, data)
    body = f"> 원본 이미지: {filename} (attachments/{stored})\n\n{description}"
    sections = await _sections(decomposer, category_id, title, body)
    return await _create_sections(
        db, wiki_id, sections, source_type="image", source_ref=stored
    )


async def _ingest_deepresearch(
    db: AsyncSession,
    wiki_id: str,
    category_id: str | None,
    session_id: str,
    decomposer: Decomposer | None = None,
) -> list[WikiPage]:
    session = await db.get(DeepResearchSession, session_id)
    title = (session.title if session else None) or "딥 리서치 보고서"
    final = await db.scalar(
        select(DeepResearchMessage)
        .where(
            DeepResearchMessage.session_id == session_id,
            DeepResearchMessage.kind == "final",
        )
        .order_by(DeepResearchMessage.created_at.desc())
    )
    if not final:
        raise ValueError("딥 리서치 세션에 완성된 최종 보고서가 없습니다")
    # 보조: step_progress 요약(선택) — 본문에 보고서만 사용
    body = f"# {title}\n\n{final.content}"
    sections = await _sections(decomposer, category_id, title, body)
    return await _create_sections(
        db, wiki_id, sections, source_type="deepresearch", source_ref=session_id
    )


async def _fetch_youtube_transcript(video_id: str) -> list[dict]:
    from youtube_transcript_api import YouTubeTranscriptApi

    def _get():
        return YouTubeTranscriptApi.get_transcript(video_id, languages=["ko", "en"])

    return await asyncio.to_thread(_get)


async def _ingest_youtube(
    db: AsyncSession,
    wiki_id: str,
    category_id: str | None,
    url: str,
    decomposer: Decomposer | None = None,
) -> list[WikiPage]:
    vid = parse_youtube_id(url)
    if not vid:
        raise ValueError("올바른 YouTube URL이 아닙니다")
    try:
        snippets = await _fetch_youtube_transcript(vid)
    except Exception as e:
        raise ValueError(f"자막을 가져올 수 없습니다: {e}") from e
    if not snippets:
        raise ValueError("이 영상에 사용 가능한 자막이 없습니다")
    text = " ".join(s.get("text", "") for s in snippets).strip()
    title = f"YouTube 영상 {vid}"
    body = (
        f"# {title}\n\n"
        f"> 원본: https://www.youtube.com/watch?v={vid}\n\n"
        f"## 자막 전사\n\n{text}"
    )
    sections = await _sections(decomposer, category_id, title, body)
    return await _create_sections(
        db, wiki_id, sections, source_type="youtube", source_ref=vid
    )


_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
_MIME_TO_EXT = {
    "image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif",
    "image/webp": ".webp", "image/bmp": ".bmp",
}


def _is_image(filename: str, content_type: str | None) -> bool:
    from pathlib import Path

    ext = Path(filename).suffix.lower()
    if ext in _IMAGE_EXTS:
        return True
    if content_type and content_type in _MIME_TO_EXT:
        return True
    return False


def _is_pdf(filename: str, content_type: str | None) -> bool:
    from pathlib import Path

    return (
        Path(filename).suffix.lower() == ".pdf"
        or (content_type == "application/pdf")
    )


async def ingest(
    db: AsyncSession,
    wiki_id: str,
    *,
    category_id: str | None = None,
    files: list | None = None,
    deepresearch_session_id: str | None = None,
    youtube_url: str | None = None,
    provider_type: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    auto_categorize: bool = False,
) -> tuple[list[WikiPage], list[dict]]:
    """제공된 소스들을 처리해 페이지를 생성한다.

    반환: (생성된 WikiPage 리스트, 이번 주입에서 자동 생성된 카테고리 dict 리스트).
    auto_categorize=True 이고 수동 category_id가 없으면 각 소스를 주제별로 분해해 다중 페이지를
    만든다. 단일 주제 문서는 자연스럽게 1개 페이지가 된다.
    """
    created: list[WikiPage] = []
    created_categories: list[dict] = []

    decomposer: Decomposer | None = None
    if auto_categorize and not category_id:
        from core.wiki_decompose import decompose_document

        async def _decomposer(title: str, content: str) -> list[dict]:
            return await decompose_document(
                provider_type, base_url, model, api_key, wiki_id, title, content,
                created_categories=created_categories,
            )

        decomposer = _decomposer

    if deepresearch_session_id:
        created.extend(
            await _ingest_deepresearch(
                db, wiki_id, category_id, deepresearch_session_id, decomposer
            )
        )

    if youtube_url:
        created.extend(
            await _ingest_youtube(db, wiki_id, category_id, youtube_url, decomposer)
        )

    for f in files or []:
        filename = f.filename or "file"
        data = await f.read()
        if _is_image(filename, f.content_type):
            if not provider_type or not model:
                raise ValueError(
                    "이미지 주입에는 비전 지원 모델이 위키에 설정되어야 합니다"
                )
            mime = f.content_type or "image/png"
            created.extend(
                await _ingest_image(
                    db, wiki_id, category_id, filename, data, mime,
                    provider_type, base_url, model, api_key, decomposer,
                )
            )
        elif _is_pdf(filename, f.content_type):
            created.extend(
                await _ingest_pdf(db, wiki_id, category_id, filename, data, decomposer)
            )
        elif filename.lower().endswith(".md") or (f.content_type or "").startswith("text/"):
            created.extend(
                await _ingest_md(db, wiki_id, category_id, filename, data, decomposer)
            )
        else:
            # 알 수 없는 형식: 텍스트로 시도
            created.extend(
                await _ingest_md(db, wiki_id, category_id, filename, data, decomposer)
            )

    return created, created_categories
