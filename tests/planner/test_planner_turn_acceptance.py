"""Failing acceptance tests for planner-turn execution and adjacent runtime contracts.

This module is the first wedge under stranske/trip-planner#956. Each test names the
design contract (epic doc / parent issue) it protects and is expected to fail until
the corresponding implementation lands. None of these tests pass by asserting only
on fixture or placeholder output.

The wider issue calls for failing acceptance tests across four areas — planner turn
execution, map target behavior, TPP approval flow, and preference-resolution
behavior. Preference resolution already has sustained coverage in
``tests/preferences/``. Of the three remaining wedges, the live-TPP and
route-context surfaces have since shipped under different names; their original
xfail tests have been removed and recorded in ``tests/planner/MIGRATIONS.md``.
The runtime-planning-services wedge below is now narrowed to the two outputs
that were deferred in the 2026-04-30 audit. It now asserts runtime payload data
for those outputs directly.

Tests run through the standard ``pytest`` invocation (e.g. ``pytest -q
tests/planner/test_planner_turn_acceptance.py``). New acceptance-style xfails
added in ``tests/planner/``, ``tests/contracts/``, or
``tests/integrations/`` must be ``strict=True`` (or carry an
``# xfail-exempt: <reason>`` marker on the decorator line); this is enforced
by ``scripts/check_xfail_strictness.py``.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.persistence.db import ensure_database_ready, reset_database_state


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'planner.db'}")
    reset_database_state()
    ensure_database_ready()
    app = create_app()

    with TestClient(app) as test_client:
        test_client.post(
            "/api/auth/signup",
            json={
                "email": "planner-acceptance@example.com",
                "password": "password123",
                "display_name": "Planner Acceptance",
            },
        )
        yield test_client

    reset_database_state()


def _assert_runtime_services_payload(payload: dict[str, Any]) -> None:
    scenario_search = payload["scenario_search"]
    ranking = payload["ranking"]
    route_comparison = payload["route_comparison"]

    assert isinstance(scenario_search, dict)
    assert isinstance(ranking, dict)
    assert isinstance(route_comparison, dict)
    assert ranking["rows"]
    assert route_comparison["scenarios"]
    assert ranking["lead_scenario_id"] == scenario_search["scenarios"][0]["scenario_id"]
    assert route_comparison["lead_scenario_id"] == scenario_search["scenarios"][0]["scenario_id"]
    assert payload["runtime_scenario_comparison"] == route_comparison


def test_planner_turn_surfaces_runtime_planning_services_outputs(client: TestClient) -> None:
    """Runtime-planning-services-epic #677 (children #690-#693) acceptance contract.

    The epic commits to exposing four runtime-planning-service outputs through the
    planner-turn → workspace path:

    - inventory bundle assembly (#690)
    - feasibility and move-cost evaluation (#691)
    - ranking and scenario generation (#692)
    - route search and scenario comparison (#693)

    The 2026-04-30 audit (issue #1046) confirmed that #690 (surfaced as
    ``inventory_summary``) and #691 (surfaced as ``feasibility_summary``)
    are top-level workspace keys. This test now proves #692 (``ranking``)
    and #693 (``route_comparison``) are also real runtime payload data.
    """
    seeded = client.get("/api/workspace/trip-leisure-kyoto-draft")
    assert seeded.status_code == 200
    _assert_runtime_services_payload(seeded.json())

    created = client.post(
        "/api/trips",
        json={
            "title": "Acceptance weekend",
            "summary": "Runtime planner acceptance trip.",
            "mode": "leisure",
            "trip_frame": {
                "start_date": "2026-06-04",
                "end_date": "2026-06-07",
                "duration_days": 4,
                "primary_regions": ["Lisbon"],
            },
        },
    )
    assert created.status_code == 201

    fresh = client.get(f"/api/workspace/{created.json()['trip']['trip_id']}")
    assert fresh.status_code == 200
    _assert_runtime_services_payload(fresh.json())
