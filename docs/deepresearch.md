# 딥 리서치 에이전트 (Deep Research Agent)

> 조사 요청 → 플랜 자동 생성 → 사용자 승인 → 백그라운드 에이전트 루프(웹 검색 반복) → 최종 보고서를
> SSE로 실시간 스트리밍하는 에이전트 기능. 플랜 **승인제**·**백그라운드 실행**·**재접속 가능 SSE**가 핵심 특징.

관련 요구사항: [`requirements/fr/deep-research.md`](../requirements/fr/deep-research.md) (FR-I 시리즈)

---

## 1. 개요

딥 리서치 에이전트는 단일 LLM 호출이 아닌 **다수 스텝을 반복하는 에이전트 루프**로 동작한다. 핵심 흐름:

1. 사용자가 조사 주제를 보내면 **플래너 LLM**이 JSON 형식의 조사 플랜(스텝 목록)을 생성.
2. 사용자가 플랜을 편집/승인하면(거부 시 종료) 승인된 플랜만 실행 대상이 됨.
3. `POST /run`이 **백그라운드 태스크**(`asyncio.create_task`)로 에이전트 루프를 시작하고 **202 Accepted**를 즉시 반환.
4. 에이전트는 스텝별로 LLM을 스트리밍하며, 필요 시 `SEARCH: <쿼리>` 프로토콜로 **Tavily 웹 검색**을 반복 호출(스텝당 ≤3회)해 외부 정보를 수집.
5. 진행 상황은 인메모리 이벤트 스토어에 push되고, 클라이언트는 별도의 `GET /stream`(SSE)으로 **과거 재생 + 실시간 tail** 조회.
6. 모든 스텝이 끝나면 **최종 보고서 LLM** 호출로 마크다운 보고서를 스트리밍하고 DB에 영속화.

---

## 2. 아키텍처 및 구성요소

| 계층 | 파일 | 역할 |
|---|---|---|
| Frontend | [`web/app/(main)/deep-research/page.js`](../web/app/(main)/deep-research/page.js) | 채팅 UI · 세션 목록 · 플랜 편집/승인 · SSE 수신 렌더링(`liveLog`) |
| API 클라이언트 | [`web/lib/api.js`](../web/lib/api.js) `deepResearch:` (L131~) | REST 호출 + `streamSession` SSE 파서(`\n\n` 프레임 분할) |
| 라우터 | [`api/routers/deep_research.py`](../api/routers/deep_research.py) | 9개 엔드포인트 + 백그라운드 에이전트 루프 + 인메모리 이벤트 스토어 |
| LLM | [`api/core/llm.py`](../api/core/llm.py) | 모델 패밀리별 스트리밍 라우팅(GPT/Claude/그외), `chat_complete`, 사용가능모델 조회 |
| 웹검색 | [`api/core/websearch.py`](../api/core/websearch.py) | Tavily 검색 도구 + 결과 포맷터 |
| 모델/스키마 | [`api/database/models.py`](../api/database/models.py) · [`api/schemas/deep_research.py`](../api/schemas/deep_research.py) | `DeepResearchSession`/`DeepResearchMessage`/`LLMProvider` + Pydantic |
| 시작 복구 | [`api/main.py`](../api/main.py) (lifespan, L18~31) | 서버 재시작 시 `running` → `approved` 복구 |

### LLM 모델 패밀리 라우팅 (`core/llm.py`)

OpenCode Zen 제공자는 모델 접두사에 따라 엔드포인트가 다르다 (`_stream_zen`, L163~):

- `gpt*` → `/v1/responses` (OpenAI Responses API, `response.output_text.delta`)
- `claude*` → `/v1/messages` (Anthropic Messages API, `content_block_delta`)
- 그 외(GLM/Qwen/DeepSeek/Kimi/Grok 등) → `/v1/chat/completions` (표준 OpenAI 호환)
- `ollama_cloud` → `/api/chat` (NDJSON 라인 스트리밍)

세 모두 텍스트 **델타(스트링)** 로 정규화하여 상위에 yield한다.

---

## 3. 데이터 모델

