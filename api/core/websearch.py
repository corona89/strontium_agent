import logging
from typing import Any

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

_TAVILY_URL = "https://api.tavily.com/search"


async def web_search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Tavily 웹 검색. 딥 리서치 에이전트의 검색 도구(FR-I05).

    returns: [{"title", "url", "content"}, ...]
    API 키가 없으면 빈 목록 반환(에이전트는 LLM만으로 진행).
    """
    if not settings.TAVILY_API_KEY:
        logger.warning("TAVILY_API_KEY가 설정되지 않아 웹 검색을 건너뜁니다")
        return []

    payload = {
        "query": query,
        "max_results": max_results,
        "include_answer": True,
        "search_depth": "basic",
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                _TAVILY_URL,
                json=payload,
                headers={"Authorization": f"Bearer {settings.TAVILY_API_KEY}"},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        logger.warning("Tavily 검색 실패: %s", e)
        return []

    results = []
    answer = data.get("answer")
    if answer:
        results.append({"title": "요약", "url": "", "content": answer})
    for r in data.get("results", []):
        results.append(
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
            }
        )
    return results


def format_search_results(results: list[dict[str, Any]]) -> str:
    """검색 결과를 LLM 컨텍스트용 텍스트로 포맷한다."""
    if not results:
        return "(검색 결과 없음)"
    lines = []
    for r in results:
        title = r.get("title", "")
        url = r.get("url", "")
        content = r.get("content", "")
        if url:
            lines.append(f"### {title}\n{url}\n{content}")
        else:
            lines.append(f"### {title}\n{content}")
    return "\n\n".join(lines)
