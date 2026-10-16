import uuid

from tests.factories import auth_headers, register


def test_register_and_reregister_device(client):
    device_id = str(uuid.uuid4())
    first = register(client, device_id)
    assert first["device_id"] == device_id
    assert first["role"] == "citizen"
    assert first["access_token"] and first["refresh_token"]
    again = register(client, device_id)
    assert again["refresh_token"] != first["refresh_token"]


def test_refresh_rotates_and_old_token_is_revoked(client):
    tokens = register(client)
    rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert rotated.status_code == 200
    reused = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"


def test_protected_endpoint_requires_valid_token(client):
    assert client.get("/api/v1/me/reports").json()["error"]["code"] == "UNAUTHORIZED"
    bad = client.get("/api/v1/me/reports", headers={"Authorization": "Bearer nope"})
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "INVALID_TOKEN"
    tokens = register(client)
    assert client.get("/api/v1/me/reports", headers=auth_headers(tokens)).status_code == 200


def test_banned_device_is_rejected(client, db):
    from sqlalchemy import text

    tokens = register(client)
    db.execute(text("UPDATE device SET is_banned = true WHERE id = :id"), {"id": tokens["device_id"]})
    response = client.get("/api/v1/me/reports", headers=auth_headers(tokens))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "DEVICE_BANNED"


def test_new_devices_per_ip_are_rate_limited(client, settings):
    settings.max_devices_per_ip_hour = 2
    register(client)
    register(client)
    third = client.post("/api/v1/auth/device", json={"device_id": str(uuid.uuid4())})
    assert third.status_code == 429


def test_production_requires_real_jwt_secret():
    import pytest
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="production", include_demo_data=False)
    Settings(_env_file=None, app_env="production", include_demo_data=False, jwt_secret="x" * 40)


def test_reregistering_device_revokes_previous_session(client):
    device_id = str(uuid.uuid4())
    first = register(client, device_id)
    register(client, device_id)  # mất refresh token → đăng ký lại
    old = client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert old.status_code == 401
