"""What the workspace says about a measured route is in the traveller's words (issue 1844).

Observed 2026-09-22: "Chicago, IL runtime bundle", "Runtime inventory assembled from
persisted trip context", stops shown as "Dest-Gateway-Chicago-Il", "Route stop 1 of 2,
sourced from the ranked scenario route sequence", and no route started where the traveller
does, though the 410 minutes were measured from Seattle. Reads the served payload.
"""

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.persistence.db import ensure_database_ready, reset_database_state

JARGON = re.compile(
    r"runtime bundle|runtime inventory|persisted|synthesi[sz]ed|dest-|sourced from the ranked",
    re.IGNORECASE,
)


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'plain.db'}")
    reset_database_state()
    ensure_database_ready()
    with TestClient(create_app()) as client:
        client.post(
            "/api/auth/signup",
            json={"email": "p@example.com", "password": "password123", "display_name": "Dana"},
        )
        created = client.post(
            "/api/trips",
            json={
                "title": "Client review",
                "summary": "Quarterly review.",
                "mode": "business",
                "trip_frame": {
                    "origin": "Seattle",
                    "start_date": "2026-10-05",
                    "end_date": "2026-10-07",
                    "duration_days": 3,
                    "primary_regions": ["Chicago, IL"],
                },
            },
        )
        yield client.get(f"/api/workspace/{created.json()['trip']['trip_id']}").json()
    reset_database_state()


def _visible_strings(row: dict[str, Any]) -> list[str]:
    markers = (row.get("map_view") or {}).get("place_markers") or []
    return [
        row["title"],
        row["summary"],
        row["route_summary"],
        str(row.get("purpose") or ""),
        *row["highlights"],
        *[marker["label"] for marker in markers],
        *[marker["description"] for marker in markers],
    ]


def test_a_measured_route_is_described_in_the_travellers_words(
    workspace: dict[str, Any],
) -> None:
    (row,) = workspace["runtime_scenario_comparison"]["scenarios"]

    leaked = [text for text in _visible_strings(row) if JARGON.search(text)]
    assert leaked == []
    assert row["title"] == "Seattle → Chicago, IL"
    assert row["summary"].startswith("Measured from Seattle:")


def test_every_route_display_starts_where_the_traveller_does(workspace: dict[str, Any]) -> None:
    (row,) = workspace["runtime_scenario_comparison"]["scenarios"]

    assert row["route_stops"] == ["Seattle", "Chicago, IL"]
    assert row["route_summary"] == "Seattle → Chicago, IL"
    markers = row["map_view"]["place_markers"]
    assert [marker["label"] for marker in markers] == ["Seattle", "Chicago, IL"]
    assert markers[0]["description"] == "Where the journey starts."
