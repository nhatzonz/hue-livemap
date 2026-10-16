"""Dữ liệu kiểm thử dùng chung. Toạ độ tổng hợp quanh Kinh thành, KHÔNG phải dữ liệu thật."""

import io
import uuid
from datetime import UTC, datetime

from PIL import Image

from app.models import PilotArea, RoadSegment

PILOT_POLYGON = "SRID=4326;POLYGON((107.57 16.46, 107.59 16.46, 107.59 16.48, 107.57 16.48, 107.57 16.46))"


def add_pilot_area(db):
    db.add(PilotArea(id="test-area", name="Vùng test", geom=PILOT_POLYGON))
    db.flush()


def add_segment(db, code, lon=107.58, lat=16.470, dlat=0.001, **kwargs):
    kwargs.setdefault("verification_status", "field_verified")
    segment = RoadSegment(
        code=code,
        display_name=kwargs.pop("display_name", f"Đoạn {code}"),
        segment_type=kwargs.pop("segment_type", "street"),
        geom=f"SRID=4326;LINESTRING({lon} {lat}, {lon} {lat + dlat})",
        **kwargs,
    )
    db.add(segment)
    db.flush()
    return segment


def register(client, device_id=None):
    device_id = device_id or str(uuid.uuid4())
    response = client.post("/api/v1/auth/device", json={"device_id": device_id, "platform": "ios"})
    assert response.status_code == 200, response.text
    return response.json()


def auth_headers(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def report_body(lat=16.4705, lon=107.5801, level="calf", dimension="flood", category="flood", **extra):
    return {
        "id": str(uuid.uuid4()),
        "dimension": dimension,
        "category": category,
        "level": level,
        "location": {"lat": lat, "lon": lon},
        "reporter_location": {"lat": lat, "lon": lon},
        "client_created_at": datetime.now(UTC).isoformat(),
        **extra,
    }


def jpeg_with_gps(size=(2400, 1800), color=(30, 120, 200)) -> bytes:
    """Ảnh JPEG có EXIF (hãng máy + toạ độ GPS) để kiểm tra server xoá metadata."""
    img = Image.new("RGB", size, color)
    exif = Image.Exif()
    exif[0x010F] = "TestCamera"  # Make
    exif[0x8825] = {1: "N", 2: (16.0, 28.0, 10.0), 3: "E", 4: (107.0, 34.0, 50.0)}  # GPSInfo
    out = io.BytesIO()
    img.save(out, "JPEG", exif=exif)
    return out.getvalue()
