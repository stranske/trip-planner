"""The gate for issue 1839: Compare shows only options derived from the trip.

Varying-input probe, 2026-09-22 (Code/Audits/trip-planner/2026-09-22-assets/evidence/probes.json):
the lead route's travel time followed the trip (Seattle->Chicago 410 min, Boston->Chicago 300,
Seattle->Reykjavik 643), but the two "alternatives" were always the lead +45 and +90 minutes
with +1 and +2 transfers, for every trip. And every business trip carried an invented "Client
priority planning block" meeting that drove feasibility.

These tests read the served workspace payload for trips that differ in one determinant.
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
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'compare.db'}")
    reset_database_state()
    ensure_database_ready()
    with TestClient(create_app()) as test_client:
        test_client.post(
            "/api/auth/signup",
            json={"email": "c@example.com", "password": "password123", "display_name": "C"},
        )
        yield test_client
    reset_database_state()


def _scenarios(client: TestClient, *, origin: str, destination: str) -> list[dict[str, Any]]:
    created = client.post(
        "/api/trips",
        json={
            "title": f"{origin} to {destination}",
            "summary": "Client review.",
            "mode": "business",
            "trip_frame": {
                "origin": origin,
                "start_date": "2026-10-05",
                "end_date": "2026-10-07",
                "duration_days": 3,
                "primary_regions": [destination],
            },
        },
    )
    assert created.status_code == 201, created.text
    trip_id = created.json()["trip"]["trip_id"]
    workspace = client.get(f"/api/workspace/{trip_id}")
    assert workspace.status_code == 200, workspace.text
    return list(workspace.json()["runtime_scenario_comparison"]["scenarios"])


def _offsets(scenarios: list[dict[str, Any]]) -> list[tuple[Any, Any]]:
    lead = scenarios[0]["metrics"]
    return [
        (row["metrics"]["travel_minutes"] - lead["travel_minutes"], row["metrics"]["transfers"])
        for row in scenarios[1:]
    ]


def test_no_alternative_is_a_fixed_offset_of_the_lead(client: TestClient) -> None:
    seattle = _scenarios(client, origin="Seattle", destination="Chicago, IL")
    boston = _scenarios(client, origin="Boston", destination="Chicago, IL")

    # The lead is real: it follows the origin.
    assert seattle[0]["metrics"]["travel_minutes"] != boston[0]["metrics"]["travel_minutes"]
    # Any alternative must be derived from the trip, so two trips cannot share the same
    # offsets from their leads. The padding produced [(45, 1), (90, 2)] for both.
    if len(seattle) > 1 and len(boston) > 1:
        assert _offsets(seattle) != _offsets(boston)
    assert (45, 1) not in _offsets(seattle)
    assert (90, 2) not in _offsets(seattle)


def test_no_option_is_titled_as_a_generated_variant(client: TestClient) -> None:
    titles = {row["title"] for row in _scenarios(client, origin="Seattle", destination="Chicago, IL")}
    assert "Reverse-order route option" not in titles
    assert "Loop route option" not in titles


def test_no_open_question_cites_an_activity_the_trip_does_not_contain(client: TestClient) -> None:
    for destination in ("Chicago, IL", "Reykjavik"):
        for row in _scenarios(client, origin="Seattle", destination=destination):
            text = " ".join(
                [*(row.get("unresolved_questions") or []), *(row.get("highlights") or [])]
            )
            assert "Client priority planning block" not in text
            assert "anchor experience" not in text


def test_an_invented_meeting_no_longer_marks_a_trip_infeasible(client: TestClient) -> None:
    """Reykjavik was marked "not recommended" because the invented meeting could not be
    reached inside its advertised start window."""

    rows = _scenarios(client, origin="Seattle", destination="Reykjavik")
    assert rows
    assert "activity_start_window_missed" not in str(rows)
