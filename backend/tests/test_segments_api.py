"""API đoạn đường. Toạ độ và đoạn ở đây là dữ liệu kiểm thử, không phải dữ liệu thật."""

from datetime import UTC, datetime

import pytest

from app.models import PilotArea, RoadSegment, SegmentStatusCurrent

NOW = datetime(2026, 10, 16, 10, 0, tzinfo=UTC)
BBOX = "107.57,16.46,107.59,16.48"


def line(lon, lat, dlat=0.001):
    return f"SRID=4326;LINESTRING({lon} {lat}, {lon} {lat + dlat})"


def add_segment(db, code, name, lon=107.58, lat=16.47, **kwargs):
    kwargs.setdefault("verification_status", "field_verified")
    segment = RoadSegment(
        code=code,
        display_name=name,
        segment_type=kwargs.pop("segment_type", "street"),
        geom=line(lon, lat),
        **kwargs,
    )
    db.add(segment)
    db.flush()
    return segment


def add_status(db, segment, dimension="flood", state="UNVERIFIED", level="calf"):
    db.add(
        SegmentStatusCurrent(
            segment_id=segment.id,
            dimension=dimension,
            state=state,
            level=level,
            confidence=0.6,
            evidence_count=3,
            independent_sources=3,
            last_evidence_at=NOW,
            computed_at=NOW,
            rule_version=1,
        )
    )
    db.flush()


def features_by_code(response):
    assert response.status_code == 200, response.text
    return {f["properties"]["code"]: f for f in response.json()["features"]}


def test_segment_without_status_is_no_data_not_normal(client, db):
    add_segment(db, "T-1", "Đoạn không có dữ liệu")
    feature = features_by_code(client.get("/api/v1/segments", params={"bbox": BBOX}))["T-1"]
    assert feature["properties"]["status"]["state"] == "NO_DATA"
    assert feature["properties"]["status"]["level"] is None
    assert feature["geometry"]["type"] == "LineString"


def test_status_is_returned_for_requested_dimension_only(client, db):
    segment = add_segment(db, "T-2", "Đoạn ngập")
    add_status(db, segment, "flood", "UNVERIFIED", "calf")
    flood = features_by_code(client.get("/api/v1/segments", params={"bbox": BBOX, "dimension": "flood"}))
    traffic = features_by_code(client.get("/api/v1/segments", params={"bbox": BBOX, "dimension": "traffic"}))
    assert flood["T-2"]["properties"]["status"]["level"] == "calf"
    assert traffic["T-2"]["properties"]["status"]["state"] == "NO_DATA"


def test_visibility_rules(client, db, settings):
    add_segment(db, "T-OK", "Đã khảo sát")
    add_segment(db, "T-DRAFT", "Nháp OSM", verification_status="draft")
    add_segment(db, "T-RETIRED", "Đã bỏ", verification_status="retired")
    add_segment(db, "T-DEMO", "Minh hoạ", is_demo=True)

    codes = set(features_by_code(client.get("/api/v1/segments", params={"bbox": BBOX})))
    assert codes == {"T-OK"}

    settings.show_unverified_segments = True
    settings.include_demo_data = True
    codes = set(features_by_code(client.get("/api/v1/segments", params={"bbox": BBOX})))
    assert codes == {"T-OK", "T-DRAFT", "T-DEMO"}  # retired không bao giờ hiện


def test_bbox_filters_spatially(client, db):
    add_segment(db, "T-IN", "Trong khung", lon=107.58)
    add_segment(db, "T-OUT", "Ngoài khung", lon=107.70)
    assert set(features_by_code(client.get("/api/v1/segments", params={"bbox": BBOX}))) == {"T-IN"}


@pytest.mark.parametrize(
    ("bbox", "code"),
    [
        ("abc", "INVALID_BBOX"),
        ("107.59,16.46,107.57,16.48", "INVALID_BBOX"),
        ("100,10,110,20", "BBOX_TOO_LARGE"),
    ],
)
def test_bad_bbox(client, bbox, code):
    response = client.get("/api/v1/segments", params={"bbox": bbox})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == code


def test_etag_returns_304_until_status_changes(client, db):
    segment = add_segment(db, "T-E", "ETag")
    first = client.get("/api/v1/segments", params={"bbox": BBOX})
    etag = first.headers["ETag"]
    again = client.get("/api/v1/segments", params={"bbox": BBOX}, headers={"If-None-Match": etag})
    assert again.status_code == 304

    add_status(db, segment)
    changed = client.get("/api/v1/segments", params={"bbox": BBOX}, headers={"If-None-Match": etag})
    assert changed.status_code == 200
    assert changed.headers["ETag"] != etag


def test_detail_has_all_dimensions(client, db):
    segment = add_segment(db, "T-D", "Kiệt 12 Đinh Tiên Hoàng", segment_type="kiet")
    add_status(db, segment, "obstacle", "CONFIRMED", "partial")
    body = client.get("/api/v1/segments/T-D").json()
    assert body["name"] == "Kiệt 12 Đinh Tiên Hoàng"
    assert body["status"]["flood"]["state"] == "NO_DATA"
    assert body["status"]["traffic"]["state"] == "NO_DATA"
    assert body["status"]["obstacle"] == {
        "state": "CONFIRMED",
        "level": "partial",
        "confidence": pytest.approx(0.6),
        "evidence_count": 3,
        "last_evidence_at": NOW.isoformat(),
    }
    assert body["midpoint"]["type"] == "Point"


def test_detail_not_found_and_hidden_draft(client, db):
    add_segment(db, "T-H", "Nháp", verification_status="draft")
    for code in ("NOPE", "T-H"):
        response = client.get(f"/api/v1/segments/{code}")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "SEGMENT_NOT_FOUND"


def test_search_without_diacritics(client, db):
    add_segment(db, "T-S1", "Kiệt 12 Đinh Tiên Hoàng (từ Mai Thúc Loan)", segment_type="kiet")
    add_segment(db, "T-S2", "Lê Duẩn (từ Trần Hưng Đạo)")
    results = client.get("/api/v1/search", params={"q": "kiet 12 dinh tien"}).json()["results"]
    assert [r["code"] for r in results] == ["T-S1"]
    assert len(results[0]["bbox"]) == 4

    by_code = client.get("/api/v1/search", params={"q": "t-s2"}).json()["results"]
    assert by_code[0]["code"] == "T-S2"


def test_search_validation(client):
    assert client.get("/api/v1/search", params={"q": "a"}).status_code == 422


def test_region(client, db):
    assert client.get("/api/v1/regions/hue").status_code == 404
    db.add(
        PilotArea(
            id="test-area",
            name="Vùng test",
            geom="SRID=4326;POLYGON((107.57 16.46, 107.59 16.46, 107.59 16.48, 107.57 16.48, 107.57 16.46))",
        )
    )
    db.flush()
    body = client.get("/api/v1/regions/hue").json()
    assert body["pilot_areas"][0]["id"] == "test-area"
    assert body["pilot_areas"][0]["area_km2"] > 4
    assert "OpenStreetMap" in body["attribution"]


def test_etag_accepts_weak_and_multiple_tags(client, db):
    add_segment(db, "T-W", "Weak ETag")
    etag = client.get("/api/v1/segments", params={"bbox": BBOX}).headers["ETag"]
    headers = {"If-None-Match": f'"other", W/{etag}'}
    assert client.get("/api/v1/segments", params={"bbox": BBOX}, headers=headers).status_code == 304
