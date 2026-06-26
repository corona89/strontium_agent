# FR-B. 계정 관리 (Account Management)

- **FR-B01** 사용자는 이메일, 비밀번호(8자 이상), 닉네임(선택)으로 회원가입할 수 있다 (`POST /accounts`, 201).
- **FR-B02** 이메일 중복 시 409 Conflict를 반환한다.
- **FR-B03** 계정의 닉네임/비밀번호를 부분 수정할 수 있다 (`PATCH /accounts/{id}`). 전송된 필드만 변경하는 PATCH 의미론을 따른다.
- **FR-B04** 계정은 소프트 삭제된다 (`DELETE /accounts/{id}`, `is_active=False`, 204).
- **FR-B05** 비밀번호는 bcrypt로 해싱하여 저장한다.
