from fastapi.testclient import TestClient

from api.main import app


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_version_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/version")
    assert response.status_code == 200
    payload = response.json()
    assert "title" in payload
    assert "version" in payload
