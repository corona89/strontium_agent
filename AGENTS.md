# AGENTS.md

Monorepo: `api/` (FastAPI, Python 3.14, uv) + `web/` (Next.js 16, JSX, yarn) + `desktop/` (Electron 셸, Windows 설치 앱 번들링). Always `cd` into the package before running commands.

## Commands

### Backend (`api/`)
```bash
uv run uvicorn main:app --reload          # dev server (port 8000)
uv sync                                    # install deps
uv add <pkg> / uv remove <pkg>             # manage deps
```

### Frontend (`web/`)
```bash
yarn dev          # dev server (port 3000)
yarn build        # prod build (verifies all pages compile)
yarn lint         # ESLint
```

### Desktop (`desktop/`)
```bash
yarn install      # electron, electron-builder, wait-on 설치
yarn dev          # SA_DEV=1 — 번들 대신 모노레포 api/·web/ 직접 실행
yarn build:all    # 전체 빌드 → desktop/dist/*Setup*.exe (NSIS 인스톨러)
# 단계별 빌드:
yarn build:api    # PyInstaller → ../api-dist/strontium_agent/
yarn build:web    # Next standalone 빌드 → ../web-out/
yarn dist         # electron-builder (api-dist/·web-out/ 필요)
```

### OpenAPI regeneration (run after changing API endpoints)
```bash
cd api && uv run python -c "import json; from main import app; open('../openapi.json','w').write(json.dumps(app.openapi(), ensure_ascii=False, indent=2))"
```
The web frontend reads `openapi.json` at the repo root to understand API schemas. Regenerate after endpoint changes.

## Critical gotchas

### Next.js 16 is not standard Next.js
`web/AGENTS.md` has the full warning. Key differences an agent will miss:
- **`proxy.js` is the middleware** — Next.js 16 renamed `middleware.ts` → `proxy.ts` exporting `function proxy()` (not `middleware`). Route guarding lives in `web/proxy.js`.
- **`useSearchParams` requires a `<Suspense>` boundary** in production builds or the build fails. See `web/app/login/page.js` for the pattern.
- Read `web/node_modules/next/dist/docs/` before writing Next.js code if unsure.
- **JSX, not TSX** — `components.json` has `tsx: false`. All components are `.jsx`. Do not create `.tsx` files.

### React 19 lint rule: `set-state-in-effect`
`react-hooks/set-state-in-effect` flags any `setState` called synchronously in `useEffect` (including via a `load()` callback). For data-fetching effects, add `// eslint-disable-next-line react-hooks/set-state-in-effect` on the `load()` line. See `web/app/(main)/users/page.js` for the pattern.

### ESLint requires `typescript` as a devDep
`eslint-config-next` pulls `@typescript-eslint` even in JSX-only projects. `typescript` is in `devDependencies` — don't remove it or `yarn lint` breaks with "Cannot find module 'typescript'".

