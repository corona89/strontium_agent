# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Structure

- `api/` — FastAPI 기반 Python API 서버
- `web/` — Next.js 웹 프론트엔드 (JSX, TailwindCSS)

## Database (`db/`)

SQLite를 사용한다. DB 파일은 `db/app.db`에 생성된다. (`.gitignore`로 제외됨)

ORM은 SQLAlchemy (비동기, `aiosqlite` / `aiomysql`)를 사용한다.

- DB 종류는 `api/.env`의 `DATABASE_URL`로 결정된다 (`.env`는 git 제외, `.env.example` 참고)
- 개발: `sqlite+aiosqlite:///...` → NullPool
- 운영: `mysql+aiomysql://...` → 커넥션 풀 (`pool_size=10`, `max_overflow=20`)
- 엔진 분기 로직: `api/database/connection.py`
- 앱 설정: `api/core/config.py` (pydantic-settings)
- `Base` — 모든 모델의 베이스 클래스
- `get_db` — FastAPI dependency로 사용하는 세션 제공자

## API 스키마 (`openapi.json`)

루트의 `openapi.json`은 FastAPI가 생성한 OpenAPI 3.1 스키마다.

- **웹 프론트엔드 작업 시 반드시 이 파일을 읽고** 엔드포인트 경로·요청/응답 스키마를 확인한다.
- API가 변경될 때마다 아래 명령으로 갱신한다:

```bash
cd api
uv run python -c "import json; from main import app; open('../openapi.json','w').write(json.dumps(app.openapi(), ensure_ascii=False, indent=2))"
```

## API (`api/`)

Python 3.14, FastAPI, uv 패키지 관리자를 사용한다.

### 패키지 관리

```bash
cd api
uv add <package>       # 패키지 추가
uv remove <package>    # 패키지 제거
uv sync                # 의존성 동기화
```

### 실행

```bash
cd api
uv run uvicorn main:app --reload
```

## Web (`web/`)

Next.js 16 (App Router), JSX, TailwindCSS, ESLint, Zustand을 사용한다. 패키지 관리자는 yarn.

### 패키지 관리

```bash
cd web
yarn add <package>     # 패키지 추가
yarn remove <package>  # 패키지 제거
```

### 실행

```bash
cd web
yarn dev    # 개발 서버 (http://localhost:3000)
yarn build  # 프로덕션 빌드
yarn lint   # ESLint
```

### 상태 관리

전역 클라이언트 상태는 Zustand를 사용한다. 스토어는 `store/` 디렉토리에 작성한다.

### 런타임 환경변수

Next.js는 빌드 시점에 환경변수를 번들에 포함시키는 문제가 있다. Docker 이미지 재빌드 없이 환경변수를 제어하기 위해 다음 구조를 사용한다.

- `web/docker-entrypoint.sh` — 컨테이너 시작 시 `public/env-config.js` 생성 (`window.__ENV__` 주입)
- `web/public/env-config.js` — 로컬 개발용 fallback (git 추적)
- `web/lib/env.js`의 `getEnv(key)` — 서버는 `process.env`, 클라이언트는 `window.__ENV__`에서 읽음
- 새 환경변수 추가 시 `docker-entrypoint.sh`에도 추가 필요

### Docker

```bash
# api
docker build -t strontium_agent-api ./api

# web
docker build -t strontium_agent-web ./web
docker run -e NEXT_PUBLIC_API_URL=https://api.example.com strontium_agent-web
```

### UI 컴포넌트 라이브러리

shadcn/ui (v4.10.0)를 사용한다. 컴포넌트를 소스코드로 직접 추가하는 방식이다.

```bash
cd web
npx shadcn@latest add <component>  # 예: button, input, dialog
```

컴포넌트는 `components/ui/`에 생성된다. 테마 변수는 `app/globals.css`에 정의되어 있다.

### 컴포넌트 구조

```
components/
├── ui/          # 도메인 무관한 순수 UI 컴포넌트 (Button, Input, Modal 등). props만으로 동작, 상태 없음
└── [feature]/   # 기능별 컴포넌트. 스토어나 API와 연결 가능
```
