from fastapi.testclient import TestClient

from app.main import APP_VERSION, app

client = TestClient(app)


def test_live() -> None:
    response = client.get("/api/v1/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version() -> None:
    response = client.get("/api/v1/version")
    assert response.status_code == 200
    payload = response.json()
    assert payload["component"] == "bsm-backend"
    assert payload["version"] == APP_VERSION
    assert payload["api_version"] == "v1"