### Turbopack root config must not be removed
`web/next.config.mjs` has `turbopack: { root: import.meta.dirname }`. This prevents Turbopack from misidentifying `C:\Users\coron\` as the project root (caused by a stray `package-lock.json` there). Removing it breaks the dev server on Windows. See `issue.md`.

### Runtime env injection (web)
`NEXT_PUBLIC_*` vars are NOT baked at build time. The chain is: `docker-entrypoint.sh` → `public/env-config.js` (`window.__ENV__`) → `lib/env.js` `getEnv()`. When adding a new `NEXT_PUBLIC_*` var, also add it to `web/docker-entrypoint.sh` and `web/public/env-config.js` (dev fallback).

## Desktop bundle gotchas

### LOCAL_MODE 단일 사용자 자동 로그인
`api/run_local.py` 가 실행되면 `LOCAL_MODE=true` + 자동 생성 시크릿을 환경변수로 주입한 뒤 uvicorn 을 띄운다. 이 모드에서:
- `core/seed.py::seed_local_admin()` 이 `local@strontium.local` 운영자 계정을 시드 (난수 비밀번호)
- `routers/local.py` 의 `/local/bootstrap` 엔드포인트가 노출되어 Electron main 이 토큰을 받아감 (POST → access/refresh 토큰 JSON)
- `core/config.py` 의 JWT_SECRET 검증이 우회됨 (config.json 의 자동 생성 키 사용)
- **절대 웹 모드에서 `LOCAL_MODE=true` 로 설정 금지** — `/local/bootstrap` 이 인증 없이 토큰을 반환함

### PyInstaller 빌드 시 누락 모듈 주의
`api/strontium_agent.spec` 에 SQLAlchemy dialects / limits(slowapi) 를 명시해두었다. 새 동적 import 패키지를 추가하면 빌드 후 실행 시 `ModuleNotFoundError` 가 날 수 있으니 스펙의 `hiddenimports` 에 추가. `uv add` 후엔 `yarn build:api` 로 검증.

### Next.js standalone 은 .next/static 이 별도
`yarn build` 후 `.next/standalone/` 트리엔 정적 에셋이 빠져있다. `desktop/scripts/build-web.ps1` 이 `.next/static/` 과 `public/` 을 `web-out/` 으로 같이 복사함. 이 복사를 생략하면 CSS/JS 404.

### 데이터 영속성
`%APPDATA%\StrontiumAgent\data\config.json` 의 `LLM_KEY_ENCRYPTION_KEY` 가 없으면 UI에서 등록한 LLM 제공자 키를 복호화할 수 없다. 이 파일/디렉토리를 사용자가 삭제하면 위키/모델 설정이 초기화됨.

### 포트 충돌 시 앱 시작 실패
고정 포트 3000(web)/8000(api) 사용. 점유 시 스플래시 단계에서 에러 다이얼로그 표시 후 종료.

## Backend architecture notes

### DB schema: create_all + seed, not Alembic
On startup, `main.py` lifespan runs `Base.metadata.create_all` then an idempotent RBAC seed (`core/seed.py`) that inserts functions, roles, and role-function mappings. Alembic exists (`api/alembic/`) but `create_all` is the primary schema mechanism. To reset the DB: delete `db/app.db` and restart.

### Alembic autogenerate gotcha
`alembic revision --autogenerate` compares against the current DB. If the DB already has all tables, it generates an empty migration. Use a throwaway DB:
```bash
cd api
$env:DATABASE_URL="sqlite+aiosqlite:///./_alembic_tmp.db"
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "description"
Remove-Item _alembic_tmp.db
```

### Rate limiter requires `Request` param
`slowapi`'s `@limiter.limit("5/minute")` decorator requires the endpoint to have `request: Request` as a parameter (not just `db`/`body`). Login: 5/min, signup: 3/min.

### JWT_SECRET validation
The app refuses to start in production (`COOKIE_SECURE=True`) if `JWT_SECRET` is the default `"change-me-in-production"`. Override in `api/.env`.

## Auth model

- **Cookie-based, no JS-accessible tokens.** Access token (JWT, 15min) and refresh token (opaque, 7d) are httpOnly cookies. All API calls use `credentials: 'include'`.
- **Auto-refresh on 401**: `web/lib/api.js` `request()` intercepts 401, calls `/auth/refresh`, retries. Concurrent 401s share one refresh promise. Refresh failure → redirect to `/login`.
- **API client namespaces**: `api.auth`, `api.accounts`, `api.roles`, `api.functions`, `api.admin` (in `web/lib/api.js`).

## RBAC permission system

- `require_permission(function, action)` FastAPI dependency in `core/deps.py` — `action` is `create`/`read`/`update`/`delete`. Returns 403 if none of the account's roles grant the permission.
- `/auth/me` response includes `roles: string[]` and `permissions: { [function]: {create, read, update, delete} }`. The frontend Sidebar filters menu items by `permissions`.
- `cpar2002@gmail.com` is auto-assigned the 운영자 role on signup/OAuth login (`core/seed.py`).
- System roles (`is_system=True`) cannot be deleted (API returns 403).

### Audit logging
`core/audit.py` `log_action(db, actor_id, target_id, action, detail)` — call within the same DB transaction before `commit()`. Never log plaintext passwords or tokens in `detail`.

## Google OAuth setup
Requires `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `api/.env`. Without them, `/auth/google` redirects to `/login?error=oauth_not_configured`. The redirect URI (`http://localhost:8000/auth/google/callback`) must be registered in Google Cloud Console.

## Verification workflow
After changes, run in order:
1. `cd api && uv run python -c "from main import app; print('OK')"` — import check
2. Regenerate `openapi.json` (command above) if endpoints changed
3. `cd web && yarn lint` then `yarn build`

## Requirements workflow
요구사항은 `requirements/` 디렉토리에 wiki 구조로 관리된다.

- **요구사항 검색**: `requirements/reqList.md`를 먼저 참조하여 카테고리를 찾은 뒤 해당 파일을 읽는다. 모든 요구사항은 식별자(`FR-A01`, `NFR-S03` 등)로 추적 가능하다.
- **요구사항 추가**: 새 요구사항을 추가할 때는 `requirements/reqList.md`를 참고하여 적절한 카테고리 파일에 추가한다. 식별자는 해당 카테고리의 기존 최대 번호 + 1로 매긴다.
- **새 카테고리 허용**: `reqList.md`에 등록되지 않은 새로운 유형의 요구사항은 새 카테고리 파일을 생성해도 된다. 이 경우 `requirements/reqList.md`의 구조 트리와 색인 테이블에도 반드시 추가한다.
- **`plan.md` (미구현 작업 큐)**: `requirements/plan.md`는 **아직 구현되지 않았거나 진행 중인** 요구사항·계획만 보관한다. 새 기능을 계획할 때 먼저 `plan.md`에 작성한다. 완료된 요구사항은 `plan.md`에 두지 않는다.
- **완료 시 이관 + 삭제**: `plan.md`의 항목이 구현 완료되면 식별자(`FR-K01` 등)를 부여해 적절한 카테고리 파일(`fr/`·`nfr/`)로 **이관**하고, `plan.md`에서는 **삭제**한다. 즉 `plan.md`에는 완료된 항목이 남지 않는다. 이관된 카테고리는 `reqList.md` 색인/트리에 반영한다. `plan.md` 전체가 비면(보류 항목이 하나도 없으면) 파일 자체를 삭제한다.
