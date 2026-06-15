import logging

from fastapi.testclient import TestClient

from trip_planner.app import main as main_module
from trip_planner.app.main import app, create_app


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


def test_startup_degrades_when_database_initialization_fails(
    monkeypatch, caplog
) -> None:
    """Resilient startup: if ensure_database_ready() raises (e.g. an expired/
    unreachable database), the service must still start and serve /api/health
    rather than crash the deploy."""

    def _raise_database_outage() -> None:
        raise RuntimeError("simulated database outage at startup")

    monkeypatch.setattr(main_module, "ensure_database_ready", _raise_database_outage)

    with caplog.at_level(logging.ERROR):
        # Using TestClient as a context manager runs the lifespan (startup).
        with TestClient(create_app()) as client:
            response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert any("degraded mode" in record.message for record in caplog.records)
