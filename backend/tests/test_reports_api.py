import io
from datetime import UTC, datetime, timedelta

import pytest
from PIL import Image
from sqlalchemy import text

from app.services import status_engine
from tests.factories import add_pilot_area, add_segment, auth_headers, jpeg_with_gps, register, report_body


@pytest.fixture
def area(db):
    add_pilot_area(db)
    return {
        "A": add_segment(db, "T-A", lon=107.5800),
        "B": add_segment(db, "T-B", lon=107.5850),
    }


@pytest.fixture
def device(client):
    return auth_headers(register(client))


def post_report(client, headers, **kwargs):
    return client.post("/api/v1/reports", json=report_body(**kwargs), headers=headers)


def flood_state(client, code):
    return client.get(f"/api/v1/segments/{code}").json()["status"]["flood"]


def test_report_snaps_to_nearest_segment_and_is_unverified(client, area, device, db):
    response = post_report(client, device)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["segment"]["code"] == "T-A"
    assert body["status"] == "pending"
    status = flood_state(client, "T-A")
    assert (status["state"], status["level"], status["evidence_count"]) == ("UNVERIFIED", "calf", 1)
    assert flood_state(client, "T-B")["state"] == "NO_DATA"


def test_report_is_idempotent_for_same_device(client, area, device):
    body = report_body()
    first = client.post("/api/v1/reports", json=body, headers=device)
    retry = client.post("/api/v1/reports", json=body, headers=device)
    assert (first.status_code, retry.status_code) == (201, 200)
    assert retry.json()["id"] == first.json()["id"]
    assert flood_state(client, "T-A")["evidence_count"] == 1

    other = auth_headers(register(client))
    assert client.post("/api/v1/reports", json=body, headers=other).status_code == 409


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [
        ({"lat": 16.50, "lon": 107.60}, "OUTSIDE_PILOT_AREA"),
        ({"level": "waist"}, "INVALID_LEVEL"),
        ({"category": "tree_fall"}, "INVALID_CATEGORY"),
        ({"client_created_at": (datetime.now(UTC) - timedelta(hours=25)).isoformat()}, "REPORT_TOO_OLD"),
        ({"client_created_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat()}, "INVALID_TIME"),
        ({"segment_code": "T-B"}, "SEGMENT_TOO_FAR"),
        ({"segment_code": "NOPE"}, "SEGMENT_NOT_FOUND"),
    ],
)
def test_report_validation(client, area, device, kwargs, code):
    response = post_report(client, device, **kwargs)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == code


def test_report_far_from_any_segment_is_kept_as_point_report(client, area, device):
    body = post_report(client, device, lat=16.475, lon=107.575).json()
    assert body["segment"] is None
    assert body["incident_id"] is not None


def test_reports_on_same_segment_join_one_incident(client, area, device, db):
    first = post_report(client, device).json()
    second = post_report(client, auth_headers(register(client)), level="knee").json()
    assert first["incident_id"] == second["incident_id"]
    count = db.execute(text("SELECT report_count FROM incident WHERE id = :id"), {"id": first["incident_id"]})
    assert count.scalar_one() == 2


def test_rate_limit_per_segment(client, area, device, settings):
    settings.max_reports_per_segment_device_hour = 1
    assert post_report(client, device).status_code == 201
    second = post_report(client, device)
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "RATE_LIMITED"


def test_three_devices_with_photo_confirm_and_map_shows_it(client, area, device):
    report_id = post_report(client, device).json()["id"]
    upload = client.put(
        f"/api/v1/reports/{report_id}/media",
        headers=device,
        files={"file": ("a.jpg", jpeg_with_gps(), "image/jpeg")},
    )
    assert upload.status_code == 201, upload.text
    assert flood_state(client, "T-A")["state"] == "UNVERIFIED"  # 1 nguồn có ảnh vẫn chưa đủ

    post_report(client, auth_headers(register(client)))
    post_report(client, auth_headers(register(client)), level="knee")
    status = flood_state(client, "T-A")
    assert status["state"] == "CONFIRMED"

    feature = next(f for f in client.get("/api/v1/segments").json()["features"] if f["id"] == "T-A")
    assert feature["properties"]["status"]["state"] == "CONFIRMED"

    history = client.get("/api/v1/segments/T-A/history").json()["entries"]
    assert [h["state"] for h in history] == ["CONFIRMED", "UNVERIFIED"]
    assert history[1]["valid_to"] is not None

    changes = client.get("/api/v1/status/changes", params={"since": 0}).json()
    assert [c["code"] for c in changes["changes"]] == ["T-A"]
    assert (
        client.get("/api/v1/status/changes", params={"since": changes["next_since"]}).json()["changes"] == []
    )

    evidence = client.get("/api/v1/segments/T-A").json()["recent_evidence"]
    assert len(evidence) == 3
    assert all("actor_key" not in e and "device" not in str(e) for e in evidence)  # ẩn danh


def test_uploaded_photo_is_reencoded_without_metadata(client, area, device, settings):
    report_id = post_report(client, device).json()["id"]
    body = client.put(
        f"/api/v1/reports/{report_id}/media",
        headers=device,
        files={"file": ("a.jpg", jpeg_with_gps(), "image/jpeg")},
    ).json()
    assert max(body["width"], body["height"]) == 1600
    stored = list((__import__("pathlib").Path(settings.media_dir)).rglob("*.jpg"))
    assert len(stored) == 2  # ảnh + thumbnail
    for path in stored:
        with Image.open(path) as img:
            assert dict(img.getexif()) == {}


def test_upload_rejects_non_images_and_other_devices(client, area, device):
    report_id = post_report(client, device).json()["id"]
    not_image = client.put(
        f"/api/v1/reports/{report_id}/media",
        headers=device,
        files={"file": ("a.jpg", b"<script>alert(1)</script>", "image/jpeg")},
    )
    assert not_image.status_code == 415
    other = auth_headers(register(client))
    stolen = client.put(
        f"/api/v1/reports/{report_id}/media",
        headers=other,
        files={"file": ("a.jpg", jpeg_with_gps(), "image/jpeg")},
    )
    assert stolen.status_code == 404


def test_reused_photo_is_flagged_and_gets_no_photo_bonus(client, area, device, db):
    photo = jpeg_with_gps()
    first = post_report(client, device).json()["id"]
    client.put(
        f"/api/v1/reports/{first}/media", headers=device, files={"file": ("a.jpg", photo, "image/jpeg")}
    )

    other = auth_headers(register(client))
    second = post_report(client, other, lat=16.4705, lon=107.5851).json()["id"]  # đoạn B
    body = client.put(
        f"/api/v1/reports/{second}/media", headers=other, files={"file": ("b.jpg", photo, "image/jpeg")}
    ).json()
    assert body["duplicate"] is True
    has_photo = db.execute(text("SELECT has_photo FROM observation WHERE source_ref = :r"), {"r": second})
    assert has_photo.scalar_one() is False


def test_snap_lists_nearby_candidates(client, area):
    body = client.get("/api/v1/snap", params={"lat": 16.4705, "lon": 107.5801}).json()
    assert body["in_pilot_area"] is True
    assert [c["code"] for c in body["candidates"]] == ["T-A"]
    outside = client.get("/api/v1/snap", params={"lat": 16.6, "lon": 107.7}).json()
    assert outside == {"in_pilot_area": False, "candidates": []}


def test_quick_confirm(client, area, device):
    conflict = client.post(
        "/api/v1/segments/T-A/confirm", headers=device, json={"dimension": "flood", "still_present": True}
    )
    assert conflict.status_code == 409  # chưa có trạng thái để xác nhận

    post_report(client, device)
    other = auth_headers(register(client))
    gone = client.post(
        "/api/v1/segments/T-A/confirm",
        headers=other,
        json={"dimension": "flood", "still_present": False, "lat": 16.4705, "lon": 107.5801},
    )
    assert gone.status_code == 201
    assert gone.json()["level"] == "dry"
    again = client.post(
        "/api/v1/segments/T-A/confirm", headers=other, json={"dimension": "flood", "still_present": False}
    )
    assert again.status_code == 429


def test_my_reports(client, area, device):
    post_report(client, device)
    reports = client.get("/api/v1/me/reports", headers=device).json()["reports"]
    assert len(reports) == 1
    assert reports[0]["segment"]["code"] == "T-A"
    assert reports[0]["status"] == "pending"


def test_decay_to_stale_then_no_data(client, area, device, db):
    post_report(client, device)
    segment_id = area["A"].id
    now = datetime.now(UTC)
    assert status_engine.recompute_all_active(db, now + timedelta(hours=4)) == 1
    assert flood_state(client, "T-A")["state"] == "STALE"
    status_engine.recompute_all_active(db, now + timedelta(hours=25))
    assert flood_state(client, "T-A")["state"] == "NO_DATA"
    causes = (
        db.execute(
            text("SELECT cause FROM segment_status_history WHERE segment_id = :s ORDER BY id"),
            {"s": segment_id},
        )
        .scalars()
        .all()
    )
    assert causes == ["new_evidence", "decay", "expiry"]


def test_image_processing_rejects_bad_format():
    from app.core.errors import AppError
    from app.services.media import process_image

    gif = io.BytesIO()
    Image.new("RGB", (10, 10)).save(gif, "GIF")
    with pytest.raises(AppError) as exc:
        process_image(gif.getvalue())
    assert exc.value.code == "UNSUPPORTED_IMAGE"
