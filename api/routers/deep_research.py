import asyncio
import json
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import require_permission
from core.llm import chat_complete, is_configured, list_enabled_models, stream_chat
from core.websearch import format_search_results, web_search
from database.connection import AsyncSessionLocal, get_db
from database.models import Account, DeepResearchMessage, DeepResearchSession, LLMProvider
from schemas.deep_research import (
    MessageResponse,
    ModelsForSelectionResponse,
    PlanStep,
    PlanUpdate,
    ProviderForSelection,
    SendMessage,
    SessionCreate,
    SessionDetailResponse,
    SessionResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/deep-research", tags=["deep-research"])

_MAX_SEARCHES_PER_STEP = 3

_PLAN_SYSTEM = (
    "너는 딥 리서치 에이전트의 플래너다. 사용자의 조사 요청을 분석해 조사 스텝 목록을 작성하라. "
    "각 스텝은 title(조사 항목)과 query(웹 검색 쿼리, 선택)을 갖는다. "
    "반드시 다음 JSON 형식만 출력하고 다른 텍스트는 출력하지 마라: "
    '{"steps":[{"title":"...","query":"..."}]}'
)

_AGENT_SYSTEM = (
    "너는 딥 리서치 에이전트다. 승인된 플랜의 각 스텝을 순서대로 조사하라. "
    "외부 정보가 필요하면 'SEARCH: <쿼리>' 형식의 줄을 출력해 웹 검색을 요청하라. "
    "검색 결과가 제공되면 이를 종합해 스텝 결과를 작성하라. "
    "SEARCH: 로 시작하지 않는 모든 텍스트는 사용자에게 실시간으로 표시된다."
)

_FINAL_SYSTEM = (
    "너는 딥 리서치 에이전트의 최종 보고서 작성자다. "
    "모든 스텝의 조사 결과를 종합해 사용자가 이해하기 쉬운 최종 보고서를 마크다운으로 작성하라."
)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _extract_json(text: str) -> dict | None:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    match = re.search(r"\{.*\}", candidate, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _session_to_response(s: DeepResearchSession) -> SessionResponse:
    plan = None
    if s.plan:
        plan = [PlanStep(**p) for p in s.plan]
    return SessionResponse(
        id=s.id,
        account_id=s.account_id,
        provider_id=s.provider_id,
        model=s.model,
        title=s.title,
        status=s.status,
        plan=plan,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


async def _messages_for(db: AsyncSession, session_id: str) -> list[MessageResponse]:
    msgs = await db.scalars(
        select(DeepResearchMessage)
        .where(DeepResearchMessage.session_id == session_id)
        .order_by(DeepResearchMessage.created_at)
    )
    return [
        MessageResponse(
            id=m.id, role=m.role, kind=m.kind, content=m.content, created_at=m.created_at
        )
        for m in msgs
    ]


async def _detail(db: AsyncSession, session: DeepResearchSession) -> SessionDetailResponse:
    return SessionDetailResponse(
        **_session_to_response(session).model_dump(),
        messages=await _messages_for(db, session.id),
    )


# ── 백그라운드 실행: 인메모리 이벤트 스토어 ────────────────────────────────────
# session_id -> {"events": [sse_str, ...], "queues": [asyncio.Queue, ...], "done": bool}
_live: dict[str, dict] = {}
# session_id -> asyncio.Task
_active_tasks: dict[str, asyncio.Task] = {}


def _init_live(session_id: str) -> None:
    if session_id not in _live:
        _live[session_id] = {"events": [], "queues": [], "done": False}


def _append_event(session_id: str, sse_str: str) -> None:
    state = _live.get(session_id)
    if not state:
        return
    state["events"].append(sse_str)
    for q in state["queues"]:
        q.put_nowait(sse_str)


async def _subscribe(session_id: str):
    """조회용 SSE 제너레이터: 과거 이벤트 재생 후 실시간 tail. 세션 종료 시 종료."""
    state = _live.get(session_id)
    if not state:
        return
    for ev in list(state["events"]):
        yield ev
    if state["done"]:
        return
    q: asyncio.Queue = asyncio.Queue()
    state["queues"].append(q)
    try:
        while True:
            ev = await q.get()
            if ev is None:
                break
            yield ev
    finally:
        if q in state["queues"]:
            state["queues"].remove(q)


def _finish_live(session_id: str) -> None:
    state = _live.get(session_id)
    if not state:
        return
    state["done"] = True
    for q in state["queues"]:
        q.put_nowait(None)


def _clear_live(session_id: str) -> None:
    state = _live.pop(session_id, None)
    if state:
        for q in state["queues"]:
            q.put_nowait(None)


def _cancel_task(session_id: str) -> None:
    task = _active_tasks.pop(session_id, None)
    if task and not task.done():
        task.cancel()


@router.get("/models", response_model=ModelsForSelectionResponse)
async def list_models_for_selection(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("deep_research", "read")),
):
    """딥 리서치 세션 시작 시 선택 가능한 모델 목록(FR-I06). 활성 + 키 설정된 제공자만.
    또한 제공자 API에서 현재 키로 실제 사용 가능한 모델을 조회해 교집합만 노출한다.
    조회 실패 시 검증을 건너뛰고 등록된 모델 전체를 노출한다."""
    providers = await db.scalars(
        select(LLMProvider).where(LLMProvider.is_active.is_(True)).order_by(LLMProvider.created_at)
    )
    result = []
    for p in providers:
        if not is_configured(p.provider_type):
            continue
        registered = list(p.models or [])
        enabled = await list_enabled_models(p.provider_type, p.base_url)
        if enabled is not None:
            usable = [m for m in registered if m in enabled]
        else:
            usable = registered
        result.append(
            ProviderForSelection(
                id=p.id,
                display_name=p.display_name,
                provider_type=p.provider_type,
                models=usable,
            )
        )
    return ModelsForSelectionResponse(providers=result)


@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: SessionCreate,
    db: AsyncSession = Depends(get_db),
    account: Account = Depends(require_permission("deep_research", "create")),
):
    provider = await db.get(LLMProvider, body.provider_id)
    if not provider or not provider.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "활성 제공자를 찾을 수 없습니다")
    if not is_configured(provider.provider_type):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"{provider.provider_type} API 키가 환경변수에 설정되지 않았습니다",
        )
    if body.model not in (provider.models or []):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "선택한 모델이 제공자에 없습니다")

    # 제공자 API에서 실제 사용 가능한 모델 조회가 가능하면 추가 검증
    enabled = await list_enabled_models(provider.provider_type, provider.base_url)
    if enabled is not None and body.model not in enabled:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "선택한 모델이 이 API 키에서 비활성화되어 있습니다. 모델 관리에서 사용 가능한 모델을 등록하세요.",
        )

    session = DeepResearchSession(
        account_id=account.id,
        provider_id=provider.id,
        model=body.model,
        title=body.title,
        status="draft",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return _session_to_response(session)


@router.get("/sessions", response_model=list[SessionResponse])
async def list_my_sessions(
    db: AsyncSession = Depends(get_db),
    account: Account = Depends(require_permission("deep_research", "read")),
):
    rows = await db.scalars(
        select(DeepResearchSession)
        .where(DeepResearchSession.account_id == account.id)
        .order_by(DeepResearchSession.created_at.desc())
    )
    return [_session_to_response(s) for s in rows]


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    account: Account = Depends(require_permission("deep_research", "read")),
):
    session = await db.get(DeepResearchSession, session_id)
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "세션을 찾을 수 없습니다")
    if session.account_id != account.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "접근할 수 없는 세션입니다")
    return await _detail(db, session)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    account: Account = Depends(require_permission("deep_research", "create")),
):
    session = await db.get(DeepResearchSession, session_id)
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "세션을 찾을 수 없습니다")
    if session.account_id != account.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "접근할 수 없는 세션입니다")
    # 실행 중인 세션도 삭제 허용: 백그라운드 태스크 취소 + 이벤트 버퍼 정리 후 행 삭제
    _cancel_task(session_id)
    _clear_live(session_id)
    await db.delete(session)
    await db.commit()


