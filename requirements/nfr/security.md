# NFR-S. 보안 (Security)

- **NFR-S01** access_token은 JWT(HS256), refresh_token은 opaque 랜덤 문자열이다.
- **NFR-S02** refresh_token은 SHA-256 해시만 DB에 저장하며 평문은 영속화하지 않는다.
- **NFR-S03** 토큰 쿠키는 httpOnly, SameSite=Lax, 운영 환경에서 Secure 속성을 갖는다.
- **NFR-S04** 계정 삭제 시 cascade로 OAuth/refresh 토큰이 함께 정리된다.
- **NFR-S05** OAuth/SSO 데이터 모델(`OAuthAccount`)이 정의되어 있어 SSO 전용 계정(hashed_password=null)을 지원한다.
- **NFR-S06** 권한 확인은 모든 보호된 엔드포인트에서 서버 측(`require_permission` 의존성)으로 수행된다. 프론트엔드 권한 제어는 UX 목적이며 보안 경계가 아니다.
- **NFR-S07** `is_system=True` 역할은 API 레벨에서 삭제가 거부된다(403).
- **NFR-S08** 비밀번호 초기화 시 생성된 평문 임시 비밀번호는 응답에 한 번만 반환되고 DB에 평문으로 저장되지 않는다(bcrypt 해시만 저장).
- **NFR-S09** 감사 로그의 `detail`에 비밀번호 평문 또는 토큰 평문을 절대 기록하지 않는다.
- **NFR-S10** LLM 제공자 API 키(Ollama Cloud / OpenCode Zen)는 DB에 **암호화하여 저장**(at-rest)한다. 암호화에는 대칭키 알고리즘(Fernet/AES-GCM 등)을 사용하고, 암호화 키는 환경변수로 주입하여 코드/DB에 하드코딩하지 않는다. 평문 API 키는 DB에 영속화하지 않는다.
- **NFR-S11** LLM API 키 평문은 감사 로그·API 응답·프론트엔드에 절대 노출하지 않는다. 조회 응답에서는 키를 마스킹(예: `sk-...abcd`)하여 표시하고, 딥 리서치 에이전트(FR-I)의 LLM 호출은 백엔드에서 제공자 설정을 직접 사용하므로 클라이언트에 키를 전달하지 않는다.
