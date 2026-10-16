"""Người dùng, thiết bị, phản ánh, sự vụ, ảnh và bằng chứng (observation)."""

import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import CITEXT, INET, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Loại phản ánh theo chiều trạng thái (PROJECT_PLAN.md mục 5.4)
CATEGORIES = {
    "flood": ("flood",),
    "obstacle": ("tree_fall", "construction", "accident", "power_line", "other"),
    "traffic": ("congestion",),
}


class AppUser(Base):
    __tablename__ = "app_user"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    role: Mapped[str] = mapped_column(Text, server_default="citizen")
    display_name: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(CITEXT, unique=True)
    password_hash: Mapped[str | None] = mapped_column(Text)
    reputation: Mapped[float] = mapped_column(Float, server_default="1.0")
    is_banned: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Device(Base):
    __tablename__ = "device"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"))
    platform: Mapped[str | None] = mapped_column(Text)
    app_version: Mapped[str | None] = mapped_column(Text)
    push_token: Mapped[str | None] = mapped_column(Text)
    gps_opt_in: Mapped[bool] = mapped_column(Boolean, server_default="false")
    reputation: Mapped[float] = mapped_column(Float, server_default="1.0")
    is_banned: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_ip: Mapped[str | None] = mapped_column(INET)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RefreshToken(Base):
    __tablename__ = "refresh_token"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("device.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Incident(Base):
    __tablename__ = "incident"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    segment_id: Mapped[int | None] = mapped_column(ForeignKey("road_segment.id"))
    dimension: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="open")
    priority: Mapped[float] = mapped_column(Float, server_default="0")
    report_count: Mapped[int] = mapped_column(Integer, server_default="0")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    location = mapped_column(Geometry("POINT", srid=4326, spatial_index=False))
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    moderator_note: Mapped[str | None] = mapped_column(Text)
    is_demo: Mapped[bool] = mapped_column(Boolean, server_default="false")


class Report(Base):
    __tablename__ = "report"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("device.id"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"))
    segment_id: Mapped[int | None] = mapped_column(ForeignKey("road_segment.id"))
    incident_id: Mapped[int | None] = mapped_column(ForeignKey("incident.id"))
    dimension: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    level: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    location = mapped_column(Geometry("POINT", srid=4326, spatial_index=False), nullable=False)
    reporter_location = mapped_column(Geometry("POINT", srid=4326, spatial_index=False))
    gps_accuracy_m: Mapped[float | None] = mapped_column(Float)
    snap_distance_m: Mapped[float | None] = mapped_column(Float)
    proximity_m: Mapped[float | None] = mapped_column(Float)
    client_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    reject_reason: Mapped[str | None] = mapped_column(Text)
    is_demo: Mapped[bool] = mapped_column(Boolean, server_default="false")


class ReportMedia(Base):
    __tablename__ = "report_media"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("report.id", ondelete="CASCADE"))
    storage_key: Mapped[str] = mapped_column(Text)
    thumb_key: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(Text)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(Text)
    duplicate_of: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("report_media.id"))
    moderation: Mapped[str] = mapped_column(Text, server_default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Observation(Base):
    __tablename__ = "observation"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    segment_id: Mapped[int] = mapped_column(ForeignKey("road_segment.id", ondelete="CASCADE"))
    dimension: Mapped[str] = mapped_column(Text)
    level: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(Text)
    source_ref: Mapped[str | None] = mapped_column(Text)
    actor_key: Mapped[str] = mapped_column(Text)
    reliability: Mapped[float] = mapped_column(Float, server_default="1.0")
    has_photo: Mapped[bool] = mapped_column(Boolean, server_default="false")
    proximity_m: Mapped[float | None] = mapped_column(Float)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_demo: Mapped[bool] = mapped_column(Boolean, server_default="false")
