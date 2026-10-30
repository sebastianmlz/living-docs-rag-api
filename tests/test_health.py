from fastapi.testclient import TestClient

from ldr.api.main import app

client = TestClient(app)


def test_health_reports_pgvector() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["pgvector"] != "missing"
