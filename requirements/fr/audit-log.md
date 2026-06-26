# FR-G. 감사 로그 (Audit Log)

- **FR-G01** `AuditLog` 테이블: `id`(UUID), `actor_id`(FK→accounts, SET NULL, 변경 수행자), `target_id`(FK→accounts, SET NULL, 변경 대상자), `action`(String, 액션 식별자), `detail`(Text, JSON 직렬화된 변경 전/후 스냅샷), `created_at`.
- **FR-G02** `core/audit.py`에 `log_action(db, actor_id, target_id, action, detail)` 헬퍼를 제공한다. 모든 감사 로그 기록은 이 헬퍼를 경유한다.
- **FR-G03** 다음 이벤트를 감사 로그에 기록한다:
  - `signup` — 회원가입 (`POST /accounts`). actor=self, target=self.
  - `oauth_signup` — OAuth 가입 (`GET /auth/google/callback`). actor=self, target=self.
  - `update_profile` — 본인 닉네임 변경 (`PATCH /accounts/{id}`). actor=self, target=self.
  - `change_password` — 본인 비밀번호 변경 (`PATCH /accounts/{id}`). actor=self, target=self.
  - `admin.change_role` — 운영자가 사용자 역할 변경. actor=운영자, target=대상. detail에 이전 역할/이후 역할 포함.
  - `admin.reset_password` — 운영자가 사용자 비밀번호 초기화. actor=운영자, target=대상. 평문 비밀번호는 기록하지 않음.
  - `admin.deactivate_user` — 운영자가 사용자 비활성화. actor=운영자, target=대상.
- **FR-G04** `GET /admin/audit-logs` — 감사 로그 목록 조회. 최신순 정렬, 페이지네이션 지원. (권한: `audit.read`)
