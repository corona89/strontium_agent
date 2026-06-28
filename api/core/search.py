"""LLM 위키용 키워드 검색(BM25). 순수 Python, 외부 의존성 없음.

한국어(CJK)는 유니그램, 영문/숫자는 단어 단위로 토큰화한다.
제목 토큰은 가중치(3x)를 둬서 제목 매칭의 점수를 높인다.
"""
from __future__ import annotations

import math
import re

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[\uac00-\ud7a3\u3040-\u30ff\u4e00-\u9fff]+")
_TITLE_WEIGHT = 3
_K1 = 1.5
_B = 0.75
_MIN_SCORE = 0.5  # 의미 있는 매칭 임계치


def tokenize(text: str) -> list[str]:
    """텍스트를 토큰 리스트로 변환. 영문/숫자는 단어, CJK는 글자 단위."""
    if not text:
        return []
    lowered = text.lower()
    tokens: list[str] = []
    for run in _TOKEN_RE.findall(lowered):
        if run[0].isascii():
            tokens.append(run)
        else:
            tokens.extend(list(run))
    return tokens


def _doc_tokens(title: str, content: str) -> list[str]:
    """제목은 가중치를 두어 반복하고 본문과 합친 토큰."""
    title_tokens = tokenize(title) * _TITLE_WEIGHT
    return title_tokens + tokenize(content)


def bm25_search(
    question: str, pages: list[dict], top_k: int = 5
) -> list[tuple[str, float]]:
    """질문으로 위키 페이지들을 BM25 점수화해 상위 K개를 (page_id, score)로 반환.

    pages: [{"id": ..., "title": ..., "content": ...}, ...]
    의미 있는 매칭(점수 >= _MIN_SCORE)인 것만 반환한다.
    """
    if not pages:
        return []

    q_tokens = tokenize(question)
    if not q_tokens:
        return []
    q_set = set(q_tokens)

    n = len(pages)
    docs_tokens: list[list[str]] = []
    df: dict[str, int] = {}
    for p in pages:
        toks = _doc_tokens(p.get("title", ""), p.get("content", "") or "")
        docs_tokens.append(toks)
        seen = set(toks)
        for t in seen:
            df[t] = df.get(t, 0) + 1

    avgdl = sum(len(d) for d in docs_tokens) / max(n, 1)

    scored: list[tuple[str, float]] = []
    for idx, toks in enumerate(docs_tokens):
        if not toks:
            continue
        dl = len(toks)
        tf: dict[str, int] = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        score = 0.0
        for term in q_set:
            f = tf.get(term)
            if not f:
                continue
            ni = df.get(term, 0)
            idf = math.log(1 + (n - ni + 0.5) / (ni + 0.5))
            denom = f + _K1 * (1 - _B + _B * dl / avgdl) if avgdl > 0 else f + _K1
            score += idf * (f * (_K1 + 1)) / denom
        if score >= _MIN_SCORE:
            scored.append((pages[idx]["id"], score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]