### `deep_research_sessions`
| 컬럼 | 설명 |
|---|---|
| `id` (UUID) | PK |
| `account_id` | 소유자(FK → accounts, CASCADE) |
| `provider_id` | LLM 제공자(FK → llm_providers, SET NULL) |
| `model` | 세션 단위로 고정된 모델 식별자 |
| `title` | 첫 메시지 앞 80자로 자동 설정(또는 수동) |
| `status` | 상태머신 값(아래) |
| `plan` | JSON 배열 `[{id,title,query,done}]` |

### `deep_research_messages`
| 컬럼 | 설명 |
|---|---|
| `role` | `user` \| `assistant` \| `tool` |
| `kind` | 메시지 종류(아래) |
| `content` | 텍스트 / JSON |

**`kind` 값 의미**
| kind | role | 용도 |
|---|---|---|
| `text` | user/assistant | 일반 대화 / 플랜 생성 실패 시 원문 |
| `plan` | user/assistant | assistant=제안 플랜(JSON), user=편집된 플랜(JSON) |
| `step_progress` | assistant | 각 스텝의 LLM 산출물(중간 결과) |
| `final` | assistant | 최종 마크다운 보고서 |

> 검색(search)은 영속화하지 않고 SSE 이벤트로만 전달한다.

---

## 4. 세션 상태머신

```
draft ──(메시지 전송 → 플랜 생성)──▶ awaiting_approval
                                        │
                 ┌──────────────────────┼──────────────────────┐
            (편집 PUT)              (승인 POST)             (거부 POST)
                 │                       │                       │
                 ▼                       ▼                       ▼
        awaiting_approval            approved                rejected
                                         │
                                   (POST /run)
                                         ▼
                                      running ──(완료)──▶ completed
                                         │
                                   (취소/에러/삭제)
                                         ▼
                                   approved 로 복귀
```

| 전이 | 엔드포인트 | 설명 |
|---|---|---|
| → `awaiting_approval` | `POST /messages` | 플래너 LLM이 플랜 파싱 성공 시 |
| → `draft` | `POST /messages` | 플랜 JSON 파싱 실패 시(원문을 메시지로 저장) |
| → `approved` | `POST /plan/approve`, 또는 복구 | 실행 가능 상태 |
| → `rejected` | `POST /plan/reject` | 조사 진행 안 함 |
| → `running` | `POST /run` (루프 시작 시) | 백그라운드 실행 중 |
| → `completed` | 에이전트 루프 완료 | 최종 보고서 저장 |
| `running`→`approved` | 취소/에러/서버 재시작 lifespan | 재실행 가능하게 복귀 |

---

## 5. API 엔드포인트

모든 엔드포인트는 `require_permission("deep_research", ...)` 로 보호된다. 세션은 소유자(`account_id`)만 접근 가능.

| Method | Path | 권한 | 용도 |
|---|---|---|---|
| GET | `/deep-research/models` | read | 선택 가능한 모델(활성 제공자 · API키 검증된 교집합) |
| POST | `/deep-research/sessions` | create | 세션 생성(status=draft) |
| GET | `/deep-research/sessions` | read | 내 세션 목록 |
| GET | `/deep-research/sessions/{id}` | read | 세션 상세(메시지 포함) |
| DELETE | `/deep-research/sessions/{id}` | create | 세션 삭제(실행 중이면 태스크 취소+버퍼 정리 후 삭제) |
| POST | `/deep-research/sessions/{id}/messages` | create | 메시지 전송 → 플랜 생성(draft일 때) |
| PUT | `/deep-research/sessions/{id}/plan` | create | 플랜 편집(awaiting_approval 전용) |
| POST | `/deep-research/sessions/{id}/plan/approve` | create | 플랜 승인 |
| POST | `/deep-research/sessions/{id}/plan/reject` | create | 플랜 거부 |
| POST | `/deep-research/sessions/{id}/run` | create | 백그라운드 루프 시작 → **202** |
| GET | `/deep-research/sessions/{id}/stream` | read | SSE 진행상황(과거 재생 + 실시간 tail) |

---

## 6. 전체 워크플로우 (시퀀스 다이어그램)

별도 파일: [`deepresearch-sequence.drawio`](./deepresearch-sequence.drawio) (draw.io / VS Code 확장에서 열기).

