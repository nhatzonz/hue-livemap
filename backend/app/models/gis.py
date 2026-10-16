"""Mạng lưới đường: nguồn dữ liệu, đường, đoạn đường, điểm trũng.

Ràng buộc CHECK và cột sinh tự động được định nghĩa trong migration (nguồn sự thật cho schema);
model ở đây phản ánh đúng các cột để ORM đọc/ghi.
"""

from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    Computed,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

SEGMENT_TYPES = ("street", "kiet", "hem", "bridge", "other")
VERIFICATION_STATUSES = ("draft", "desk_reviewed", "field_verified", "retired")


class DataSource(Base):
    __tablename__ = "data_source"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    license: Mapped[str | None] = mapped_column(Text)
    attribution: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)


class Road(Base):
    __tablename__ = "road"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    region_id: Mapped[str] = mapped_column(Text, server_default="hue")
    name: Mapped[str] = mapped_column(Text)
    name_search: Mapped[str] = mapped_column(Text, Computed("lower(immutable_unaccent(name))"))
    road_class: Mapped[str | None] = mapped_column(Text)
    osm_way_ids: Mapped[list[int] | None] = mapped_column(ARRAY(BigInteger))
    is_demo: Mapped[bool] = mapped_column(Boolean, server_default="false")

    segments: Mapped[list["RoadSegment"]] = relationship(back_populates="road")


class RoadSegment(Base):
    __tablename__ = "road_segment"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True)
    region_id: Mapped[str] = mapped_column(Text, server_default="hue")
    road_id: Mapped[int | None] = mapped_column(ForeignKey("road.id"))
    display_name: Mapped[str] = mapped_column(Text)
    segment_type: Mapped[str] = mapped_column(Text)
    geom = mapped_column(Geometry("LINESTRING", srid=4326, spatial_index=False), nullable=False)
    length_m: Mapped[float] = mapped_column(Numeric, Computed("ST_Length(geom::geography)"))
    geom_version: Mapped[int] = mapped_column(Integer, server_default="1")
    width_class: Mapped[str | None] = mapped_column(Text)
    vehicle_access: Mapped[str | None] = mapped_column(Text)
    drainage_notes: Mapped[str | None] = mapped_column(Text)
    flood_prone: Mapped[str] = mapped_column(Text, server_default="unknown")
    source_id: Mapped[int | None] = mapped_column(ForeignKey("data_source.id"))
    source_ref: Mapped[str | None] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(Text, server_default="draft")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by: Mapped[int | None] = mapped_column(BigInteger)
    supersedes: Mapped[list[int] | None] = mapped_column(ARRAY(BigInteger))
    pilot_tier: Mapped[int | None] = mapped_column(SmallInteger)  # 1 trục chính, 2 dân sinh, 3 kiệt
    dataset_import_id: Mapped[int | None] = mapped_column(ForeignKey("dataset_import.id"))
    is_demo: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    road: Mapped[Road | None] = relationship(back_populates="segments")


class PilotArea(Base):
    __tablename__ = "pilot_area"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    region_id: Mapped[str] = mapped_column(Text, server_default="hue")
    name: Mapped[str] = mapped_column(Text)
    geom = mapped_column(Geometry("POLYGON", srid=4326, spatial_index=False), nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default="draft")
    method: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("data_source.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DatasetImport(Base):
    __tablename__ = "dataset_import"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(Text)
    region_id: Mapped[str] = mapped_column(Text, server_default="hue")
    source_file: Mapped[str] = mapped_column(Text)
    source_meta: Mapped[dict | None] = mapped_column(JSONB)
    stats: Mapped[dict] = mapped_column(JSONB)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    imported_by: Mapped[str | None] = mapped_column(Text)


class SegmentHotspot(Base):
    __tablename__ = "segment_hotspot"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    segment_id: Mapped[int] = mapped_column(ForeignKey("road_segment.id"))
    geom = mapped_column(Geometry("POINT", srid=4326, spatial_index=False), nullable=False)
    kind: Mapped[str] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("data_source.id"))
