# FR-D. 프론트엔드 — 앱 셸

- **FR-D01** 인증된 영역 `(main)`에 접이식 Sidebar와 TopNav로 구성된 레이아웃이 제공된다.
- **FR-D02** Sidebar는 사용자의 권한(`permissions`)에 따라 메뉴를 동적으로 렌더링한다. 기본 메뉴: 홈(`/`, 항상 표시), 설정(`/settings`, settings.read), 사용자(`/users`, users.read), 역할 관리(`/roles`, roles.read), 감사 로그(`/audit-logs`, audit.read), 딥 리서치 에이전트(`/deep-research`, deep_research.read), 모델 관리(`/models`, models.read). 접기/펼치기가 가능하다.
- **FR-D03** TopNav는 사용자 닉네임/이메일을 표시하는 드롭다운 메뉴와 로그아웃 항목을 제공한다.
