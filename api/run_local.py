"""로컬 데스크톱(Electron) 실행용 진입점.

PyInstaller 로 번들된 단일 exe가 이 스크립트를 실행한다.
흐름:
  1. 사용자 데이터 디렉토리(DATA_DIR 환경변수, 기본 %APPDATA%/StrontiumAgent) 보장
  2. DATA_DIR/config.json 에서 JWT_SECRET / LLM_KEY_ENCRYPTION_KEY 로드
     (없으면 새로 생성해 영속화 — 다음 실행부터 동일 키로 기존 데이터 복호화 가능)
  3. DATABASE_URL, WIKI_ROOT, LOCAL_MODE 등을 환경변수로 주입
  4. main 모듈 import → uvicorn 실행

운영용 .env 파일은 읽지 않는다. 모든 설정은 DATA_DIR 기반으로 자급자족한다.
"""

from __future__ import annotations

import json
import os
import secrets
import sys
from pathlib import Path


def _resolve_data_dir() -> Path:
    """DATA_DIR 환경변수 또는 플랫폼 기본값(%APPDATA%/WLM) 반환 및 생성."""
    env_val = os.environ.get("DATA_DIR")
    if env_val:
        path = Path(env_val)
    elif sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        path = Path(base) / "StrontiumAgent"
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "StrontiumAgent"
    else:
        path = Path.home() / ".local" / "share" / "StrontiumAgent"
    path.mkdir(parents=True, exist_ok=True)
    (path / "wiki").mkdir(exist_ok=True)
    return path


def _load_or_create_config(data_dir: Path) -> dict:
    """data_dir/config.json 에서 시크릿을 로드. 없으면 생성."""
    config_path = data_dir / "config.json"
    if config_path.exists():
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass  # 손상된 경우 새로 생성

    # Fernet 키 — cryptography.fernet.Fernet.generate_key() 와 동일 포맷
    from cryptography.fernet import Fernet

    config = {
        "JWT_SECRET": secrets.token_hex(32),
        "LLM_KEY_ENCRYPTION_KEY": Fernet.generate_key().decode(),
    }
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return config


def main() -> None:
    data_dir = _resolve_data_dir()
    config = _load_or_create_config(data_dir)

    # 환경변수 주입 — core.config.Settings() 가 이 값을 우선 반영한다.
    # (pydantic-settings 우선순위: env var > .env file > 기본값)
    os.environ.setdefault("LOCAL_MODE", "true")
    os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{(data_dir / 'app.db').as_posix()}")
    os.environ.setdefault("WIKI_ROOT", str(data_dir / "wiki"))
    os.environ.setdefault("JWT_SECRET", config["JWT_SECRET"])
    os.environ.setdefault("LLM_KEY_ENCRYPTION_KEY", config["LLM_KEY_ENCRYPTION_KEY"])
    # CORS 는 동일 호스트 다른 포트(3000→8000) 호출용. Electron webview origin 고정.
    os.environ.setdefault("CORS_ORIGINS", '["http://localhost:3000", "http://127.0.0.1:3000"]')
    os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")

    # 늦은 import — 위 환경변수들이 주입된 상태에서 Settings 가 평가되어야 함
    import uvicorn

    from main import app  # noqa: F401 — app 객체를 uvicorn 에 넘김

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="warning",
        access_log=False,
    )


if __name__ == "__main__":
    main()
