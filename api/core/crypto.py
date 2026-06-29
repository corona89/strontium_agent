"""LLM 제공자 API 키의 대칭 암호화(Fernet).

마스터 키(LLM_KEY_ENCRYPTION_KEY)만 환경변수로 주입한다.
평문 키는 이 모듈을 통해서만 메모리에 상주하며, 로그/응답에 노출되지 않는다(NFR-S11).
"""
from __future__ import annotations

import logging
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from core.config import settings

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None
# 개발 전용 영속 키 파일 — LLM_KEY_ENCRYPTION_KEY 미설정 시 사용. 재시작해도 키가 유지되도록.
# (운영 환경에서는 무조건 환경변수를 사용하며 이 파일은 생성되지 않는다.)
_DEV_KEY_FILE = Path(__file__).resolve().parents[1] / ".dev-fernet-key"


def _load_or_create_dev_key() -> bytes:
    """개발용 키 파일이 있으면 읽고, 없으면 새로 생성해 저장한다(안정적인 dev 경험)."""
    try:
        return _DEV_KEY_FILE.read_bytes()
    except FileNotFoundError:
        key = Fernet.generate_key()
        _DEV_KEY_FILE.write_bytes(key)
        return key


def _get_fernet() -> Fernet:
    """마스터 키로 Fernet 인스턴스를 초기화한다(싱글톤).

    운영(COOKIE_SECURE)에서는 LLM_KEY_ENCRYPTION_KEY 미설정 시 시작을 거부한다.
    개발에서는 미설정 시 영속 키 파일을 생성/재사용해 재시작 시에도 기존 암호문이 복호화되도록 한다.
    """
    global _fernet
    if _fernet is not None:
        return _fernet

    raw = settings.LLM_KEY_ENCRYPTION_KEY
    if raw:
        try:
            _fernet = Fernet(raw.encode("ascii") if isinstance(raw, str) else raw)
        except (ValueError, TypeError) as e:
            raise RuntimeError(
                "LLM_KEY_ENCRYPTION_KEY가 유효한 Fernet 키가 아닙니다. "
                "Fernet.generate_key() 로 생성한 32바이트 url-safe base64 문자열이어야 합니다."
            ) from e
    elif settings.COOKIE_SECURE:
        raise RuntimeError(
            "운영 환경에서는 LLM_KEY_ENCRYPTION_KEY를 반드시 설정해야 합니다. "
            "Fernet.generate_key() 로 생성하세요."
        )
    else:
        _fernet = Fernet(_load_or_create_dev_key())
        logger.warning(
            "LLM_KEY_ENCRYPTION_KEY 미설정 — 개발용 키를 %s 에 저장해 사용합니다. "
            "운영 배포 전 Fernet.generate_key() 로 생성한 키를 .env의 "
            "LLM_KEY_ENCRYPTION_KEY에 설정하세요.",
            _DEV_KEY_FILE,
        )
    return _fernet


def encrypt(plaintext: str) -> str:
    """평문 API 키를 암호문 토큰으로 변환해 DB 저장용으로 반환한다."""
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(token: str | None) -> str | None:
    """DB 암호문 토큰을 평문으로 복호화한다. 잘못된 토큰/키 변경 시 None."""
    if not token:
        return None
    try:
        return _get_fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        logger.error(
            "API 키 복호화 실패 — LLM_KEY_ENCRYPTION_KEY가 변경되었거나 암호문이 손상되었습니다."
        )
        return None


def mask(plaintext: str | None) -> str | None:
    """평문 키를 마스킹해 응답용으로 안전하게 노출한다(예: code-...WE6X)."""
    if not plaintext:
        return None
    if len(plaintext) <= 8:
        return "*" * len(plaintext)
    return f"{plaintext[:4]}...{plaintext[-4:]}"
