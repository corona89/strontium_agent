#!/bin/sh
set -e

# 런타임 환경변수를 클라이언트에서 읽을 수 있도록 public/env-config.js 생성
# NEXT_PUBLIC_으로 시작하는 변수를 추가하려면 이 파일에 직접 작성
cat > /app/public/env-config.js << EOF
window.__ENV__ = {
  NEXT_PUBLIC_API_URL: "${NEXT_PUBLIC_API_URL:-}",
};
EOF

exec "$@"