@router.post("/sessions/{session_id}/messages", response_model=SessionDetailResponse)
async def send_message(
    session_id: str,
    body: SendMessage,
    db: AsyncSession = Depends(get_db),
    account: Account = Depends(require_permission("deep_research", "create")),
):
    """사용자 메시지 전송. draft 상태면 플랜을 생성해 awaiting_approval로 전환(FR-I04)."""
    session = await db.get(DeepResearchSession, session_id)
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "세션을 찾을 수 없습니다")
    if session.account_id != account.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "접근할 수 없는 세션입니다")

    db.add(DeepResearchMessage(session_id=session_id, role="user", kind="text", content=body.content))
    if not session.title:
        session.title = body.content[:80]

    provider = await db.get(LLMProvider, session.provider_id) if session.provider_id else None
    if not provider:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "제공자를 찾을 수 없습니다")

    messages = [
        {"role": "system", "content": _PLAN_SYSTEM},
        {"role": "user", "content": body.content},
    ]
    try:
        raw = await chat_complete(provider.provider_type, provider.base_url, session.model, messages)
    except RuntimeError as e:
        await db.commit()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e))
    except Exception as e:
        logger.exception("플랜 생성 LLM 호출 실패: %s", e)
        await db.commit()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "플랜 생성에 실패했습니다")

    plan_data = _extract_json(raw)
    if not plan_data or not plan_data.get("steps"):
        db.add(DeepResearchMessage(session_id=session_id, role="assistant", kind="text", content=raw))
        session.status = "draft"
        await db.commit()
        await db.refresh(session)
        return await _detail(db, session)

    steps = []
    for s in plan_data["steps"]:
        steps.append(
            PlanStep(
                id=s.get("id") or str(len(steps) + 1),
                title=str(s.get("title", "")).strip(),
                query=s.get("query"),
                done=False,
            ).model_dump()
        )
    session.plan = steps
    session.status = "awaiting_approval"
    db.add(
        DeepResearchMessage(
            session_id=session_id,
            role="assistant",
            kind="plan",
            content=json.dumps(steps, ensure_ascii=False),
        )
    )
    await db.commit()
    await db.refresh(session)
    return await _detail(db, session)


