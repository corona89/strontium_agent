"""LLM 위키 문서 주제별 분해(decomposition).

주입 소스의 전체 본문을 LLM이 분석해 주제별로 여러 섹션으로 분할한다.
각 섹션은 (title, content[원문 발췌], category)를 가지며, 각각 별도의 위키 페이지로 생성된다.
카테고리는 기존 이름 재사용을 우선하고, 없으면 새 이름으로 find_or_create 한다.
모든 실패 경로는 단일 페이지 [{title, content, None}]로 폴백해 정보 손실을 막는다.
"""
from __future__ import annotations

import json
import logging
import re

import core.wiki_store as store
from core.llm import chat_complete
from core.wiki_service import find_or_create_category

logger = logging.getLogger(__name__)

_MAX_INPUT_CHARS = 16000
_MAX_SECTIONS = 12

_SYSTEM_PROMPT = (
    "너는 문서 구조화 전문가다. 주어진 문서를 주제별로 분할해 각각을 별도의 위키 페이지로 만들고, "
    "각 페이지에 들어갈 카테고리를 할당한다.\n"
    "규칙:\n"
    "1. 문서에서 구분되는 주제/섹션을 식별하라. 같은 주제를 다루는 부분은 하나로 합쳐라.\n"
    "2. 각 섹션의 content는 원문에서 해당 주제에 해당하는 부분을 가능한 한 그대로 발췌하라. "
    "절대 요약하거나 새로 창작하지 마라 (원문 보존).\n"
    "3. 각 섹션의 category: 기존 카테고리 목록 중 주제가 맞으면 그 '이름'을 그대로 사용하고, "
    "없으면 간결한 새 이름(명사구, 1~15자, 한국어)을 제안하라. 중복/유사 카테고리 생성을 피하라.\n"
    "4. 문서가 단일 주제면 섹션을 정확히 1개만 반환하라.\n"
    "5. 섹션은 최대 12개까지 생성할 수 있다.\n"
    "6. 반드시 아래 JSON 형식으로만 응답하고, 그 외 텍스트는 절대 출력하지 마라.\n"
    '{"sections": [{"title": "...", "content": "...", "category": "..."}]}'
)

# 응답 전체가 JSON이라 가정하고 가장 바깥 객체를 잡는다(중첩 배열/객체 포함).
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _list_categories(wiki_id: str) -> list[dict]:
    st = store.read_structure(wiki_id)
    return [{"id": c["id"], "name": c["name"]} for c in st.get("categories", [])]


def _truncate(text: str) -> str:
    text = (text or "").strip()
    if len(text) > _MAX_INPUT_CHARS:
        logger.info(
            "decompose input truncated %d -> %d chars", len(text), _MAX_INPUT_CHARS
        )
        return text[:_MAX_INPUT_CHARS]
    return text


def _build_user_prompt(existing_names: list[str], title: str, content: str) -> str:
    if existing_names:
        cat_lines = "\n".join(f"- {n}" for n in existing_names)
    else:
        cat_lines = "(기존 카테고리 없음 — 필요시 새 이름 제안)"
    return (
        "[기존 카테고리 이름 목록(재사용 우선)]\n"
        f"{cat_lines}\n\n"
        "[문서]\n"
        f"제목: {title}\n"
        f"본문:\n{content}\n\n"
        "이 문서를 주제별로 분할해 위 JSON 형식으로 답하라."
    )


def _parse_sections(raw: str) -> list[dict] | None:
    """LLM 원시 응답에서 sections 배열을 추출한다. 실패 시 None."""
    if not raw:
        return None
    text = raw.strip()
    # ```json ... ``` 펜스 내부면 추출
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    candidate = fence.group(1) if fence else None
    if not candidate:
        m = _JSON_RE.search(text)
        candidate = m.group(0) if m else None
    if not candidate:
        return None
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    sections = data.get("sections")
    if not isinstance(sections, list) or not sections:
        return None
    return sections


def _single_fallback(title: str, content: str, category_id: str | None) -> list[dict]:
    return [{"title": title, "content": content, "category_id": category_id}]


async def decompose_document(
    provider_type: str | None,
    base_url: str | None,
    model: str | None,
    api_key: str | None,
    wiki_id: str,
    title: str,
    content: str,
    *,
    created_categories: list[dict] | None = None,
) -> list[dict]:
    """문서를 주제별 섹션으로 분해해 [{title, content, category_id}, ...]를 반환한다.

    각 섹션의 category_id는 기존 카테고리 재사용 또는 신규 생성(find_or_create_category)으로 결정.
    새로 생성된 카테고리는 created_categories에 누적된다.
    LLM 미설정/호출 실패/파싱 실패 → 단일 페이지 폴백(정보 손실 방지).
    """
    if not provider_type or not model or not api_key:
        logger.warning("decompose requested but no provider/model/key; single-page fallback")
        return _single_fallback(title, content, None)

    body = _truncate(content)
    categories = _list_categories(wiki_id)
    existing_names = [c["name"] for c in categories]
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(existing_names, title, body)},
    ]
    try:
        raw = await chat_complete(provider_type, base_url, model, messages, api_key)
    except Exception as e:
        logger.warning("decompose LLM call failed: %s; single-page fallback", e)
        return _single_fallback(title, content, None)

    sections = _parse_sections(raw)
    if not sections:
        logger.warning("decompose unparseable response: %r; single-page fallback", raw[:200])
        return _single_fallback(title, content, None)

    result: list[dict] = []
    for sec in sections[:_MAX_SECTIONS]:
        if not isinstance(sec, dict):
            continue
        sec_title = (sec.get("title") or "").strip()
        sec_content = (sec.get("content") or "").strip()
        cat_name = (sec.get("category") or "").strip()
        if not sec_title or not sec_content:
            continue
        # 카테고리 결정: 빈 이름이면 미분류(None), 아니면 find_or_create
        if cat_name:
            before_ids = {c["id"] for c in _list_categories(wiki_id)}
            cat_id = find_or_create_category(wiki_id, cat_name)
            if created_categories is not None and cat_id not in before_ids:
                st = store.read_structure(wiki_id)
                cat = next((c for c in st["categories"] if c["id"] == cat_id), None)
                if cat:
                    created_categories.append(cat)
        else:
            cat_id = None
        result.append({"title": sec_title, "content": sec_content, "category_id": cat_id})

    if not result:
        return _single_fallback(title, content, None)
    return result
