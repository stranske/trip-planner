"""A timetabled train reaches the workspace from the Amtrak schedule feed.

The Amtrak GTFS adapter (PR 1857) was merged and called by nothing. Every assertion here
reads the served workspace payload for a trip, with a small Northeast Corridor timetable:
an Acela on weekdays only, a Northeast Regional every day, and a train the other way.
"""

import csv
import io
import json
from collections.abc import Iterator
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from scripts import probe_rail_timetable
from scripts.probe_rail_timetable import (
    IndependentTimetable,
    IndependentTrain,
    workspace_agrees,
)
from trip_planner.app.main import create_app
from trip_planner.geo.resolver import resolve_place
from trip_planner.persistence.db import ensure_database_ready, reset_database_state
from trip_planner.sources import rail_schedule

FEED = {
    "agency.txt": "agency_id,agency_name,agency_url,agency_timezone\n"
    "AMTK,Amtrak,https://www.amtrak.com,America/New_York\n",
    "stops.txt": "stop_id,stop_name,stop_lat,stop_lon\n"
    "BOS,Boston South Station,42.3523,-71.0552\n"
    "PVD,Providence,41.8295,-71.4134\n"
    "NYP,New York Penn Station,40.7506,-73.9935\n"
    "RTE,Route 128 Amtrak Station,42.2102,-71.1476\n"
    "CHI,Chicago Union Station,41.8789,-87.6403\n"
    "DEN,Denver,39.7525,-105.0000\n"
    "SLC,Salt Lake City,40.7497,-111.9122\n",
    # As in Amtrak's real feed: short names empty, Thruway buses (route_type 3) alongside
    # trains, and pickup_type / drop_off_type marking stops a train only sets down at.
    "routes.txt": "route_id,agency_id,route_short_name,route_long_name,route_type\n"
    "ACELA,AMTK,,Acela,2\nNER,AMTK,,Northeast Regional,2\n"
    "BUS,AMTK,,Amtrak Thruway Connecting Service,3\n"
    "CZ,AMTK,,California Zephyr,2\n",
    "trips.txt": "route_id,service_id,trip_id,trip_short_name,trip_headsign,direction_id\n"
    "ACELA,WEEKDAY,2150,2150,New York,0\nNER,DAILY,171,171,New York,0\n"
    "NER,DAILY,172,172,Boston,1\nBUS,DAILY,9001,9001,New York,0\n"
    "ACELA,WEEKDAY,2190,2190,New York,0\n"
    "ACELA,WEEKDAY,2191,2191,New York,0\n"
    "CZ,TUESDAY,5,5,Emeryville,0\n",
    "stop_times.txt": "trip_id,arrival_time,departure_time,stop_id,stop_sequence,"
    "pickup_type,drop_off_type\n"
    "2150,06:00:00,06:00:00,BOS,1,0,1\n2150,06:35:00,06:37:00,PVD,2,0,0\n"
    "2150,09:40:00,09:40:00,NYP,3,1,0\n"
    "171,05:00:00,05:00:00,BOS,1,0,1\n171,05:45:00,05:47:00,PVD,2,0,0\n"
    "171,09:30:00,09:30:00,NYP,3,1,0\n"
    # Northbound, it reaches Route 128 (inside 30 km of Boston) before South Station.
    "172,07:00:00,07:00:00,NYP,1,0,1\n172,09:50:00,09:52:00,PVD,2,0,0\n"
    "172,10:10:00,10:11:00,RTE,3,0,0\n172,10:30:00,10:30:00,BOS,4,1,0\n"
    # Leaves Chicago on Tuesdays only, so it boards Denver on Wednesdays (GTFS hour 31).
    "5,14:00:00,14:00:00,CHI,1,0,1\n5,31:00:00,31:10:00,DEN,2,0,0\n"
    "5,46:00:00,46:00:00,SLC,3,1,0\n"
    # A bus that is faster than any train: it must not be shown as a train.
    "9001,06:30:00,06:30:00,BOS,1,0,1\n9001,08:00:00,08:00:00,NYP,2,1,0\n"
    # The fastest Acela of all, but it does not pick up at Boston (set-down only).
    "2190,07:00:00,07:00:00,BOS,1,1,1\n2190,07:35:00,07:37:00,PVD,2,0,0\n"
    "2190,09:05:00,09:05:00,NYP,3,1,0\n"
    # Faster than the valid Acela, but passengers cannot alight in New York.
    "2191,08:00:00,08:00:00,BOS,1,0,1\n2191,10:00:00,10:00:00,NYP,2,1,1\n",
    "calendar.txt": "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,"
    "start_date,end_date\n"
    "WEEKDAY,1,1,1,1,1,0,0,20260901,20270901\nDAILY,1,1,1,1,1,1,1,20260901,20270901\n"
    "TUESDAY,0,1,0,0,0,0,0,20260901,20270901\n",
}


