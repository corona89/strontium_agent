# reqList.md — 요구사항 색인

요구사항은 `requirements/` 디렉토리에 카테고리별로 분리되어 있다. 이 파일은 전체 구조의 색인이다.

## 구조

```
requirements/
├── reqList.md          ← 이 파일 (색인)
├── overview.md         ← 프로젝트 개요
├── fr/                 ← 기능 요구사항 (Functional Requirements)
│   ├── auth.md         ← FR-A: 인증
│   ├── account.md      ← FR-B: 계정 관리
│   ├── auth-ui.md      ← FR-C: 프론트엔드 인증 UI
│   ├── app-shell.md    ← FR-D: 프론트엔드 앱 셸
│   ├── api-client.md   ← FR-E: API 클라이언트
│   ├── rbac.md         ← FR-F: 권한 관리 (RBAC)
│   ├── audit-log.md    ← FR-G: 감사 로그
│   ├── admin-ui.md     ← FR-H: 프론트엔드 관리자 페이지
│   ├── deep-research.md ← FR-I: 딥 리서치 에이전트
│   ├── model-mgmt.md   ← FR-J: 모델 관리
│   └── llmwiki.md      ← FR-K: LLM 위키
├── nfr/                ← 비기능 요구사항 (Non-Functional Requirements)
│   ├── security.md     ← NFR-S: 보안
│   ├── tech-stack.md   ← NFR-T: 기술 스택
│   └── database.md     ← NFR-D: 데이터베이스
├── plan.md             ← 미구현 요구사항 / 진행 중 계획 큐
└── issues.md           ← 미구현 기능 및 알려진 이슈
```

## 카테고리 색인

### 기능 요구사항 (FR)

| ID | 카테고리 | 파일 | 항목 수 |
|---|---|---|---|
| FR-A | 인증 (Authentication) | [fr/auth.md](fr/auth.md) | 6 |
| FR-B | 계정 관리 (Account Management) | [fr/account.md](fr/account.md) | 5 |
| FR-C | 프론트엔드 인증 UI | [fr/auth-ui.md](fr/auth-ui.md) | 5 |
| FR-D | 프론트엔드 앱 셸 | [fr/app-shell.md](fr/app-shell.md) | 3 |
| FR-E | API 클라이언트 | [fr/api-client.md](fr/api-client.md) | 4 |
| FR-F | 권한 관리 (RBAC) | [fr/rbac.md](fr/rbac.md) | 26 |
| FR-G | 감사 로그 (Audit Log) | [fr/audit-log.md](fr/audit-log.md) | 4 |
| FR-H | 프론트엔드 관리자 페이지 | [fr/admin-ui.md](fr/admin-ui.md) | 5 |
| FR-I | 딥 리서치 에이전트 (Deep Research Agent) | [fr/deep-research.md](fr/deep-research.md) | 9 |
| FR-J | 모델 관리 (Model Management) | [fr/model-mgmt.md](fr/model-mgmt.md) | 4 |
| FR-K | LLM 위키 (LLM Wiki) | [fr/llmwiki.md](fr/llmwiki.md) | 11 |

### 비기능 요구사항 (NFR)

| ID | 카테고리 | 파일 | 항목 수 |
|---|---|---|---|
| NFR-S | 보안 (Security) | [nfr/security.md](nfr/security.md) | 11 |
| NFR-T | 기술 스택 (Tech Stack) | [nfr/tech-stack.md](nfr/tech-stack.md) | 3 |
| NFR-D | 데이터베이스 (Database) | [nfr/database.md](nfr/database.md) | 3 |

### 기타

| 카테고리 | 파일 |
|---|---|
| 프로젝트 개요 | [overview.md](overview.md) |
| 미구현 요구사항 / 진행 중 계획 큐 | [plan.md](plan.md) |
| 미구현 기능 및 알려진 이슈 | [issues.md](issues.md) |

## 식별자 체계

- **FR-<카테고리><번호>**: 기능 요구사항 (예: `FR-A01`, `FR-F15`)
- **NFR-<카테고리><번호>**: 비기능 요구사항 (예: `NFR-S01`, `NFR-D03`)
- **TODO-<번호>**: 미구현 기능
- **ISSUE-<번호>**: 알려진 이슈/결함

## 작성 규칙

1. 새 요구사항은 해당 카테고리 파일의 끝에 번호를 증가시켜 추가한다.
2. 항목 해결 시 삭제하지 않고 취소선(`~~`) + **해결** 표시를 추가한다 (`issues.md` 참조).
3. 기존 카테고리에 맞지 않는 요구사항은 새 카테고리 파일을 생성하고 이 색인에 등록한다.
4. 카테고리 파일 추가 시 이 색인의 테이블과 구조 트리에 반영한다.
