# FR-A. 인증 (Authentication)

- **FR-A01** 사용자는 이메일과 비밀번호로 로그인할 수 있다 (`POST /auth/login`).
- **FR-A02** 로그인 성공 시 서버는 httpOnly 쿠키로 access_token(15분)과 refresh_token(7일)을 설정한다 (204 응답, 본문 없음).
- **FR-A03** 인증된 사용자는 `/auth/me`로 현재 계정 정보를 조회할 수 있다 (`GET /auth/me`). 응답은 계정 기본 정보 외에 역할(`roles`)과 권한 매트릭스(`permissions`: 각 기능별 CRUD 비트)를 포함한다.
- **FR-A04** refresh_token 쿠키로 만료된 access_token을 갱신할 수 있다 (`POST /auth/refresh`). 갱신 시 기존 refresh_token은 삭제되고 새 토큰이 발급된다(토큰 회전).
- **FR-A05** 사용자는 로그아웃할 수 있다 (`POST /auth/logout`). 서버는 refresh_token DB 레코드를 삭제하고 두 쿠키를 제거한다.
- **FR-A06** 로그인 실패 시 이메일/비밀번호 불일치, 비활성 계정, SSO 전용 계정 모두 동일한 에러 메시지를 반환한다(열거 공격 방지).
