/**
 * 환경변수 접근 유틸리티
 *
 * - 서버(SSR): process.env에서 직접 읽음
 * - 클라이언트: docker-entrypoint.sh가 생성한 window.__ENV__에서 읽음
 *   (빌드 타임이 아닌 런타임에 주입되므로 Docker 이미지 재빌드 없이 변경 가능)
 *
 * 사용 예: getEnv("NEXT_PUBLIC_API_URL")
 */
export function getEnv(key) {
  if (typeof window !== "undefined") {
    return window.__ENV__?.[key] ?? process.env[key];
  }
  return process.env[key];
}
