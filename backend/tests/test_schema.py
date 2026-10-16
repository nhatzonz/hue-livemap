import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.models import DataSource, Road, RoadSegment, StatusRule

# Đoạn thẳng ~111 m theo phương Bắc–Nam (0.001° vĩ độ) gần Kinh thành.
# Toạ độ chỉ để kiểm thử, không phải dữ liệu đoạn đường thật.
TEST_LINE = "SRID=4326;LINESTRING(107.5786 16.4698, 107.5786 16.4708)"


def test_unaccent_search_column(db):
    road = Road(name="Kiệt Đinh Tiên Hoàng")
    db.add(road)
    db.flush()
    db.refresh(road)
    assert road.name_search == "kiet dinh tien hoang"


def test_segment_length_is_computed_and_demo_defaults_false(db):
    segment = RoadSegment(code="TEST-0001", display_name="Đoạn kiểm thử", segment_type="kiet", geom=TEST_LINE)
    db.add(segment)
    db.flush()
    db.refresh(segment)
    assert 105 < float(segment.length_m) < 115
    assert segment.is_demo is False
    assert segment.verification_status == "draft"
    assert segment.flood_prone == "unknown"


def test_segment_type_is_constrained(db):
    db.add(RoadSegment(code="TEST-0002", display_name="x", segment_type="highway", geom=TEST_LINE))
    with pytest.raises(IntegrityError):
        db.flush()


def test_segment_search_matches_without_diacritics(db):
    db.add(
        RoadSegment(
            code="TEST-0003", display_name="Kiệt 12 Đinh Tiên Hoàng", segment_type="kiet", geom=TEST_LINE
        )
    )
    db.flush()
    found = db.scalars(
        select(RoadSegment.code).where(
            text("lower(immutable_unaccent(display_name)) LIKE :q").bindparams(q="%kiet 12 dinh tien%")
        )
    ).all()
    assert found == ["TEST-0003"]


def test_reference_data_seeded(db):
    assert db.get(DataSource, 1).license == "ODbL-1.0"
    demo = db.scalar(select(DataSource).where(DataSource.code == "demo"))
    assert "MINH HOẠ" in demo.name

    rule = db.get(StatusRule, 1)
    assert rule.params["dimensions"]["flood"]["fresh_ttl_min"] == 180
    # Nguyên tắc: một phản ánh đơn lẻ không đủ để xác nhận.
    assert rule.params["confirm_min_independent"] >= 2
