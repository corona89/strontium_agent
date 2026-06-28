import logging
from pathlib import Path
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_DB = f"sqlite+aiosqlite:///{Path(__file__).resolve().parents[2] / 'db' / 'app.db'}"
_INSECURE_SECRET = "change-me-in-production"

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    DATABASE_URL: str = _DEFAULT_DB

    JWT_SECRET: str = _INSECURE_SECRET
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    COOKIE_SECURE: bool = False  # 운영 환경에서는 True로 설정

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    FRONTEND_URL: str = "http://localhost:3000"

    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"

    # LLM 제공자 API 키 — 환경변수로 주입, DB/코드에 영속화하지 않는다(NFR-S10).
    OLLAMA_API_KEY: str | None = None
    ZEN_AI_API_KEY: str | None = None
    # 웹 검색 도구(Tavily) — 딥 리서치 에이전트용
    TAVILY_API_KEY: str | None = None

    # LLM 위키 — 파일시스템 루트(repo/wiki), 업로드 최대 바이트
    WIKI_ROOT: Path = Path(__file__).resolve().parents[2] / "wiki"
    UPLOAD_MAX_BYTES: int = 25 * 1024 * 1024  # 파일당 25MB

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def _check_jwt_secret(self) -> "Settings":
        if self.JWT_SECRET == _INSECURE_SECRET:
            if self.COOKIE_SECURE:
                raise ValueError(
                    "JWT_SECRET가 기본값입니다. 운영 환경에서는 반드시 변경해야 합니다. "
                    "secrets.token_hex(32) 로 생성하세요."
                )
            logger.warning("JWT_SECRET가 기본값입니다. 운영 배포 전 반드시 변경하세요.")
        return self


settings = Settings()
