"""Tính lại trạng thái đồng thời trên cùng (đoạn, chiều) không được ghi trùng lịch sử.

Không có khoá: luồng B không thấy trạng thái A vừa ghi (chưa commit) nên cũng coi là "chuyển từ chưa có
→ UNVERIFIED" và ghi thêm một dòng lịch sử trùng.

Cần dữ liệu đã commit và hai kết nối thật, nên test tự tạo rồi tự xoá dữ liệu (không dùng fixture rollback).
"""

import threading
import time
from datetime import UTC, datetime

from sqlalchemy import text

from app.db.session import get_engine
from app.services import status_engine

CODE = "T-CONCURRENT"


def _setup() -> int:
    with get_engine().begin() as conn:
        segment_id = conn.execute(
            text("""
                INSERT INTO road_segment (code, display_name, segment_type, geom, verification_status)
                VALUES (:code, 'Đoạn test đồng thời', 'street',
                        ST_GeomFromText('LINESTRING(107.58 16.47, 107.58 16.471)', 4326), 'field_verified')
                RETURNING id
            """),
            {"code": CODE},
        ).scalar_one()
        for actor in ("device:a", "device:b"):
            conn.execute(
                text("""
                    INSERT INTO observation (segment_id, dimension, level, source_type, actor_key, observed_at)
                    VALUES (:s, 'flood', 'calf', 'citizen_report', :actor, now())
                """),
                {"s": segment_id, "actor": actor},
            )
    return segment_id


def _cleanup(segment_id: int) -> None:
    with get_engine().begin() as conn:
        for table in ("segment_status_history", "segment_status_current", "observation"):
            conn.execute(text(f"DELETE FROM {table} WHERE segment_id = :s"), {"s": segment_id})
        conn.execute(text("DELETE FROM road_segment WHERE id = :s"), {"s": segment_id})


def test_concurrent_recompute_writes_history_once():
    segment_id = _setup()
    errors = []

    def worker(hold_s: float):
        try:
            from sqlalchemy.orm import Session

            with Session(get_engine()) as db:
                status_engine.recompute(db, segment_id, "flood", datetime.now(UTC))
                time.sleep(hold_s)  # giữ transaction mở để luồng kia chạy chen vào
                db.commit()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    try:
        threads = [threading.Thread(target=worker, args=(0.3,)), threading.Thread(target=worker, args=(0,))]
        threads[0].start()
        time.sleep(0.05)
        threads[1].start()
        for t in threads:
            t.join(timeout=10)
        assert not errors, errors
        with get_engine().connect() as conn:
            rows = conn.execute(
                text("SELECT state, valid_to FROM segment_status_history WHERE segment_id = :s"),
                {"s": segment_id},
            ).all()
        assert [(r.state, r.valid_to) for r in rows] == [("UNVERIFIED", None)]
    finally:
        _cleanup(segment_id)
