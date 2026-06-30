@echo off
chcp 65001 >nul
echo [stop] strontium_agent 서버 종료 중...

REM 1) start.bat 으로 띄운 창(제목 ww-api / ww-web)과 자식 프로세스 트리를 /T 로 함께 종료
taskkill /F /T /FI "WINDOWTITLE eq ww-api*" >nul 2>nul && echo   - ww-api 종료
taskkill /F /T /FI "WINDOWTITLE eq ww-web*" >nul 2>nul && echo   - ww-web 종료

REM 2) 폴백: 포트 3000/8000 점유 프로세스(수동 실행/잔류/고아) 종료
for /f "tokens=5" %%a in ('netstat -aon -p TCP ^| findstr ":3000 " ^| findstr LISTENING') do (
    taskkill /F /T /PID %%a >nul 2>nul && echo   - web PID %%a (포트 3000)
)
for /f "tokens=5" %%a in ('netstat -aon -p TCP ^| findstr ":8000 " ^| findstr LISTENING') do (
    taskkill /F /T /PID %%a >nul 2>nul && echo   - api PID %%a (포트 8000)
)
echo 종료 완료.
