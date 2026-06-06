// 로컬 개발용 환경변수 (Docker entrypoint가 없는 환경에서 사용)
// 실제 값은 web/.env.local 또는 이 파일에 직접 작성
window.__ENV__ = {
  NEXT_PUBLIC_API_URL: "http://localhost:8000",
};
