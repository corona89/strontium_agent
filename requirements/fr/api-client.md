# FR-E. API 클라이언트

- **FR-E01** 모든 API 요청은 `credentials: 'include'`로 쿠키를 전송한다.
- **FR-E02** 401 응답 시 자동으로 `/auth/refresh`를 호출 후 원 요청을 재시도한다.
- **FR-E03** 동시 다발 401은 단일 refresh Promise로 중복 제거한다.
- **FR-E04** refresh 실패 시 `/login`로 강제 이동한다.