@router.put("/sessions/{session_id}/plan", response_model=SessionResponse)
async def update_plan(
    session_id: str,
    body: PlanUpdate,
    db: AsyncSession = Depends(get_db),
    account: Account = Depends(require_permission("deep_research", "create")),
):
    session = await db.get(DeepResearchSession, session_id)
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "세션을 찾을 수 없습니다")
    if session.account_id != account.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "접근할 수 없는 세션입니다")
    if session.status != "awaiting_approval":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "플랜 편집은 승인 대기 상태에서만 가능합니다")

    session.plan = [s.model_dump() for s in body.steps]
    db.add(
        DeepResearchMessage(
            session_id=session_id,
            role="user",
            kind="plan",
            content=json.dumps(session.plan, ensure_ascii=False),
        )
    )
    await db.commit()
    await db.refresh(session)
    return _session_to_response(session)


@router.post("/sessions/{session_id}/plan/approve", response_model=SessionResponse)
async def approve_plan(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    account: Account = Depends(require_permission("deep_research", "create")),
):
    session = await db.get(DeepResearchSession, session_id)
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "세션을 찾을 수 없습니다")
    if session.account_id != account.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "접근할 수 없는 세션입니다")
    if session.status != "awaiting_approval":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "승인 대기 상태가 아닙니다")
    session.status = "approved"
    await db.commit()
    await db.refresh(session)
    return _session_to_response(session)


