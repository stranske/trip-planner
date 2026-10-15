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


def test_health_reports_the_rail_timetable_in_three_distinct_states(monkeypatch, tmp_path) -> None:
    """The deploy fetches the Amtrak timetable; /api/health is how a deployed server shows
    whether that worked. "Not configured", "configured but unreadable" (a failed download)
    and "loaded" must read differently, and none of them makes the service degraded."""

    from zipfile import ZipFile

    from trip_planner.sources import rail_schedule

    from trip_planner.persistence.db import reset_database_state

    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'health.db'}")
    reset_database_state()
    monkeypatch.delenv(rail_schedule.FEED_PATH_ENV, raising=False)
    client = TestClient(create_app())
    body = client.get("/api/health").json()
    assert body["rail_timetable"]["status"] == "not_configured"

    monkeypatch.setenv(rail_schedule.FEED_PATH_ENV, str(tmp_path / "missing" / "GTFS.zip"))
    body = client.get("/api/health").json()
    assert body["rail_timetable"]["status"] == "feed_unreadable"
    assert body["rail_timetable"]["reason"] == "FileNotFoundError"
    assert body["status"] == "ok"

    feed = tmp_path / "GTFS.zip"
    with ZipFile(feed, "w") as archive:
        archive.writestr(
            "stops.txt",
            "stop_id,stop_name,stop_lat,stop_lon\nNYP,New York,40.75,-73.99\nPHL,Philadelphia,39.95,-75.18\n",
        )
        archive.writestr(
            "routes.txt",
            "route_id,route_short_name,route_long_name,route_type\nNER,,Northeast Regional,2\n",
        )
        archive.writestr(
            "trips.txt", "route_id,service_id,trip_id,trip_headsign\nNER,DAILY,171,Washington\n"
        )
        archive.writestr(
            "stop_times.txt",
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            "171,07:00:00,07:00:00,NYP,1\n171,08:20:00,08:22:00,PHL,2\n",
        )
    monkeypatch.setenv(rail_schedule.FEED_PATH_ENV, str(feed))
    body = client.get("/api/health").json()
    assert body["rail_timetable"] == {
        "status": "loaded",
        "feed_name": "GTFS.zip",
        "reason": None,
        "stations": 2,
        "trips": 1,
    }
