from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "ok"}


def test_list_students():
    resp = client.get("/api/students")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
