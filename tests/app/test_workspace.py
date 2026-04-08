from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.persistence.db import reset_database_state


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv(
        "TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'workspace.db'}"
    )
    reset_database_state()
    app = create_app()

    with TestClient(app) as test_client:
        test_client.post(
            "/api/auth/signup",
            json={
                "email": "workspace@example.com",
                "password": "password123",
                "display_name": "Workspace Owner",
            },
        )
        yield test_client

    reset_database_state()


def test_workspace_endpoint_returns_trip_scenario_payload(client: TestClient) -> None:
    response = client.get("/api/workspace/trip-leisure-kyoto-draft")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trip_record"]["trip"]["trip_id"] == "trip-leisure-kyoto-draft"
    assert (
        payload["session"]["current_saved_scenario_id"]
        == "saved-scenario:kyoto-baseline"
    )
    assert payload["scenario_search"]["scenarios"][0]["scenario_summary"][
        "route_sequence"
    ] == [
        "kyoto",
        "uji",
        "kyoto",
    ]
    assert payload["inventory_summary"]["bundle_count"] == 2
    assert payload["inventory_summary"]["bundles"][0]["title"] == "Osaka arrival buffer"
    assert payload["planner_panel_state"]["trip"]["trip_id"] == "trip-leisure-kyoto-draft"
    assert payload["planner_panel_state"]["option_set"]["options"][0]["option_id"].startswith(
        "scenario:"
    )


def test_workspace_endpoint_returns_not_found_for_unknown_trip(
    client: TestClient,
) -> None:
    response = client.get("/api/workspace/trip-unknown")

    assert response.status_code == 404


def test_workspace_endpoint_returns_minimal_payload_for_persisted_trip(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Chicago kickoff",
            "summary": "Get into the workspace quickly.",
            "mode": "business",
            "trip_frame": {
                "start_date": "2026-05-04",
                "end_date": "2026-05-06",
                "duration_days": 3,
                "primary_regions": ["Chicago"],
                "traveler_party": {
                    "kind": "team",
                    "traveler_count": 3,
                    "notes": "Customer kickoff",
                },
            },
        },
    )
    trip_id = created.json()["trip"]["trip_id"]

    response = client.get(f"/api/workspace/{trip_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trip_record"]["trip"]["trip_id"] == trip_id
    assert payload["trip_record"]["trip"]["title"] == "Chicago kickoff"
    assert payload["trip_record"]["artifact_refs"]["session_state_id"] == f"session:{trip_id}"
    assert payload["session"]["trip_id"] == trip_id
    assert payload["saved_scenarios"] == []
    assert payload["scenario_search"]["scenarios"] == []
    assert payload["inventory_summary"]["bundle_count"] == 0
    assert payload["planner_panel_state"]["trip"]["trip_id"] == trip_id
    assert payload["planner_panel_state"]["option_set"]["purpose"] == "workspace_bootstrap"


def test_workspace_endpoint_hides_other_users_persisted_trips(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Kyoto Spring",
            "summary": "Food and gardens",
            "mode": "leisure",
            "trip_frame": {"duration_days": 7},
        },
    )
    trip_id = created.json()["trip"]["trip_id"]

    client.post("/api/auth/logout")
    client.post(
        "/api/auth/signup",
        json={
            "email": "other@example.com",
            "password": "password123",
            "display_name": "Other User",
        },
    )

    response = client.get(f"/api/workspace/{trip_id}")

    assert response.status_code == 404