def _feed(
    tmp_path: Path,
    *,
    with_calendar: bool = True,
    extra_tables: dict[str, str] | None = None,
) -> Path:
    path = tmp_path / ("GTFS.zip" if with_calendar else "GTFS-nocal.zip")
    with ZipFile(path, "w") as archive:
        for name, body in (FEED | (extra_tables or {})).items():
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


def _workspace(
    client: TestClient, origin: str, destination: str, day: str | None
) -> dict[str, Any]:
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


def _probe_answer(
    feed: Path, origin: str, destination: str, day: str
) -> tuple[str, IndependentTrain | None]:
    return IndependentTimetable(str(feed)).answer(
        resolve_place(origin), resolve_place(destination), date.fromisoformat(day)
    )


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
    # Excludes the faster bus, the train without pickup, and the train without drop-off.
    assert rail["title"] == "Boston → New York, NY by Amtrak Acela"
    assert rail["metrics"]["travel_minutes"] == 220  # 06:00 to 09:40
    assert "Acela 2150" in rail["summary"]
    assert rail["metrics"]["transfers"] == 0  # a direct train: measured, not assumed
    assert rail["availability_checked"] is False
    assert rail["metrics"]["estimated_total"] is None
    assert rail["route_stops"] == ["Boston", "New York, NY"]
    assert "Boston South Station 06:00" in rail["summary"]
    assert "No fare" in rail["summary"]
    assert "Scheduled to run on 2026-10-13." in rail["summary"]
    assert (
        "Scheduled to run on 2026-10-13." in payload["inventory_summary"]["rail_lookup"]["summary"]
    )


