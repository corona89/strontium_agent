# NFR-T. 기술 스택 (Tech Stack)

- **NFR-T01** 백엔드: Python 3.14, FastAPI, SQLAlchemy 2.0(async), uv 패키지 관리.
- **NFR-T02** 프론트엔드: Next.js 16(App Router, JSX), React 19, TailwindCSS v4, Zustand v5, shadcn/ui v4.
- **NFR-T03** 프론트엔드 런타임 환경변수는 `docker-entrypoint.sh` → `env-config.js` → `window.__ENV__` 체인으로 빌드와 분리하여 주입한다.
