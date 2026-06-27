# FR-F. 권한 관리 (RBAC — Role-Based Access Control)

## FR-F1. 데이터 모델

- **FR-F01** `Function`(기능) 테이블: `id`(UUID), `name`(식별자, unique), `description`, 타임스탬프. 각 메뉴/자원에 대응하는 기능 단위.
- **FR-F02** `Role`(역할) 테이블: `id`(UUID), `name`(unique), `description`, `is_system`(Boolean, True면 삭제 불가), 타임스탬프. 역할은 추가·삭제가 가능한 구조.
- **FR-F03** `RoleFunction`(역할-기능 매핑) 테이블: `id`, `role_id`(FK→roles, CASCADE), `function_id`(FK→functions, CASCADE), `can_create`/`can_read`/`can_update`/`can_delete`(Boolean, 기본 False). `(role_id, function_id)` 복합 unique. Role과 Function의 CRUD 권한을 매핑.
- **FR-F04** `AccountRole`(계정-역할 매핑) 테이블: `id`, `account_id`(FK→accounts, CASCADE), `role_id`(FK→roles, CASCADE). `(account_id, role_id)` 복합 unique. 한 계정에 여러 역할 부여 가능.
- **FR-F05** 계정이 여러 역할을 가질 때 권한은 합집합(OR)으로 계산한다. 어느 한 역할이라도 해당 action을 허용하면 접근 가능.

## FR-F2. 시드 데이터

- **FR-F06** 앱 시작 시(lifespan) 멱등 시드로 다음 기능을 등록한다: `home`, `settings`, `users`, `roles`, `audit`.
- **FR-F07** 앱 시작 시 멱등 시드로 다음 역할을 등록한다:
  - **운영자**(`is_system=True`): 모든 기능에 대해 C/R/U/D 권한 부여. 단, `roles` 기능의 `delete`는 False(역할 삭제는 허용하되 시스템 역할 자체는 보호).
  - **프리미엄 사용자**: `home`(R), `settings`(R/U/D).
  - **사용자**: `home`(R), `settings`(R/U/D).
- **FR-F08** `cpar2002@gmail.com` 계정은 앱 시작 시 시드에서 운영자 역할을 부여받는다. 해당 이메일의 계정이 없으면 시드에서 생성하지 않고, 회원가입/OAuth 로그인 시 해당 이메일이면 자동으로 운영자 역할을 부여한다.

## FR-F3. 권한 확인

- **FR-F09** `require_permission(function_name, action)` FastAPI 의존성을 제공한다. `action`은 `create`/`read`/`update`/`delete` 중 하나. 인증된 계정의 역할 중 어느 하나라도 해당 기능의 해당 action 권한이 있으면 통과, 아니면 403 Forbidden.
- **FR-F10** `/auth/me` 응답에 `roles`(역할명 배열)와 `permissions`(기능명 → {create, read, update, delete} 객체)를 포함한다. 프론트엔드는 이 정보로 사이드바 메뉴와 페이지 접근을 제어한다.

## FR-F4. 역할 관리 API (`/roles` — `roles` 기능 권한 필요)

- **FR-F11** `GET /roles` — 역할 목록 조회. 각 역할에 연결된 기능-CRUD 매핑을 포함. (권한: `roles.read`)
- **FR-F12** `POST /roles` — 역할 생성. `name`, `description` 입력. (권한: `roles.create`)
- **FR-F13** `PATCH /roles/{id}` — 역할의 `name`/`description` 수정. (권한: `roles.update`)
- **FR-F14** `DELETE /roles/{id}` — 역할 삭제. `is_system=True`인 역할은 403으로 거부. 삭제 시 연결된 `RoleFunction`, `AccountRole`도 cascade 삭제. (권한: `roles.delete`)
- **FR-F15** `PUT /roles/{id}/functions` — 역할의 기능-CRUD 매핑을 일괄 설정. 요청 본문은 `[{function_id, can_create, can_read, can_update, can_delete}]` 배열. 기존 매핑을 삭제하고 새로 교체. (권한: `roles.update`)

## FR-F5. 기능 관리 API (`/functions` — `roles` 기능 권한 필요)

- **FR-F16** `GET /functions` — 기능 목록 조회. (권한: `roles.read`)
- **FR-F17** `POST /functions` — 기능 생성. `name`, `description` 입력. (권한: `roles.create`)
- **FR-F18** `PATCH /functions/{id}` — 기능의 `name`/`description` 수정. (권한: `roles.update`)
- **FR-F19** `DELETE /functions/{id}` — 기능 삭제. 연결된 `RoleFunction`도 cascade 삭제. (권한: `roles.delete`)

## FR-F6. 사용자 관리 API (`/admin/users` — `users` 기능 권한 필요)

- **FR-F20** `GET /admin/users` — 전체 사용자 목록 조회. 각 사용자의 역할 목록 포함. (권한: `users.read`)
- **FR-F21** `PATCH /admin/users/{id}/roles` — 사용자의 역할을 변경. 요청 본문은 역할 ID 배열. 기존 역할을 교체. → 감사 로그 기록. (권한: `users.update`)
- **FR-F22** `POST /admin/users/{id}/reset-password` — 사용자 비밀번호 초기화. 랜덤 임시 비밀번호를 생성하여 bcrypt 해싱 후 저장. 평문 비밀번호는 응답 본문에 한 번만 반환(운영자에게 전달). → 감사 로그 기록. (권한: `users.update`)
- **FR-F23** `DELETE /admin/users/{id}` — 사용자 비활성화(soft delete, `is_active=False`). 실제 DB 레코드는 보존. → 감사 로그 기록. (권한: `users.delete`)

## FR-F7. 딥 리서치·모델 관리 기능/권한 확장

- **FR-F24** FR-F06의 시드 기능 목록에 `deep_research`(딥 리서치 에이전트)와 `models`(모델 관리)를 추가한다. 앱 시작 시 멱등 시드로 등록한다.
- **FR-F25** 역할-기능 권한 매핑(FR-F07)을 다음과 같이 확장한다:
  - **운영자**: `deep_research`(C/R/U/D), `models`(C/R/U/D).
  - **프리미엄 사용자**: `deep_research`(C/R).
  - **사용자**: `deep_research`(C/R).
  - `models` 기능은 **운영자만** C/R/U/D 권한을 갖는다.
  - 딥 리서치의 세션 생성·메시지 전송·플랜 편집/승인/거절·실행은 모두 `deep_research.create` 액션으로 제어된다. 따라서 FR-I02의 "사용자 이상 접근 및 사용"이 실제로 작동하도록 사용자·프리미엄 사용자에게 `create` 권한을 부여한다(초안 FR-F25가 read만 부여하던 gap 수정).
- **FR-F26** 회원가입(이메일) 및 OAuth 로그인/가입 시 계정에 기본 **"사용자"** 역할을 자동 부여한다. `cpar2002@gmail.com` 계정은 "사용자" 역할 부여 후 추가로 운영자 역할을 부여한다(`ensure_admin_role` 로직과 함께 `ensure_default_role` 형태로 시드에서 처리). 이는 기존 gap(일반 가입자 역할 미부여)을 해소하고 FR-I02 "사용자 이상 접근"이 실제로 작동하도록 보장한다.
