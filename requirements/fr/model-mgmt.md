# FR-J. 모델 관리 (Model Management)

## FR-J1. 메뉴 및 접근 제어

- **FR-J01** 사이드바에 "모델 관리" 메뉴(`/models`)를 추가한다. **운영자 전용**이며 접근 제어는 서버 측 `require_permission("models", "read")` 등 CRUD action별로 수행한다. 시드로 운영자 역할에만 `models` 기능의 C/R/U/D 권한이 부여된다(FR-F25 참조).

## FR-J2. 제공자/모델 관리

- **FR-J02** 모델 관리 메뉴에서는 **Ollama Cloud**와 **OpenCode Zen API Key** 두 가지 제공자 타입의 항목을 CRUD(생성·조회·수정·삭제)할 수 있다. 각 항목은 다음 필드를 갖는다:
  - `provider_type`: `"ollama_cloud"` | `"opencode_zen"`
  - `display_name`: 사용자에게 표시할 이름
  - `base_url`: 선택적 기본 엔드포인트 URL
  - `models`: 해당 제공자에서 사용 가능한 모델 식별자 목록
  - `is_active`: 활성화 여부 (활성화된 항목의 모델만 FR-I06 선택지에 노출)

  **API 키는 항목에 저장하지 않고 환경변수에서 `provider_type`별로 주입**한다(`OLLAMA_API_KEY` for `ollama_cloud`, `ZEN_AI_API_KEY` for `opencode_zen`). 운영자는 UI에서 키 값이 아닌 **키 설정 여부**(`api_key_configured`)만 확인할 수 있으며, 평문 키는 절대 노출되지 않는다(NFR-S11). 키 교체는 환경변수(운영 체계)를 통해 수행한다.

## FR-J3. 데이터 모델

- **FR-J03** 제공자 설정을 저장할 `llm_providers` 테이블을 정의한다:
  - `id`(UUID, PK)
  - `provider_type`(String, `"ollama_cloud"` | `"opencode_zen"`)
  - `display_name`(String)
  - `base_url`(String, nullable)
  - `models`(JSON, 모델 식별자 문자열 배열)
  - `is_active`(Boolean, 기본 True)
  - `created_at`/`updated_at`(타임스탬프)

  API 키는 이 테이블에 저장하지 않고 환경변수로 주입한다(NFR-S10 참조).

## FR-J4. API

- **FR-J04** 모델 관리 API를 제공한다 (운영자 `models.*` 권한 필요):
  - `GET /models/providers` — 제공자 목록 조회. 응답은 `api_key_configured`(환경변수 키 설정 여부)만 포함하며 **평문 키는 절대 포함하지 않는다**(NFR-S11).
  - `POST /models/providers` — 제공자 생성(`provider_type`, `display_name`, `base_url`, `models`, `is_active`).
  - `PATCH /models/providers/{id}` — 표시명·base_url·models·is_active 수정.
  - `DELETE /models/providers/{id}` — 제공자 삭제. 연결된 모델 선택지는 더 이상 노출되지 않음.

  모든 쓰기 액션(생성·수정·삭제)은 감사 로그에 기록한다. `detail`에 API 키 평문은 존재하지 않으므로 노출 우려가 없다(NFR-S09, NFR-S11).