> 아래 ```drawio 블록은 프로젝트 `MarkdownRenderer`(`DrawioDiagram.jsx`, viewer.diagrams.net)에서 렌더링된다.
> GitHub 등 일반 마크다운 뷰어에서는 XML 원문으로 보이며, 이 경우 위 파일을 draw.io로 열면 된다.

```drawio
    <mxfile host="app.diagrams.net" agent="wherewindsmeet" version="24.0.0">
      <diagram id="deepresearch-seq" name="DeepResearch Sequence">
    <mxGraphModel dx="1422" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1500" pageHeight="1900" math="0" shadow="0">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        <mxCell id="title" value="딥 리서치 에이전트 — 전체 시퀀스 (end-to-end)" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=16;fontStyle=1;" vertex="1" parent="1"><mxGeometry x="40" y="6" width="900" height="28" as="geometry"/></mxCell>
        <mxCell id="legend" value="실선 = 요청/호출    ┊    점선(열린 화살표) = 반환/응답    ┊    점선(채워진 화살표) = SSE 스트리밍" style="text;html=1;strokeColor=none;fillColor=none;align=right;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=10;fontColor=#666666;" vertex="1" parent="1"><mxGeometry x="900" y="10" width="560" height="20" as="geometry"/></mxCell>
        <mxCell id="ll_U" value="사용자" style="shape=umlLifeline;perimeter=lifelinePerimeter;fontSize=12;fontStyle=1;whiteSpace=wrap;html=1;container=0;collapsible=0;recursiveResize=0;outlineConnect=0;size=38;fillColor=#dae8fc;strokeColor=#6c8ebf;" vertex="1" parent="1"><mxGeometry x="30" y="44" width="150" height="1845" as="geometry"/></mxCell>
        <mxCell id="ll_F" value="Frontend
    (page.js)" style="shape=umlLifeline;perimeter=lifelinePerimeter;fontSize=12;fontStyle=1;whiteSpace=wrap;html=1;container=0;collapsible=0;recursiveResize=0;outlineConnect=0;size=38;fillColor=#d5e8d4;strokeColor=#82b366;" vertex="1" parent="1"><mxGeometry x="240" y="44" width="150" height="1845" as="geometry"/></mxCell>
        <mxCell id="ll_A" value="API 라우터
    (deep_research.py)" style="shape=umlLifeline;perimeter=lifelinePerimeter;fontSize=12;fontStyle=1;whiteSpace=wrap;html=1;container=0;collapsible=0;recursiveResize=0;outlineConnect=0;size=38;fillColor=#ffe6cc;strokeColor=#d79b00;" vertex="1" parent="1"><mxGeometry x="450" y="44" width="150" height="1845" as="geometry"/></mxCell>
        <mxCell id="ll_L" value="LLM
    (core/llm.py)" style="shape=umlLifeline;perimeter=lifelinePerimeter;fontSize=12;fontStyle=1;whiteSpace=wrap;html=1;container=0;collapsible=0;recursiveResize=0;outlineConnect=0;size=38;fillColor=#e1d5e7;strokeColor=#9673a6;" vertex="1" parent="1"><mxGeometry x="660" y="44" width="150" height="1845" as="geometry"/></mxCell>
        <mxCell id="ll_T" value="Tavily
    (websearch.py)" style="shape=umlLifeline;perimeter=lifelinePerimeter;fontSize=12;fontStyle=1;whiteSpace=wrap;html=1;container=0;collapsible=0;recursiveResize=0;outlineConnect=0;size=38;fillColor=#daeef4;strokeColor=#5e8db4;" vertex="1" parent="1"><mxGeometry x="870" y="44" width="150" height="1845" as="geometry"/></mxCell>
        <mxCell id="ll_D" value="DB (SQLite)
    (deep_research_*)" style="shape=umlLifeline;perimeter=lifelinePerimeter;fontSize=12;fontStyle=1;whiteSpace=wrap;html=1;container=0;collapsible=0;recursiveResize=0;outlineConnect=0;size=38;fillColor=#f5f5f5;strokeColor=#666666;" vertex="1" parent="1"><mxGeometry x="1080" y="44" width="150" height="1845" as="geometry"/></mxCell>
        <mxCell id="ll_E" value="EventStore
    (인메모리 _live)" style="shape=umlLifeline;perimeter=lifelinePerimeter;fontSize=12;fontStyle=1;whiteSpace=wrap;html=1;container=0;collapsible=0;recursiveResize=0;outlineConnect=0;size=38;fillColor=#fff2cc;strokeColor=#d6b656;" vertex="1" parent="1"><mxGeometry x="1290" y="44" width="150" height="1845" as="geometry"/></mxCell>
        <mxCell id="loop1" value="백그라운드 에이전트 루프 — 스텝마다 반복 · HTTP 연결 무관" style="shape=umlFrame;whiteSpace=wrap;html=1;pointerEvents=0;fillColor=none;strokeColor=#b85450;fontSize=12;fontColor=#b85450;fontStyle=1;" vertex="1" parent="1"><mxGeometry x="455" y="1005" width="1000" height="515" as="geometry"/></mxCell>
        <mxCell id="m0" value="1. 제공자·모델 선택 → [새 조사]" style="endArrow=classic;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="105" y="110" as="sourcePoint"/><mxPoint x="315" y="110" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m1" value="POST /sessions {provider_id, model}" style="endArrow=classic;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="315" y="150" as="sourcePoint"/><mxPoint x="525" y="150" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m2" value="INSERT session (status=draft)" style="endArrow=classic;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="525" y="190" as="sourcePoint"/><mxPoint x="1155" y="190" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m3" value="ok" style="endArrow=open;dashed=1;html=1;fontSize=11;edgeStyle=none;rounded=0;strokeColor=#999999;fontColor=#666666;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="1155" y="230" as="sourcePoint"/><mxPoint x="525" y="230" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m4" value="201 SessionResponse" style="endArrow=open;dashed=1;html=1;fontSize=11;edgeStyle=none;rounded=0;strokeColor=#999999;fontColor=#666666;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="525" y="270" as="sourcePoint"/><mxPoint x="315" y="270" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m5" value="2. 조사 주제 입력 → 전송" style="endArrow=classic;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="105" y="315" as="sourcePoint"/><mxPoint x="315" y="315" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m6" value="POST /sessions/{id}/messages {content}" style="endArrow=classic;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="315" y="355" as="sourcePoint"/><mxPoint x="525" y="355" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m7" value="INSERT msg(user, text)" style="endArrow=classic;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="525" y="395" as="sourcePoint"/><mxPoint x="1155" y="395" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m8" value="chat_complete [_PLAN_SYSTEM] → JSON" style="endArrow=classic;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="525" y="435" as="sourcePoint"/><mxPoint x="735" y="435" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m9" value="{&quot;steps&quot;:[{title,query}]}" style="endArrow=open;dashed=1;html=1;fontSize=11;edgeStyle=none;rounded=0;strokeColor=#999999;fontColor=#666666;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="735" y="475" as="sourcePoint"/><mxPoint x="525" y="475" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m10" value="plan 저장 · awaiting_approval · msg(plan)" style="endArrow=classic;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="525" y="515" as="sourcePoint"/><mxPoint x="1155" y="515" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m11" value="SessionDetailResponse" style="endArrow=open;dashed=1;html=1;fontSize=11;edgeStyle=none;rounded=0;strokeColor=#999999;fontColor=#666666;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="525" y="555" as="sourcePoint"/><mxPoint x="315" y="555" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m12" value="PUT /plan (편집, 옵션)" style="endArrow=classic;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="315" y="600" as="sourcePoint"/><mxPoint x="525" y="600" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m13" value="3. [승인] 클릭" style="endArrow=classic;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="105" y="640" as="sourcePoint"/><mxPoint x="315" y="640" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m14" value="POST /plan/approve" style="endArrow=classic;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="315" y="680" as="sourcePoint"/><mxPoint x="525" y="680" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m15" value="status = approved" style="endArrow=classic;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="525" y="720" as="sourcePoint"/><mxPoint x="1155" y="720" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m16" value="4. [조사 실행] 클릭" style="endArrow=classic;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="105" y="765" as="sourcePoint"/><mxPoint x="315" y="765" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m17" value="POST /sessions/{id}/run" style="endArrow=classic;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="315" y="805" as="sourcePoint"/><mxPoint x="525" y="805" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m18" value="asyncio.create_task(_run_agent_loop)" style="endArrow=classic;html=1;fontSize=11;rounded=0;verticalAlign=middle;strokeColor=#d79b00;fontColor=#b07000;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="525" y="845" as="sourcePoint"/><mxPoint x="525" y="875" as="targetPoint"/><Array as="points"><mxPoint x="580" y="845"/><mxPoint x="580" y="875"/></Array></mxGeometry></mxCell>
        <mxCell id="m19" value="202 Accepted (즉시 반환)" style="endArrow=open;dashed=1;html=1;fontSize=11;edgeStyle=none;rounded=0;strokeColor=#999999;fontColor=#666666;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="525" y="885" as="sourcePoint"/><mxPoint x="315" y="885" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m20" value="GET /sessions/{id}/stream (SSE)" style="endArrow=classic;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="315" y="925" as="sourcePoint"/><mxPoint x="525" y="925" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m21" value="text/event-stream (과거 재생 + 실시간 tail)" style="endArrow=classic;dashed=1;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="525" y="965" as="sourcePoint"/><mxPoint x="315" y="965" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m22" value="event: step_start {index,title}" style="endArrow=classic;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="525" y="1035" as="sourcePoint"/><mxPoint x="1365" y="1035" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m23" value="stream_chat [_AGENT_SYSTEM + 스텝 컨텍스트]" style="endArrow=classic;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="525" y="1075" as="sourcePoint"/><mxPoint x="735" y="1075" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m24" value="텍스트 델타 (스트리밍)" style="endArrow=classic;dashed=1;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="735" y="1115" as="sourcePoint"/><mxPoint x="525" y="1115" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m25" value="event: step_delta (델타마다 push)" style="endArrow=classic;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="525" y="1155" as="sourcePoint"/><mxPoint x="1365" y="1155" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m26" value="정규식 검출: &#x27;SEARCH: &lt;query&gt;&#x27;" style="endArrow=classic;html=1;fontSize=11;rounded=0;verticalAlign=middle;strokeColor=#d79b00;fontColor=#b07000;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="525" y="1195" as="sourcePoint"/><mxPoint x="525" y="1225" as="targetPoint"/><Array as="points"><mxPoint x="580" y="1195"/><mxPoint x="580" y="1225"/></Array></mxGeometry></mxCell>
        <mxCell id="m27" value="event: search {query}" style="endArrow=classic;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="525" y="1235" as="sourcePoint"/><mxPoint x="1365" y="1235" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m28" value="web_search(query)" style="endArrow=classic;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="525" y="1275" as="sourcePoint"/><mxPoint x="945" y="1275" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m29" value="검색 결과 [{title,url,content}]" style="endArrow=open;dashed=1;html=1;fontSize=11;edgeStyle=none;rounded=0;strokeColor=#999999;fontColor=#666666;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="945" y="1315" as="sourcePoint"/><mxPoint x="525" y="1315" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m30" value="event: search_results {count}" style="endArrow=classic;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="525" y="1355" as="sourcePoint"/><mxPoint x="1365" y="1355" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m31" value="결과 주입 → stream_chat 재호출 (≤3회/스텝)" style="endArrow=classic;html=1;fontSize=11;rounded=0;verticalAlign=middle;strokeColor=#d79b00;fontColor=#b07000;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="525" y="1395" as="sourcePoint"/><mxPoint x="525" y="1425" as="targetPoint"/><Array as="points"><mxPoint x="580" y="1395"/><mxPoint x="580" y="1425"/></Array></mxGeometry></mxCell>
        <mxCell id="m32" value="INSERT msg(step_progress)" style="endArrow=classic;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="525" y="1435" as="sourcePoint"/><mxPoint x="1155" y="1435" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m33" value="event: step_done" style="endArrow=classic;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="525" y="1475" as="sourcePoint"/><mxPoint x="1365" y="1475" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m34" value="event: final_start" style="endArrow=classic;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="525" y="1540" as="sourcePoint"/><mxPoint x="1365" y="1540" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m35" value="stream_chat [_FINAL_SYSTEM + 전체 스텝 요약]" style="endArrow=classic;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="525" y="1580" as="sourcePoint"/><mxPoint x="735" y="1580" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m36" value="최종 보고서 델타 (스트리밍)" style="endArrow=classic;dashed=1;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="735" y="1620" as="sourcePoint"/><mxPoint x="525" y="1620" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m37" value="event: final_delta (델타마다 push)" style="endArrow=classic;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="525" y="1660" as="sourcePoint"/><mxPoint x="1365" y="1660" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m38" value="INSERT msg(final) · status=completed" style="endArrow=classic;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="525" y="1700" as="sourcePoint"/><mxPoint x="1155" y="1700" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m39" value="event: final_done · completed (_finish_live)" style="endArrow=classic;html=1;fontSize=11;edgeStyle=none;rounded=0;verticalAlign=middle;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="525" y="1740" as="sourcePoint"/><mxPoint x="1365" y="1740" as="targetPoint"/></mxGeometry></mxCell>
        <mxCell id="m40" value="&#x27;completed&#x27; 수신 → SSE 종료, 세션 새로고침" style="endArrow=classic;html=1;fontSize=11;rounded=0;verticalAlign=middle;strokeColor=#d79b00;fontColor=#b07000;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="315" y="1785" as="sourcePoint"/><mxPoint x="315" y="1815" as="targetPoint"/><Array as="points"><mxPoint x="370" y="1785"/><mxPoint x="370" y="1815"/></Array></mxGeometry></mxCell>
        <mxCell id="m41" value="스트림 종료 (None sentinel)" style="endArrow=open;dashed=1;html=1;fontSize=11;edgeStyle=none;rounded=0;strokeColor=#999999;fontColor=#666666;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="1365" y="1825" as="sourcePoint"/><mxPoint x="315" y="1825" as="targetPoint"/></mxGeometry></mxCell>
      </root>
    </mxGraphModel>
      </diagram>
    </mxfile>
