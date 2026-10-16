def test_liveness(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_reports_postgis_version(client):
    response = client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["postgis_version"].startswith("3.")
    assert body["postgres_version"]


def test_request_id_header(client):
    response = client.get("/health", headers={"X-Request-Id": "abc123"})
    assert response.headers["X-Request-Id"] == "abc123"


def test_unknown_route_uses_error_format(client):
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_unsafe_request_id_is_replaced(client):
    response = client.get("/health", headers={"X-Request-Id": "abc\r\nfake log line"})
    assert response.headers["X-Request-Id"] != "abc\r\nfake log line"
    assert len(response.headers["X-Request-Id"]) == 16


def test_unexpected_error_uses_error_format(db, settings):
    from fastapi.testclient import TestClient

    from app.db.session import get_db
    from app.main import create_app

    app = create_app(settings)

    def broken_db():
        raise RuntimeError("boom")
        yield  # pragma: no cover

    app.dependency_overrides[get_db] = broken_db
    with TestClient(app, raise_server_exceptions=False) as c:
        response = c.get("/health/ready")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "boom" not in response.text
