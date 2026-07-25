from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint_returns_request_id() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"]


def test_request_id_is_preserved() -> None:
    response = client.get("/api/v1/version", headers={"X-Request-ID": "test-request-id"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request-id"
    assert response.json()["api_version"] == "v1"


def test_ready_endpoint() -> None:
    response = client.get("/api/v1/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_openapi_contains_public_resources() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/health" in paths
    assert "/api/v1/version" in paths
    assert "/api/v1/organizations" in paths
    assert "/api/v1/installations" in paths
    assert "/api/v1/live" not in paths
