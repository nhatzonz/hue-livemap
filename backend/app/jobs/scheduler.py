"""Job nền chạy trong cùng process API (PROJECT_PLAN.md 7.2: chưa cần Redis/Celery ở MVP).

Chạy nhiều worker/instance vẫn an toàn: advisory lock bảo đảm mỗi lượt chỉ một process thực thi.
Khi tải lớn, nên chuyển job sang process riêng để không chiếm threadpool của API.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from app.db.session import get_sessionmaker
from app.services import status_engine

logger = logging.getLogger("hue_livemap.jobs")

DECAY_LOCK_ID = 7_310_001  # pg advisory lock: chỉ một process chạy job suy giảm tại một thời điểm
REVOKED_TOKEN_RETENTION = timedelta(days=7)


def run_decay_once() -> int:
    with get_sessionmaker()() as db:
        if not db.execute(text("SELECT pg_try_advisory_xact_lock(:id)"), {"id": DECAY_LOCK_ID}).scalar_one():
            return 0
        now = datetime.now(UTC)
        changed = status_engine.recompute_all_active(db, now)
        # Dọn refresh token đã hết hạn/thu hồi để bảng không phình mãi
        db.execute(
            text("DELETE FROM refresh_token WHERE expires_at < :now OR revoked_at < :old"),
            {"now": now, "old": now - REVOKED_TOKEN_RETENTION},
        )
        db.commit()
        return changed


async def decay_loop(interval_s: int) -> None:
    while True:
        try:
            changed = await run_in_threadpool(run_decay_once)
            if changed:
                logger.info("status decay: %d trạng thái thay đổi", changed)
        except Exception:  # noqa: BLE001 — job không được làm chết API
            logger.exception("status decay job lỗi")
        await asyncio.sleep(interval_s)
