"""A timetabled train reaches the workspace from the Amtrak schedule feed.

The Amtrak GTFS adapter (PR 1857) was merged and called by nothing. Every assertion here
reads the served workspace payload for a trip, with a small Northeast Corridor timetable:
an Acela on weekdays only, a Northeast Regional every day, and a train the other way.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.persistence.db import ensure_database_ready, reset_database_state
from trip_planner.sources import rail_schedule

FEED = {
    "agency.txt": "agency_id,agency_name,agency_url,agency_timezone\n"
    "AMTK,Amtrak,https://www.amtrak.com,America/New_York\n",
    "stops.txt": "stop_id,stop_name,stop_lat,stop_lon\n"
    "BOS,Boston South Station,42.3523,-71.0552\n"
    "PVD,Providence,41.8295,-71.4134\n"
    "NYP,New York Penn Station,40.7506,-73.9935\n",
    "routes.txt": "route_id,agency_id,route_short_name,route_long_name,route_type\n"
    "ACELA,AMTK,ACELA,Acela,2\nNER,AMTK,NER,Northeast Regional,2\n",
    "trips.txt": "route_id,service_id,trip_id,trip_headsign,direction_id\n"
    "ACELA,WEEKDAY,2150,New York,0\nNER,DAILY,171,New York,0\nNER,DAILY,172,Boston,1\n",
    "stop_times.txt": "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
    "2150,06:00:00,06:00:00,BOS,1\n2150,06:35:00,06:37:00,PVD,2\n2150,09:40:00,09:40:00,NYP,3\n"
    "171,05:00:00,05:00:00,BOS,1\n171,05:45:00,05:47:00,PVD,2\n171,09:30:00,09:30:00,NYP,3\n"
    "172,07:00:00,07:00:00,NYP,1\n172,09:50:00,09:52:00,PVD,2\n172,10:30:00,10:30:00,BOS,3\n",
    "calendar.txt": "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,"
    "start_date,end_date\n"
    "WEEKDAY,1,1,1,1,1,0,0,20260901,20270901\nDAILY,1,1,1,1,1,1,1,20260901,20270901\n",
}


def _feed(tmp_path: Path, *, with_calendar: bool = True) -> Path:
    path = tmp_path / ("GTFS.zip" if with_calendar else "GTFS-nocal.zip")
    with ZipFile(path, "w") as archive:
        for name, body in FEED.items():
            if name == "calendar.txt" and not with_calendar:
                continue
            archive.writestr(name, body)
    return path


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'rail.db'}")
    monkeypatch.delenv(rail_schedule.FEED_PATH_ENV, raising=False)
    reset_database_state()
    ensure_database_ready()
    with TestClient(create_app()) as test_client:
        test_client.post(
            "/api/auth/signup",
            json={"email": "r@example.com", "password": "password123", "display_name": "Ria"},
        )
        yield test_client
    reset_database_state()


def _workspace(client: TestClient, origin: str, destination: str, day: str) -> dict[str, Any]:
    created = client.post(
        "/api/trips",
        json={
            "title": "Client visit",
            "summary": "Quarterly review.",
            "mode": "business",
            "trip_frame": {
                "origin": origin,
                "start_date": day,
                "end_date": day,
                "duration_days": 1,
                "primary_regions": [destination],
            },
        },
    )
    assert created.status_code == 201, created.text
    response = client.get(f"/api/workspace/{created.json()['trip']['trip_id']}")
    assert response.status_code == 200, response.text
    return dict(response.json())


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return list(payload["runtime_scenario_comparison"]["scenarios"])


def _rail(payload: dict[str, Any]) -> dict[str, Any]:
    (row,) = [row for row in _rows(payload) if "Amtrak" in row["title"]]
    return row


def test_without_a_timetable_the_server_says_so(client: TestClient) -> None:
    payload = _workspace(client, "Boston", "New York, NY", "2026-10-13")

    assert payload["inventory_summary"]["rail_lookup"]["status"] == rail_schedule.NOT_CONFIGURED
    assert len(_rows(payload)) == 1


def test_a_weekday_trip_gets_the_fastest_direct_train(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(rail_schedule.FEED_PATH_ENV, str(_feed(tmp_path)))
    payload = _workspace(client, "Boston", "New York, NY", "2026-10-13")  # a Tuesday

    assert payload["inventory_summary"]["rail_lookup"]["status"] == rail_schedule.FOUND
    assert len(_rows(payload)) == 2
    rail = _rail(payload)
    assert rail["title"] == "Boston → New York, NY by Amtrak (Acela)"
    assert rail["metrics"]["travel_minutes"] == 220  # 06:00 to 09:40
    assert rail["metrics"]["transfers"] == 0  # a direct train: measured, not assumed
    assert rail["availability_checked"] is False
    assert rail["metrics"]["estimated_total"] is None
    assert rail["route_stops"] == ["Boston", "New York, NY"]
    assert "Boston South Station 06:00" in rail["summary"]
    assert "No fare" in rail["summary"]


def test_a_saturday_trip_does_not_get_a_weekday_only_train(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(rail_schedule.FEED_PATH_ENV, str(_feed(tmp_path)))
    rail = _rail(_workspace(client, "Boston", "New York, NY", "2026-10-17"))

    assert rail["title"].endswith("(Northeast Regional)")
    assert rail["metrics"]["travel_minutes"] == 270


def test_a_timetable_without_a_calendar_says_the_date_was_not_checked(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(rail_schedule.FEED_PATH_ENV, str(_feed(tmp_path, with_calendar=False)))
    rail = _rail(_workspace(client, "Boston", "New York, NY", "2026-10-17"))

    assert "date was not checked" in rail["summary"]


def test_places_without_stations_get_no_train_and_say_why(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(rail_schedule.FEED_PATH_ENV, str(_feed(tmp_path)))
    payload = _workspace(client, "Seattle", "Chicago, IL", "2026-10-13")

    lookup = payload["inventory_summary"]["rail_lookup"]
    assert lookup["status"] == rail_schedule.NO_STATION_NEAR_ORIGIN
    assert "Seattle" in lookup["summary"]
    assert len(_rows(payload)) == 1