@router.post("/sessions/{session_id}/plan/reject", response_model=SessionResponse)
async def reject_plan(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    account: Account = Depends(require_permission("deep_research", "create")),
):
    session = await db.get(DeepResearchSession, session_id)
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "세션을 찾을 수 없습니다")
    if session.account_id != account.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "접근할 수 없는 세션입니다")
    if session.status != "awaiting_approval":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "승인 대기 상태가 아닙니다")
    session.status = "rejected"
    await db.commit()
    await db.refresh(session)
    return _session_to_response(session)


# ── 에이전트 루프 (백그라운드 실행) ────────────────────────────────────────────


async def _execute_step(
    db: AsyncSession,
    session_id: str,
    session: DeepResearchSession,
    provider: LLMProvider,
    step: dict,
    step_summaries: list[str],
    idx: int,
    holder: dict,
):
    """단일 스텝 실행: LLM 스트리밍 + SEARCH: 파싱 + 웹 검색 반복. 이벤트는 _append_event로 push."""
    context = "\n\n".join(step_summaries) if step_summaries else "(이전 스텝 없음)"
    user_msg = (
        f"이전 스텝 결과:\n{context}\n\n"
        f"현재 스텝({idx + 1}): {step.get('title', '')}\n"
        f"검색 쿼리 힌트: {step.get('query') or '없음'}\n"
        "이 스텝을 조사하라. 필요하면 SEARCH: <쿼리> 로 검색을 요청하라."
    )
    messages: list[dict] = [
        {"role": "system", "content": _AGENT_SYSTEM},
        {"role": "user", "content": user_msg},
    ]

    collected = ""
    searches = 0
    while searches <= _MAX_SEARCHES_PER_STEP:
        chunk_text = ""
        async for delta in stream_chat(
            provider.provider_type, provider.base_url, session.model, messages
        ):
            chunk_text += delta
            collected += delta
            holder["text"] = collected
            _append_event(session_id, _sse("step_delta", {"index": idx, "delta": delta}))

        search_match = re.search(r"SEARCH:\s*(.+?)(?:\n|$)", chunk_text)
        if search_match and searches < _MAX_SEARCHES_PER_STEP:
            query = search_match.group(1).strip()
            _append_event(session_id, _sse("search", {"index": idx, "query": query}))
            results = await web_search(query)
            _append_event(session_id, _sse("search_results", {"index": idx, "count": len(results)}))
            messages.append({"role": "assistant", "content": chunk_text})
            messages.append(
                {
                    "role": "user",
                    "content": f"검색 결과 for '{query}':\n{format_search_results(results)}\n\n"
                    "이 결과를 활용해 스텝 조사를 계속하라. 더 이상 검색이 필요 없으면 최종 스텝 결과를 작성하라.",
                }
            )
            searches += 1
            continue
        break

    db.add(
        DeepResearchMessage(
            session_id=session_id, role="assistant", kind="step_progress", content=collected
        )
    )
    await db.commit()


