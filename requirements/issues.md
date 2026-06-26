# 미구현 기능 및 알려진 이슈

## TODO (미구현)

- ~~**TODO-01** 회원가입 UI가 없다.~~ → **해결**: `api.accounts` 네임스페이스 추가(`lib/api.js`), `/register` 페이지 생성, `proxy.js` 공개 경로에 `/register` 추가, 로그인 페이지에 회원가입 링크 추가.
- ~~**TODO-02** Google OAuth가 구현되지 않았다.~~ → **해결**: 백엔드 `routers/oauth.py` 추가(`GET /auth/google`, `GET /auth/google/callback`), state 기반 CSRF 방어, 계정 자동 연결/생성, `httpx` 의존성 추가, 프론트엔드 Google 버튼 활성화 및 OAuth 에러 처리. 사용하려면 `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` 환경변수 설정 필요.
- ~~**TODO-03** 홈 페이지(`/`)가 "Hello World" 자리표시자 상태이다.~~ → **해결**: 사용자 환영 메시지 + 계정 정보 카드 + 빠른 작업 카드를 포함한 대시보드 홈 페이지로 교체.
- ~~**TODO-04** `/settings` 페이지가 존재하지 않는다.~~ → **해결**: `/settings` 페이지 추가 — 계정 정보 조회, 닉네임 변경, 비밀번호 변경, 계정 비활성화(확인 다이얼로그 포함) 기능.
- ~~**TODO-05** TopNav 프로필 메뉴 항목에 핸들러가 없다.~~ → **해결**: 프로필 메뉴 클릭 시 `/settings`로 이동하도록 `onClick` 핸들러 추가.
- ~~**TODO-06** DB 마이그레이션(Alembic)이 없다.~~ → **해결**: `alembic` 패키지 추가, async 템플릿으로 초기화, `env.py`를 프로젝트 설정(`settings.DATABASE_URL`, `Base.metadata`)에 연결, 초기 스키마 마이그레이션 생성. SQLite `render_as_batch` 적용.
- ~~**TODO-07** 로그인/회원가입 rate limiting이 없다.~~ → **해결**: `slowapi` 패키지 추가, `core/limiter.py` 설정, 로그인 5회/분·회원가입 3회/분 제한 적용.
- ~~**TODO-08** 권한 관리(RBAC) 시스템을 구현한다 (FR-F, FR-G, FR-H 참조).~~ → **해결**:
  - 백엔드: `Function`, `Role`, `RoleFunction`, `AccountRole`, `AuditLog` 5개 모델 추가 + Alembic 마이그레이션.
  - 시드: `home`, `settings`, `users`, `roles`, `audit` 기능 / 운영자·프리미엄 사용자·사용자 역할 / `cpar2002@gmail.com` 회원가입 시 운영자 자동 부여.
  - 권한 확인: `require_permission(function, action)` 의존성, `/auth/me` 응답에 `roles`/`permissions` 포함.
  - 감사 로그: `log_action()` 헬퍼, 회원가입/OAuth/본인 변경/운영자 액션 기록.
  - API: `/roles`(CRUD + 매핑), `/functions`(CRUD), `/admin/users`(목록/역할변경/비밀번호초기화/삭제), `/admin/audit-logs`.
  - 프론트엔드: 동적 Sidebar(권한 기반), `/users`·`/roles`·`/audit-logs` 페이지, `api.roles`/`api.functions`/`api.admin` 네임스페이스.

## ISSUE (보안/결함)

- ~~**ISSUE-01** `PATCH /accounts/{id}`와 `DELETE /accounts/{id}`에 인증이 없다.~~ → **해결**: 두 엔드포인트에 `Depends(get_current_account)` 추가, `current.id != account_id` 시 403 Forbidden 반환.
- ~~**ISSUE-02** `JWT_SECRET` 기본값이 insecure하여 `.env` 오버라이드에 의존한다.~~ → **해결**: `Settings`에 `model_validator` 추가 — 운영 환경(`COOKIE_SECURE=True`)에서 기본값 사용 시 `ValueError`로 앱 시작 거부, 개발 환경에서는 경고 로그 출력.

## 신규 미구현 (딥 리서치 에이전트 / 모델 관리)

- **TODO-09** 딥 리서치 에이전트 기능을 구현한다 (FR-I 참조).
  - 백엔드: 딥 리서치 세션/메시지 데이터 모델, 플랜 생성·승인·편집 API, 승인된 플랜 기반 에이전트 루프(웹 검색 도구 포함), 결과 스트리밍, LLM 호출(Ollama Cloud / OpenCode Zen) 연동.
  - 프론트엔드: `/deep-research` 채팅 UI, 플랜 편집/승인 인터랙션, 세션 단위 모델 선택, 중간/최종 결과 스트리밍 렌더링, `deep_research.read` 권한 제어.
- **TODO-10** 모델 관리 기능을 구현한다 (FR-J 참조).
  - 백엔드: `llm_providers` 테이블 + Alembic 마이그레이션, API 키 암호화 저장(NFR-S10), `GET/POST/PATCH/DELETE /models/providers` API(운영자 `models.*`), 응답 키 마스킹(NFR-S11), 감사 로그 기록.
  - 프론트엔드: `/models` 관리 페이지(운영자 전용), 제공자/모델 CRUD UI, `api.models` 네임스페이스 추가.
- **TODO-11** 회원가입(이메일/OAuth) 시 기본 "사용자" 역할 자동 부여(FR-F26). 기존 구현은 `cpar2002@gmail.com`에만 운영자를 부여하고 일반 가입자에게 역할을 할당하지 않는 gap. `ensure_default_role` 시드 헬퍼 추가 후 `account.py`/`oauth.py`에 연결.
