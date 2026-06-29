@echo off
chcp 65001 >nul
set "ROOT=%~dp0"

echo [start] wherewindsmeet 서버 시작 (API :8000, Web :3000)
start "ww-api" /D "%ROOT%api" cmd /k "title ww-api && uv run uvicorn main:app --reload"
start "ww-web" /D "%ROOT%web" cmd /k "title ww-web && yarn dev"
echo API(http://localhost:8000) 와 Web(http://localhost:3000) 창이 각각 새로 열렸습니다.
echo 종료는 stop.bat 을 실행하세요.
