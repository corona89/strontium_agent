# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Structure

- `api/` — FastAPI 기반 Python API 서버
- `web/` — Next.js 웹 프론트엔드 (JSX, TailwindCSS)

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

### 컴포넌트 구조

```
components/
├── ui/          # 도메인 무관한 순수 UI 컴포넌트 (Button, Input, Modal 등). props만으로 동작, 상태 없음
└── [feature]/   # 기능별 컴포넌트. 스토어나 API와 연결 가능
```