```

---

## 7. 에이전트 루프 상세 (`_run_agent_loop` / `_execute_step`)

프롬프트 기반 **tool-use 프로토콜**: 네이티브 function-calling이 아니라, 시스템 프롬프트로 `SEARCH: <쿼리>` 형식의 줄을 출력하도록 지시(`_AGENT_SYSTEM`)하고 백엔드가 정규식으로 감지(`re.search(r"SEARCH:\s*(.+?)(?:\n|$)", chunk_text)`)해 검색을 수행한다.

### 스텝 루프 (`_execute_step`)
1. 이전 스텝 결과(`step_summaries`)를 컨텍스트로 누적해 user 메시지 구성.
2. `stream_chat` 으로 LLM 토큰을 스트리밍 — **델타마다** `step_delta` 이벤트 push.
3. 응답 내 `SEARCH:` 라인이 있고 `searches < _MAX_SEARCHES_PER_STEP`(=3)이면:
   - `search` 이벤트 → `web_search(query)` (Tavily) → `search_results` 이벤트
   - assistant 산출물 + 검색결과를 messages에 append 후 **다시 스트리밍**(continue)
4. 더 이상 검색이 없으면 루프 종료 → 산출물을 `msg(step_progress)`로 저장.

### 최종 보고서
- 모든 스텝 완료 후 `_FINAL_SYSTEM` 으로 전체 스텝 요약을 종합해 마크다운 보고서 스트리밍(`final_delta`).
- `msg(final)` 저장 · `status=completed`.

### 중단/에러 처리
- `asyncio.CancelledError`(삭제/취소): `status`를 `approved`로 복원 후 `cancelled` 이벤트. 정상 종료로 처리(재전파 안 함).
- 기타 예외: `status` 복원 후 `error` 이벤트.
- `finally`에서 항상 `_finish_live()` 호출 → 조회 스트림 종료.

---

## 8. 스트리밍 / SSE

### 이벤트 타입
| event | data | 시점 |
|---|---|---|
| `step_start` | `{index, title}` | 스텝 시작 |
| `step_delta` | `{index, delta}` | LLM 토큰(실시간) |
| `search` | `{index, query}` | 검색 요청 직전 |
| `search_results` | `{index, count}` | 검색 완료 |
| `step_done` | `{index}` | 스텝 종료 |
| `final_start` | `{}` | 최종 보고서 시작 |
| `final_delta` | `{delta}` | 최종 보고서 토큰(실시간) |
| `final_done` | `{}` | 최종 보고서 종료 |
| `completed` | `{status}` | 전체 완료 |
| `cancelled` | `{}` | 취소 |
| `error` | `{message}` | 에러 |

### 인메모리 이벤트 스토어 (`_live`)
```
session_id -> { events: [sse_str, ...],   # 전체 이벤트 히스토리(과거 재생용)
                queues:  [asyncio.Queue],  # 활성 구독자
                done: bool }
