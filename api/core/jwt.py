import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from core.config import settings


def create_access_token(account_id: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": account_id, "type": "access", "exp": exp},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> str:
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("invalid token type")
    return payload["sub"]


def generate_refresh_token() -> tuple[str, str]:
    """(plain_token, token_hash) 반환. DB에는 hash만 저장."""
    plain = secrets.token_urlsafe(64)
    return plain, _hash(plain)


def hash_refresh_token(plain: str) -> str:
    return _hash(plain)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
