from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_DB = f"sqlite+aiosqlite:///{Path(__file__).resolve().parents[2] / 'db' / 'app.db'}"


class Settings(BaseSettings):
    DATABASE_URL: str = _DEFAULT_DB

    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    COOKIE_SECURE: bool = False  # 운영 환경에서는 True로 설정

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
