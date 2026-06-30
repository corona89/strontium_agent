#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$ROOT/.run"

echo "[stop] strontium_agent 서버 종료 중..."

# 1) start.sh 으로 띄운 프로세스(PID 파일)와 자식 트리를 함께 종료
kill_pid_file() {
  local name="$1" file="$2"
  [[ -f "$file" ]] || return 0
  local pid
  pid="$(cat "$file" 2>/dev/null || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    pkill -P "$pid" 2>/dev/null || true
    kill "$pid" 2>/dev/null || true
    sleep 1
    kill -9 "$pid" 2>/dev/null || true
    echo "  - $name 종료 (PID $pid)"
  fi
  rm -f "$file"
}

kill_pid_file "ww-api" "$PID_DIR/ww-api.pid"
kill_pid_file "ww-web" "$PID_DIR/ww-web.pid"

# 2) 폴백: 포트 3000/8000 점유 프로세스(수동 실행/잔류/고아) 종료
kill_port() {
  local port="$1" name="$2"
  local pids
  pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  [[ -n "$pids" ]] || return 0
  echo "$pids" | while read -r pid; do
    kill "$pid" 2>/dev/null || true
    echo "  - $name PID $pid (포트 $port)"
  done
  sleep 1
  echo "$pids" | while read -r pid; do
    kill -9 "$pid" 2>/dev/null || true
  done
}

kill_port 3000 "web"
kill_port 8000 "api"

# 3) 검증: 포트가 실제로 해제됐는지 확인
remain=0
for port in 3000 8000; do
  pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    echo "  - 경고: 포트 $port 에 여전히 프로세스가 남아 있습니다 (PID: $(echo "$pids" | tr '\n' ' '))"
    remain=1
  fi
done

if [[ "$remain" -eq 0 ]]; then
  echo "종료 완료."
else
  echo "일부 프로세스가 종료되지 않았습니다. 위 PID 를 수동으로 확인하세요."
fi
