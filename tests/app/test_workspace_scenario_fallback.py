"""Compare shows only what the planner measured (issues 1827, 1839).

Every assertion reads the served workspace payload. Before this:
- a destination the planner could not locate was shown two saved drafts with invented
  timings (duration x 120 minutes; +45 and 1 / 2 transfers for the "fallback");
- every trip read "0 transfers" (Seattle to Reykjavik included, which has no nonstop) and
  every card "Ready to review", though nothing counted connections or asked a provider
  about availability;
- a trip that flew to its first destination and drove to its second crashed the workspace
  with a 500, because its transport was labelled "mixed", which the contract rejects.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.persistence.db import ensure_database_ready, reset_database_state


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'measured.db'}")
    reset_database_state()
    ensure_database_ready()
    with TestClient(create_app()) as test_client:
        test_client.post(
            "/api/auth/signup",
            json={"email": "m@example.com", "password": "password123", "display_name": "Dana"},
        )
        yield test_client
    reset_database_state()


def _workspace(client: TestClient, *, origin: str, regions: list[str]) -> dict[str, Any]:
    created = client.post(
        "/api/trips",
        json={
            "title": " / ".join(regions),
            "summary": "Client review.",
            "mode": "business",
            "trip_frame": {
                "origin": origin,
                "start_date": "2026-10-05",
                "end_date": "2026-10-07",
                "duration_days": 3,
                "primary_regions": regions,
            },
        },
    )
    assert created.status_code == 201, created.text
    response = client.get(f"/api/workspace/{created.json()['trip']['trip_id']}")
    assert response.status_code == 200, response.text
    return dict(response.json())


def test_uncovered_destination_yields_no_substituted_scenarios(client: TestClient) -> None:
    payload = _workspace(client, origin="Seattle", regions=["Zzqxwv Nonexistent Place"])

    assert payload["runtime_scenario_comparison"]["scenarios"] == []
    assert payload["route_comparison"]["scenarios"] == []
    assert "nothing to compare" in payload["runtime_scenario_comparison"]["summary"]
    assert payload["runtime_state"]["title"] == (
        "The planner could not locate Zzqxwv Nonexistent Place"
    )
    # The traveller is not told planning has not started: setup is complete, and the next
    # step is the same as for any trip.
    assert payload["view_model"]["next_step"]["title"] == "Enter the prices you have"
    # No other city's itinerary stands in for this one.
    route_data = str([payload["scenario_search"], payload["runtime_scenario_comparison"]]).lower()
    assert "kyoto" not in route_data and "osaka" not in route_data


def test_covered_destination_keeps_its_measured_route(client: TestClient) -> None:
    seattle = _workspace(client, origin="Seattle", regions=["Chicago, IL"])
    boston = _workspace(client, origin="Boston", regions=["Chicago, IL"])

    (from_seattle,) = seattle["runtime_scenario_comparison"]["scenarios"]
    (from_boston,) = boston["runtime_scenario_comparison"]["scenarios"]
    assert from_seattle["metrics"]["travel_minutes"] != from_boston["metrics"]["travel_minutes"]


def test_an_unmeasured_connection_count_is_not_reported_as_zero(client: TestClient) -> None:
    for regions in (["Chicago, IL"], ["Reykjavik"]):
        payload = _workspace(client, origin="Seattle", regions=regions)
        (row,) = payload["runtime_scenario_comparison"]["scenarios"]
        assert row["metrics"]["transfers"] is None, regions
        assert row["delta"]["transfers_delta"] is None, regions
        assert row["availability_checked"] is False, regions
        assert not any("0 transfer" in item for item in row["highlights"]), row["highlights"]
        assert any("connections not measured" in item for item in row["highlights"])


def test_a_trip_that_flies_then_drives_is_served(client: TestClient) -> None:
    payload = _workspace(client, origin="Seattle", regions=["Austin, TX", "Dallas, TX"])

    (row,) = payload["runtime_scenario_comparison"]["scenarios"]
    assert row["metrics"]["travel_minutes"] > 0
