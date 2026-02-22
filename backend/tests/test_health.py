from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_returns_200():
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_healthy():
    response = client.get("/health")
    assert response.json() == {"status": "healthy"}
