# FR-H. 프론트엔드 — 관리자 페이지

- **FR-H01** `/users` 페이지 — 사용자 목록 테이블(이메일, 닉네임, 역할, 상태). 행별 액션:
  - 역할 변경: 역할 셀렉트(다중 선택) → `PATCH /admin/users/{id}/roles`.
  - 비밀번호 초기화: 확인 다이얼로그 → `POST /admin/users/{id}/reset-password` → 임시 비밀번호를 모달로 표시(복사 가능).
  - 삭제(비활성화): 확인 다이얼로그 → `DELETE /admin/users/{id}`.
  - 각 액션은 `users` 권한(C/U/D)에 따라 버튼 활성화/비활성화.
- **FR-H02** `/roles` 페이지 — 탭 2개 구성:
  - **역할 탭**: 역할 목록 + 추가/삭제 버튼. 각 역할별 Function×CRUD 매트릭스(체크박스 그리드)를 표시하고 저장(`PUT /roles/{id}/functions`). `is_system` 역할은 삭제 버튼 비활성화.
  - **기능 탭**: 기능 목록 + 추가/수정/삭제.
  - 역할 페이지 전체는 `roles.read` 권한이 있어야 접근 가능. 각 CRUD 액션은 해당 권한에 따라 제어.
- **FR-H03** `/audit-logs` 페이지 — 감사 로그 테이블(시간, 수행자 이메일, 대상 이메일, 액션, 상세). 최신순 정렬, 페이지네이션. `audit.read` 권한 필요.
- **FR-H04** `lib/api.js`에 `api.roles`, `api.functions`, `api.admin` 네임스페이스를 추가한다.
- **FR-H05** `useAuthStore`의 `user` 객체에 `permissions`를 저장하여 Sidebar 동적 렌더링과 페이지 내 권한 제어에 사용한다.
