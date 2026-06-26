import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from database.models import AuditLog

logger = logging.getLogger(__name__)


async def log_action(
    db: AsyncSession,
    actor_id: str | None,
    target_id: str | None,
    action: str,
    detail: dict | None = None,
) -> None:
    """감사 로그를 기록한다. detail에 평문 비밀번호/토큰을 포함하지 마세요."""
    try:
        entry = AuditLog(
            actor_id=actor_id,
            target_id=target_id,
            action=action,
            detail=json.dumps(detail, ensure_ascii=False) if detail else None,
        )
        db.add(entry)
        await db.flush()
    except Exception:
        logger.exception("Failed to write audit log: action=%s", action)
