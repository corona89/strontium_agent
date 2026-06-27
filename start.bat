@echo off
chcp 65001 >nul
set "ROOT=%~dp0"

REM OS 환경변수 OLLAMA_API_KEY(스테일 키)가 .env 의 올바른 키를 덮어쓰지 않도록 이 세션에서는 비움
set "OLLAMA_API_KEY="

echo [start] wherewindsmeet 서버 시작 (API :8000, Web :3000)
start "ww-api" /D "%ROOT%api" cmd /k "title ww-api && uv run uvicorn main:app --reload"
start "ww-web" /D "%ROOT%web" cmd /k "title ww-web && yarn dev"
echo API(http://localhost:8000) 와 Web(http://localhost:3000) 창이 각각 새로 열렸습니다.
echo 종료는 stop.bat 을 실행하세요.
