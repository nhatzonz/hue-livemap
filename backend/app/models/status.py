"""Trạng thái đoạn đường: tham số engine, trạng thái hiện tại, lịch sử (PROJECT_PLAN.md mục 6)."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

DIMENSIONS = ("flood", "obstacle", "traffic")
STATES = ("NO_DATA", "STALE", "UNVERIFIED", "CONFIRMED", "CONFLICTING")


class StatusRule(Base):
    __tablename__ = "status_rule"

    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    params: Mapped[dict] = mapped_column(JSONB)
    active_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)


class SegmentStatusCurrent(Base):
    __tablename__ = "segment_status_current"

    segment_id: Mapped[int] = mapped_column(ForeignKey("road_segment.id"), primary_key=True)
    dimension: Mapped[str] = mapped_column(Text, primary_key=True)
    state: Mapped[str] = mapped_column(Text)
    level: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    evidence_count: Mapped[int] = mapped_column(Integer, server_default="0")
    independent_sources: Mapped[int] = mapped_column(Integer, server_default="0")
    last_evidence_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    rule_version: Mapped[int] = mapped_column(ForeignKey("status_rule.version"))
    # Tăng mỗi khi trạng thái đổi; client polling GET /status/changes?since=<change_seq>
    change_seq: Mapped[int] = mapped_column(BigInteger, server_default=text("nextval('status_change_seq')"))


class SegmentStatusHistory(Base):
    __tablename__ = "segment_status_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    segment_id: Mapped[int] = mapped_column(ForeignKey("road_segment.id"))
    dimension: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)
    level: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cause: Mapped[str] = mapped_column(Text)
    rule_version: Mapped[int] = mapped_column(ForeignKey("status_rule.version"))