```
- `_append_event`: 이벤트를 `events`에 append + 모든 구독자 큐에 put.
- `_subscribe`(GET /stream): **과거 이벤트를 먼저 재생**한 뒤 큐를 등록해 실시간 tail. 덕분에 페이지를 닫았다 다시 들어와도 진행 상황을 이어볼 수 있다. `done=True`면 재생 후 종료.
- `_finish_live`: `done=True` 세팅 + 큐에 `None` sentinel put → 제너레이터 종료.

### 클라이언트 처리 (`page.js` `openStream`)
`step_delta`/`final_delta`는 누적 버퍼(`stepBuf`)로 raw 텍스트를 실시간 표시하고, `completed`/`cancelled` 수신 시 스트림을 닫고 세션을 새로고침해 DB 영속 결과(마크다운 렌더링)로 전환한다(불완전 마크다운 레이아웃 점프 방지, FR-I09).

---

## 9. 백그라운드 실행 · 복구

- **HTTP와 무관**: `POST /run`은 `asyncio.create_task(_run_agent_loop)`로 루프를 띄우고 202를 즉시 반환. 루프는 요청 컨텍스트 밖에서 자체 DB 세션(`AsyncSessionLocal`)으로 동작.
- **재시작 복구** (`main.py` lifespan): 백그라운드 태스크는 서버 재시작 시 소실되므로, 시작 시 `running` 상태를 `approved`로 되돌려 재실행 가능하게 함.
- **실행 중 삭제** (`DELETE`): `_cancel_task`(태스크 취소) → `_clear_live`(버퍼 정리·구독자 종료) → 행 삭제. 프론트는 진행 중 스트림을 중단.
- **중복 실행 방지**: 이미 `running` + 활성 태스크면 400.

> 제약: 단일 서버 프로세스 단위. 다중 워커/서버 환경에서는 인메모리 스토어가 공유되지 않으므로 별도 백엔드(Redis Pub/Sub 등)가 필요하다.

---

## 10. 권한 / 보안

- `require_permission("deep_research", "read"|"create")` — `사용자` 역할 이상(사용자·프리미엄·운영자)이 시드로 권한 보유(FR-I02).
- LLM 제공자 API 키는 **운영자가 모델 관리 UI에서 등록**해 Fernet 암호화로 DB(`llm_providers.api_key_encrypted`)에 저장되며, 백엔드에서 복호화해 메모리에서만 사용한다. 평문은 클라이언트·감사 로그에 노출되지 않는다(NFR-S10/S11). Tavily 웹 검색 키(`TAVILY_API_KEY`)만 환경변수로 주입된다.
- 모든 세션 접근은 `session.account_id == account.id` 로 소유자 검증(타인 세션 403).

---

## 11. 환경변수 / 설정

| 변수 | 용도 | 비고 |
|---|---|---|
| `LLM_KEY_ENCRYPTION_KEY` | LLM API 키 암호화 마스터 키(Fernet) | UI 등록 키를 암호화. 운영 필수 |
| `ABCLAB_BASE_URL` | ABCLab 기본 base URL | `/v1` 제외. 기본 `https://api.abclab.ktds.com` |
| `TAVILY_API_KEY` | 웹 검색(Tavily) | 미설정 시 검색 건너뛰고 LLM만으로 진행 |

LLM 제공자별 API 키는 환경변수가 아닌 **모델 관리 메뉴**(FR-J)에서 항목별로 등록한다. `GET /models`는 등록 모델과 제공자 API 실사용가능 모델의 **교집합**만 노출한다(조회 실패 시 검증 생략).
