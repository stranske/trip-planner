from fastapi.testclient import TestClient

from trip_planner.app import database_status
from trip_planner.app import main as main_module
from trip_planner.app.main import app, create_app


def test_health_endpoint_returns_live_status_contract() -> None:
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert {key: body[key] for key in ("service", "status", "environment", "version")} == {
        "service": "trip-planner-api",
        "status": "ok",
        "environment": "local",
        "version": "0.1.0",
    }
    assert body["database"]["ready"] is True
    assert body["database"]["reason"] is None


def test_startup_degrades_when_database_initialization_fails(monkeypatch) -> None:
    """Resilient startup, reported truthfully (issue 1851).

    If ensure_database_ready() raises (an expired or unreachable database), the service must
    still start and answer /api/health with 200, so the deploy is not failed. It must not say
    "ok": every trip request in that state errors, and the status page used to call it healthy.
    """

    def _raise_database_outage() -> None:
        raise RuntimeError("simulated database outage at startup")

    monkeypatch.setattr(main_module, "ensure_database_ready", _raise_database_outage)

    # Using TestClient as a context manager runs the lifespan (startup).
    with TestClient(create_app()) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"]["ready"] is False
    assert body["database"]["reason"] == "RuntimeError: database initialisation failed"
    assert body["database"]["checked_at"]
    # The reason names the failure class only; connection details never reach the page.
    assert "simulated" not in body["database"]["reason"]


def test_degraded_health_clears_when_the_database_comes_back(monkeypatch) -> None:
    """The degraded report is not a latch: a retry that finds the database clears it."""

    outage = {"on": True}

    def _database() -> None:
        if outage["on"]:
            raise RuntimeError("down")

    monkeypatch.setattr(main_module, "ensure_database_ready", _database)
    clock = {"now": 1000.0}
    monkeypatch.setattr(database_status.time, "monotonic", lambda: clock["now"])

    with TestClient(create_app()) as client:
        assert client.get("/api/health").json()["status"] == "degraded"

        outage["on"] = False
        # Inside the retry interval the last observation stands (health is polled often).
        clock["now"] += database_status.RETRY_INTERVAL_SECONDS / 2
        assert client.get("/api/health").json()["status"] == "degraded"

        clock["now"] += database_status.RETRY_INTERVAL_SECONDS
        recovered = client.get("/api/health").json()

    assert recovered["status"] == "ok"
    assert recovered["database"] == {
        "ready": True,
        "reason": None,
        "checked_at": recovered["database"]["checked_at"],
    }