def test_a_saturday_trip_does_not_get_a_weekday_only_train(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(rail_schedule.FEED_PATH_ENV, str(_feed(tmp_path)))
    rail = _rail(_workspace(client, "Boston", "New York, NY", "2026-10-17"))

    assert rail["title"].endswith("by Amtrak Northeast Regional")
    assert rail["metrics"]["travel_minutes"] == 270
    assert "Scheduled to run on 2026-10-17." in rail["summary"]


@pytest.mark.parametrize(
    ("day", "expected_status"),
    [
        ("2026-10-20", rail_schedule.NO_TRAIN_ON_DATE),
        ("2026-10-24", rail_schedule.FOUND),
    ],
)
def test_calendar_exceptions_control_the_train_and_service_date_shown(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    day: str,
    expected_status: str,
) -> None:
    feed = _feed(
        tmp_path,
        extra_tables={
            "calendar_dates.txt": "service_id,date,exception_type\n"
            "WEEKDAY,20261020,2\nDAILY,20261020,2\nWEEKDAY,20261024,1\n"
        },
    )
    monkeypatch.setenv(rail_schedule.FEED_PATH_ENV, str(feed))
    payload = _workspace(client, "Boston", "New York, NY", day)

    lookup = payload["inventory_summary"]["rail_lookup"]
    assert lookup["status"] == expected_status
    if expected_status == rail_schedule.FOUND:
        rail = _rail(payload)
        assert "Acela 2150" in rail["summary"]
        assert rail["metrics"]["travel_minutes"] == 220
        assert f"Scheduled to run on {day}." in lookup["summary"]
        assert f"Scheduled to run on {day}." in rail["summary"]
    else:
        assert len(_rows(payload)) == 1
        assert f"none on {day}" in lookup["summary"]


@pytest.mark.parametrize(
    ("with_calendar", "exceptions", "day", "expected_status", "expected_number"),
    [
        (True, "WEEKDAY,20261020,2\nDAILY,20261020,2\n", "2026-10-20", "no_train_on_date", None),
        (True, "WEEKDAY,20261024,1\n", "2026-10-24", "found", "2150"),
        (False, "WEEKDAY,20261024,1\n", "2026-10-24", "found", "2150"),
        (False, "WEEKDAY,20261024,1\n", "2026-10-25", "no_train_on_date", None),
        (False, None, "2026-10-24", "found", "2150"),
    ],
)
def test_independent_probe_checks_calendar_exceptions_and_missing_calendars(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    with_calendar: bool,
    exceptions: str | None,
    day: str,
    expected_status: str,
    expected_number: str | None,
) -> None:
    extra = (
        {"calendar_dates.txt": "service_id,date,exception_type\n" + exceptions}
        if exceptions is not None
        else {}
    )
    feed = _feed(tmp_path, with_calendar=with_calendar, extra_tables=extra)
    monkeypatch.setenv(rail_schedule.FEED_PATH_ENV, str(feed))
    payload = _workspace(client, "Boston", "New York, NY", day)
    status, expected = _probe_answer(feed, "Boston", "New York, NY", day)

    assert status == expected_status
    if expected_number is not None:
        assert expected is not None
        assert expected.number == expected_number
        assert expected.origin == "Boston South Station"
        assert expected.destination == "New York Penn Station"
        assert expected.departure_minutes == 360
        assert expected.arrival_minutes == 580
        assert expected.runs_on_date is (True if with_calendar or exceptions is not None else None)
    else:
        assert expected is None
    assert workspace_agrees(payload, status, expected, date.fromisoformat(day))


def test_probe_rejects_incorrect_times_stations_service_dates_and_pricing(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    feed = _feed(tmp_path)
    monkeypatch.setenv(rail_schedule.FEED_PATH_ENV, str(feed))
    payload = _workspace(client, "Boston", "New York, NY", "2026-10-13")
    status, expected = _probe_answer(feed, "Boston", "New York, NY", "2026-10-13")
    day = date(2026, 10, 13)
    assert workspace_agrees(payload, status, expected, day)

    for before, after in (
        ("Boston South Station", "Providence"),
        ("New York Penn Station", "Newark Penn Station"),
        ("06:00", "07:00"),
        ("09:40", "10:40"),
        ("Acela 2150", "Acela 2190"),
        ("2026-10-13", "2026-10-14"),
        ("No fare", "Fare included"),
    ):
        corrupted = deepcopy(payload)
        rail = _rail(corrupted)
        rail["summary"] = rail["summary"].replace(before, after)
        assert not workspace_agrees(corrupted, status, expected, day), (before, after)

    for metric, value in (("travel_minutes", 200), ("transfers", 1), ("estimated_total", 50)):
        corrupted = deepcopy(payload)
        _rail(corrupted)["metrics"][metric] = value
        assert not workspace_agrees(corrupted, status, expected, day), metric

    corrupted = deepcopy(payload)
    _rail(corrupted)["availability_checked"] = True
    assert not workspace_agrees(corrupted, status, expected, day)
    corrupted = deepcopy(payload)
    corrupted["inventory_summary"]["rail_lookup"]["summary"] = "Wrong journey"
    assert not workspace_agrees(corrupted, status, expected, day)
    corrupted = deepcopy(payload)
    corrupted["runtime_scenario_comparison"]["scenarios"].append(deepcopy(_rail(payload)))
    assert not workspace_agrees(corrupted, status, expected, day)


def test_a_timetable_without_a_calendar_says_the_date_was_not_checked(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(rail_schedule.FEED_PATH_ENV, str(_feed(tmp_path, with_calendar=False)))
    payload = _workspace(client, "Boston", "New York, NY", "2026-10-17")
    rail = _rail(payload)

    assert "date was not checked" in rail["summary"]
    assert "date was not checked" in payload["inventory_summary"]["rail_lookup"]["summary"]
    assert "Scheduled to run" not in rail["summary"]


def test_a_trip_without_a_travel_date_does_not_claim_the_calendar_is_missing(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(rail_schedule.FEED_PATH_ENV, str(_feed(tmp_path)))
    payload = _workspace(client, "Boston", "New York, NY", None)

    for summary in (
        _rail(payload)["summary"],
        payload["inventory_summary"]["rail_lookup"]["summary"],
    ):
        assert "No travel date was provided" in summary
        assert "date was not checked" in summary
        assert "no service calendar" not in summary
        assert "Scheduled to run" not in summary


def test_places_without_stations_get_no_train_and_say_why(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(rail_schedule.FEED_PATH_ENV, str(_feed(tmp_path)))
    payload = _workspace(client, "Seattle", "Chicago, IL", "2026-10-13")

    lookup = payload["inventory_summary"]["rail_lookup"]
    assert lookup["status"] == rail_schedule.NO_STATION_NEAR_ORIGIN
    assert "Seattle" in lookup["summary"]
    assert len(_rows(payload)) == 1


def test_the_train_stops_at_the_city_station_not_a_suburban_one_on_the_way(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real feed, 2026-10-14: Washington to Boston arrived at "Route 128" because the train
    reaches it minutes before South Station."""

    monkeypatch.setenv(rail_schedule.FEED_PATH_ENV, str(_feed(tmp_path)))
    rail = _rail(_workspace(client, "New York, NY", "Boston", "2026-10-13"))

    assert "Boston South Station 10:30" in rail["summary"]
    assert rail["metrics"]["travel_minutes"] == 210


def test_an_overnight_train_is_checked_for_the_day_it_boards_the_traveller(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GTFS counts times from the train's first departure: this one leaves Chicago on
    Tuesdays, so it leaves Denver on Wednesdays, at 07:10."""

    feed = _feed(tmp_path)
    monkeypatch.setenv(rail_schedule.FEED_PATH_ENV, str(feed))
    wednesday = _workspace(client, "Denver, CO", "Salt Lake City, UT", "2026-10-14")
    tuesday = _workspace(client, "Denver, CO", "Salt Lake City, UT", "2026-10-13")

    rail = _rail(wednesday)
    assert "Denver 07:10 → Salt Lake City 22:00," in rail["summary"]
    assert rail["metrics"]["travel_minutes"] == 890
    assert "Scheduled to run on 2026-10-14." in rail["summary"]
    assert tuesday["inventory_summary"]["rail_lookup"]["status"] == rail_schedule.NO_TRAIN_ON_DATE
    for payload, day in ((wednesday, "2026-10-14"), (tuesday, "2026-10-13")):
        status, expected = _probe_answer(feed, "Denver, CO", "Salt Lake City, UT", day)
        assert workspace_agrees(payload, status, expected, date.fromisoformat(day))


def test_a_two_day_train_arrives_at_the_city_and_displays_the_correct_day(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    feed = _feed(
        tmp_path,
        extra_tables={
            "stops.txt": FEED["stops.txt"]
            + "SEA,Seattle King Street Station,47.5984,-122.3299\n"
            + "GLN,Glenview,42.0751,-87.8055\n",
            "routes.txt": FEED["routes.txt"] + "EB,AMTK,,Empire Builder,2\n",
            "trips.txt": FEED["trips.txt"] + "EB,TUESDAY,8,8,Chicago,0\n",
            "stop_times.txt": FEED["stop_times.txt"]
            + "8,19:55:00,19:55:00,SEA,1,0,1\n"
            + "8,64:30:00,64:32:00,GLN,2,0,0\n"
            + "8,65:45:00,65:45:00,CHI,3,1,0\n",
        },
    )
    monkeypatch.setenv(rail_schedule.FEED_PATH_ENV, str(feed))
    payload = _workspace(client, "Seattle", "Chicago, IL", "2026-10-13")
    rail = _rail(payload)

    assert len(_rows(payload)) == 2
    assert rail["metrics"]["travel_minutes"] == 2750
    assert rail["metrics"]["transfers"] == 0
    assert rail["metrics"]["estimated_total"] is None
    for summary in (rail["summary"], payload["inventory_summary"]["rail_lookup"]["summary"]):
        assert (
            "Seattle King Street Station 19:55 → Chicago Union Station 17:45 (+2 days)" in summary
        )
        assert "Scheduled to run on 2026-10-13." in summary
    status, expected = _probe_answer(feed, "Seattle", "Chicago, IL", "2026-10-13")
    assert workspace_agrees(payload, status, expected, date(2026, 10, 13))
    corrupted = deepcopy(payload)
    _rail(corrupted)["summary"] = rail["summary"].replace("+2 days", "+1 day")
    assert not workspace_agrees(corrupted, status, expected, date(2026, 10, 13))


@pytest.mark.parametrize("restriction", ["pickup_type", "drop_off_type"])
def test_a_pair_with_only_restricted_trains_has_no_direct_train(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    restriction: str,
) -> None:
    # Leave the bus available so the absence also proves buses cannot substitute for rail.
    rows = list(csv.DictReader(io.StringIO(FEED["stop_times.txt"])))
    for row in rows:
        if row["trip_id"] != "9001":
            row[restriction] = "1"
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    feed = _feed(tmp_path, extra_tables={"stop_times.txt": stream.getvalue()})
    monkeypatch.setenv(rail_schedule.FEED_PATH_ENV, str(feed))
    payload = _workspace(client, "Boston", "New York, NY", "2026-10-13")

    assert payload["inventory_summary"]["rail_lookup"]["status"] == rail_schedule.NO_DIRECT_TRAIN
    assert len(_rows(payload)) == 1
    status, expected = _probe_answer(feed, "Boston", "New York, NY", "2026-10-13")
    assert status == "no_direct_train"
    assert expected is None
    assert workspace_agrees(payload, status, expected, date(2026, 10, 13))


def test_probe_reports_all_cases_and_fails_if_a_workspace_disagrees(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    feed = _feed(tmp_path)
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'probe.db'}")
    monkeypatch.setenv(rail_schedule.FEED_PATH_ENV, str(feed))
    monkeypatch.setattr(
        probe_rail_timetable,
        "PAIRS",
        [("Boston", "New York, NY"), ("Seattle", "Chicago, IL")],
    )
    monkeypatch.setattr(probe_rail_timetable, "DAYS", [date(2026, 10, 20), date(2026, 10, 24)])
    try:
        assert probe_rail_timetable.main(["probe", str(feed)]) == 0
        output = capsys.readouterr().out
        cases, pass_number = output.split("PASS NUMBER:")
        results = json.loads(cases)
        assert len(results) == 4
        assert all(row["agree"] for row in results)
        assert {row["served"] for row in results} == {"found", "no_station_near_origin"}
        assert pass_number.strip().startswith("4/4 ")

        monkeypatch.setattr(probe_rail_timetable, "workspace_agrees", lambda *args: False)
        assert probe_rail_timetable.main(["probe", str(feed)]) == 1
        assert "PASS NUMBER: 0/4 " in capsys.readouterr().out
    finally:
        reset_database_state()
