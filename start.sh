#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$ROOT/.run"
mkdir -p "$PID_DIR"

# OS 환경변수 OLLAMA_API_KEY(스테일 키)가 .env 의 올바른 키를 덮어쓰지 않도록 이 세션에서는 비움
unset OLLAMA_API_KEY

echo "[start] strontium_agent 서버 시작 (API :8000, Web :3000)"

start_proc() {
  local name="$1" cmd_dir="$2" cmd="$3" port="$4"
  local pid_file="$PID_DIR/$name.pid" log_file="$PID_DIR/$name.log"
  if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    echo "  - $name 이미 실행 중 (PID $(cat "$pid_file"))"
    return
  fi
  if [[ -n "$(lsof -ti tcp:"$port" 2>/dev/null || true)" ]]; then
    echo "  - $name 시작 건너뜀: 포트 $port 가 이미 사용 중입니다. stop.sh 로 정리 후 재시도하세요."
    return
  fi
  # exec 로 서브쉘을 실제 프로세스로 치환해야 $! 가 서버 PID 자체가 됨.
  # eval 을 쓰면 서브쉘이 자식을 fork 하므로 PID 파일이 서버가 아닌 서브쉘을 가리키게 됨.
  (cd "$cmd_dir" && exec $cmd) > "$log_file" 2>&1 &
  echo $! > "$pid_file"
  echo "  - $name 시작 (PID $!, 로그: $log_file)"
}

start_proc "ww-api" "$ROOT/api" "uv run uvicorn main:app --reload" 8000
start_proc "ww-web" "$ROOT/web" "yarn dev" 3000

echo "API(http://localhost:8000), Web(http://localhost:3000)"
echo "종료는 stop.sh 를 실행하세요."
echo "로그 확인: tail -f $PID_DIR/ww-api.log $PID_DIR/ww-web.log"
