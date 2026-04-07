from fastapi.testclient import TestClient

from trip_planner.app.main import app


def test_health_endpoint_returns_live_status_contract() -> None:
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "service": "trip-planner-api",
        "status": "ok",
        "environment": "local",
        "version": "0.1.0",
    }
