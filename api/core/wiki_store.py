"""LLM 위키 파일시스템 레이어.

파일시스템이 진실의 원천이며, `structure.md` 매니페스트가 카테고리/페이지 트리를 기술한다.
DB는 검색 인덱스용 캐시일 뿐이므로 시작/쓰기 시 동기화한다.
"""
from __future__ import annotations

import json
import re
import shutil
import unicodedata
from pathlib import Path

import aiofiles

from core.config import settings

EMPTY_STRUCTURE = {"categories": [], "pages": []}
_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def wiki_root() -> Path:
    root = Path(settings.WIKI_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    return root


def wiki_dir(wiki_id: str) -> Path:
    return wiki_root() / wiki_id


def attachments_dir(wiki_id: str) -> Path:
    d = wiki_dir(wiki_id) / "attachments"
    d.mkdir(parents=True, exist_ok=True)
    return d


def structure_path(wiki_id: str) -> Path:
    return wiki_dir(wiki_id) / "structure.md"


def init_wiki_dir(wiki_id: str) -> None:
    """신규 위키 디렉토리와 빈 매니페스트를 생성한다."""
    attachments_dir(wiki_id)
    if not structure_path(wiki_id).exists():
        write_structure(wiki_id, dict(EMPTY_STRUCTURE))


def delete_wiki_dir(wiki_id: str) -> None:
    d = wiki_dir(wiki_id)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def write_structure(wiki_id: str, structure: dict) -> None:
    body = "# Wiki Structure\n\n이 파일은 자동 생성됩니다. 카테고리/페이지 트리 매니페스트.\n\n"
    body += "```json\n" + json.dumps(structure, ensure_ascii=False, indent=2) + "\n```\n"
    structure_path(wiki_id).write_text(body, encoding="utf-8")


def read_structure(wiki_id: str) -> dict:
    p = structure_path(wiki_id)
    if not p.exists():
        return dict(EMPTY_STRUCTURE)
    text = p.read_text(encoding="utf-8")
    m = _FENCE_RE.search(text)
    if not m:
        return dict(EMPTY_STRUCTURE)
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return dict(EMPTY_STRUCTURE)
    return {
        "categories": list(data.get("categories") or []),
        "pages": list(data.get("pages") or []),
    }


def category_dir(wiki_id: str, slug: str) -> Path:
    return wiki_dir(wiki_id) / slug


def page_path(wiki_id: str, category_slug: str, page_slug: str) -> Path:
    cat = category_slug or "_uncategorized"
    return category_dir(wiki_id, cat) / f"{page_slug}.md"


async def read_page_content(wiki_id: str, category_slug: str, page_slug: str) -> str:
    p = page_path(wiki_id, category_slug, page_slug)
    if not p.exists():
        return ""
    async with aiofiles.open(p, "r", encoding="utf-8") as f:
        return await f.read()


async def write_page_content(
    wiki_id: str, category_slug: str, page_slug: str, content: str
) -> Path:
    cat = category_slug or "_uncategorized"
    d = category_dir(wiki_id, cat)
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{page_slug}.md"
    async with aiofiles.open(p, "w", encoding="utf-8") as f:
        await f.write(content)
    return p


def delete_page_file(wiki_id: str, category_slug: str, page_slug: str) -> None:
    p = page_path(wiki_id, category_slug, page_slug)
    if p.exists():
        p.unlink(missing_ok=True)


def attachment_path(wiki_id: str, name: str) -> Path:
    """첨부파일 경로. 이름은 서버 생성 난수 접두 파일명이어야 한다(경로 순회 방지)."""
    if "/" in name or "\\" in name or ".." in name:
        raise ValueError("잘못된 첨부파일 이름")
    return attachments_dir(wiki_id) / name


async def save_attachment(wiki_id: str, filename: str, data: bytes) -> str:
    """첨부파일을 저장하고 안전한 저장 이름을 반환한다."""
    import uuid

    stem = slugify(Path(filename).stem) or "file"
    suffix = Path(filename).suffix.lower()
    stored = f"{stem}-{uuid.uuid4().hex[:8]}{suffix}"
    p = attachments_dir(wiki_id) / stored
    async with aiofiles.open(p, "wb") as f:
        await f.write(data)
    return stored


_slug_strip_re = re.compile(r"[^\w\- ]+", re.UNICODE)


def slugify(text: str) -> str:
    """텍스트를 URL/파일명용 슬러그로 변환. 한글/영문/숫자/하이픈 유지."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text.strip())
    text = _slug_strip_re.sub("", text)
    text = re.sub(r"\s+", "-", text)
    text = text.strip("-_")
    return text.lower()[:80]


def unique_slug(existing_slugs: set[str], base: str) -> str:
    """충돌 회피 슬러그. base가 이미 존재하면 -2, -3, ... 접미."""
    base = base or "untitled"
    if base not in existing_slugs:
        return base
    n = 2
    while f"{base}-{n}" in existing_slugs:
        n += 1
    return f"{base}-{n}"
