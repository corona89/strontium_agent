# Strontium Agent — Desktop (Windows)

Next.js(Frontend) + FastAPI(Backend) + Electron(Shell) 을 단일 Windows 설치 앱으로 번들.

## 아키텍처

```
Strontium Agent Setup.exe (NSIS)
└─ 설치 후 실행 시:
   ├─ strontium_agent.exe  (PyInstaller 로 번들된 FastAPI, 127.0.0.1:8000)
   ├─ node server.js     (Next.js standalone, 127.0.0.1:3000)
   └─ Electron BrowserWindow  (127.0.0.1:3000 을 로드)
```

사용자 데이터는 `%APPDATA%\StrontiumAgent\data\` (또는 Electron userData 경로)에 저장:
- `app.db`         — SQLite 데이터베이스
- `wiki/`          — 업로드된 위키 파일
- `config.json`    — 자동 생성된 JWT_SECRET, LLM_KEY_ENCRYPTION_KEY (절대 삭제 금지 — LLM 키 복호화 불가)

## 개발 모드 실행

```powershell
cd desktop
yarn install
yarn dev
```

`SA_DEV=1` 환경변수가 설정되면 Electron은 번들된 빌드 대신 모노레포 루트의 `api/`, `web/` 을 직접 실행합니다 (`uv run uvicorn`, `yarn dev`). 단일 사용자 자동 로그인은 동일하게 동작.

## 인스톨러 빌드

```powershell
cd desktop
yarn build:all
# 또는 단계별:
#   yarn build:api   → ../api-dist/strontium_agent/
#   yarn build:web   → ../web-out/
#   yarn dist        → desktop/dist/*Setup*.exe
```

## 자동 로그인 동작

1. FastAPI 시작 시 `LOCAL_MODE=true` → `local@strontium.local` 단일 운영자 계정 자동 시드
2. Electron main 이 두 서버 헬스체크 후 `POST /local/bootstrap` 호출
3. 받은 access/refresh 토큰을 `localhost:3000` 도메인에 httpOnly 쿠키로 주입
4. BrowserWindow 에서 Next.js 로드 → `proxy.js` 미들웨어가 쿠키 감지 → 홈으로 직행

## 커스터마이징

- **아이콘 교체**: `build/icon.ico` (256x256, 멀티레졸루션 ICO) 추가 후 `electron-builder.yml` 에서 `icon:` 라인 주석 해제
- **포트 변경**: `main.js` 상단 `API_PORT`/`WEB_PORT` (단, FastAPI 도 같은 포트여야 함 — `run_local.py` 도 수정)
- **데이터 위치 변경**: 실행 시 `DATA_DIR` 환경변수로 오버라이드

## 주의사항

- 코드사이닝 미적용 상태 — Windows SmartScreen 이 "인식되지 않은 앱" 경고 표시. 사용자가 **추가 정보** → **실행** 클릭 필요
- 포트 3000/8000 이 이미 사용 중이면 앱 시작 실패 (에러 다이얼로그 표시)
- Google OAuth 는 `LOCAL_MODE=true` 에서 의도적으로 비활성화됨 (web redirect URI 한계)