async def _run_agent_loop(session_id: str, account_id: str):
    """백그라운드 에이전트 루프. 이벤트를 _append_event로 push하고 DB에 영속화한다(FR-I05).

    HTTP 연결과 무관하게 실행되며, 완료/실패/취소 어느 경우든 _finish_live로 조회 스트림을 종료한다.
    """
    _init_live(session_id)
    async with AsyncSessionLocal() as db:
        session = await db.get(DeepResearchSession, session_id)
        if not session or session.account_id != account_id:
            _append_event(session_id, _sse("error", {"message": "세션을 찾을 수 없습니다"}))
            _finish_live(session_id)
            return
        if session.status != "approved" and session.status != "running":
            _append_event(
                session_id, _sse("error", {"message": "승인된 플랜만 실행할 수 있습니다"})
            )
            _finish_live(session_id)
            return

        provider = await db.get(LLMProvider, session.provider_id) if session.provider_id else None
        if not provider:
            _append_event(session_id, _sse("error", {"message": "제공자를 찾을 수 없습니다"}))
            _finish_live(session_id)
            return

        session.status = "running"
        await db.commit()

        plan: list[dict] = list(session.plan or [])
        step_summaries: list[str] = []

        try:
            for idx, step in enumerate(plan):
                if session_id not in _live:
                    return  # 삭제됨
                _append_event(session_id, _sse("step_start", {"index": idx, "title": step.get("title", "")}))
                holder = {"text": ""}
                await _execute_step(
                    db, session_id, session, provider, step, step_summaries, idx, holder
                )
                step_summaries.append(
                    f"## 스텝 {idx + 1}: {step.get('title', '')}\n{holder['text']}"
                )
                step["done"] = True
                session.plan = plan
                await db.commit()
                _append_event(session_id, _sse("step_done", {"index": idx}))

            _append_event(session_id, _sse("final_start", {}))
            final_messages = [
                {"role": "system", "content": _FINAL_SYSTEM},
                {
                    "role": "user",
                    "content": "모든 스텝 결과를 종합해 최종 보고서를 작성하라:\n\n"
                    + "\n\n".join(step_summaries),
                },
            ]
            final_text = ""
            async for delta in stream_chat(
                provider.provider_type, provider.base_url, session.model, final_messages
            ):
                final_text += delta
                _append_event(session_id, _sse("final_delta", {"delta": delta}))

            db.add(
                DeepResearchMessage(
                    session_id=session_id, role="assistant", kind="final", content=final_text
                )
            )
            session.status = "completed"
            await db.commit()
            _append_event(session_id, _sse("final_done", {}))
            _append_event(session_id, _sse("completed", {"status": "completed"}))
        except asyncio.CancelledError:
            # 삭제/취소로 인한 중단 — status 복원 후 재전파하지 않음(정상 종료 처리)
            session = await db.get(DeepResearchSession, session_id)
            if session:
                session.status = "approved"
                await db.commit()
            _append_event(session_id, _sse("cancelled", {}))
            raise
        except Exception as e:
            logger.exception("에이전트 루프 실패: %s", e)
            session = await db.get(DeepResearchSession, session_id)
            if session:
                session.status = "approved"
                await db.commit()
            _append_event(session_id, _sse("error", {"message": f"에이전트 실행 중 오류: {e}"}))
        finally:
            _finish_live(session_id)
            _active_tasks.pop(session_id, None)


@router.post("/sessions/{session_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_session(
    session_id: str,
    account: Account = Depends(require_permission("deep_research", "create")),
    db: AsyncSession = Depends(get_db),
):
    """백그라운드 에이전트 루프를 시작하고 즉시 202를 반환한다. 진행은 GET /stream으로 조회."""
    session = await db.get(DeepResearchSession, session_id)
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "세션을 찾을 수 없습니다")
    if session.account_id != account.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "접근할 수 없는 세션입니다")

    existing = _active_tasks.get(session_id)
    live = existing is not None and not existing.done()
    if session.status == "running" and live:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "이미 실행 중인 세션입니다")
    if session.status not in ("approved", "running"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "승인된 플랜만 실행할 수 있습니다")

    if not live:
        _init_live(session_id)
        task = asyncio.create_task(_run_agent_loop(session_id, account.id))
        _active_tasks[session_id] = task
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.get("/sessions/{session_id}/stream")
async def stream_session(
    session_id: str,
    account: Account = Depends(require_permission("deep_research", "read")),
):
    """백그라운드 진행 상황을 SSE로 조회. 과거 이벤트 재생 후 실시간 tail. 재접속 가능."""
    return StreamingResponse(
        _subscribe(session_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
