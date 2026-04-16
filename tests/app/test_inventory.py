from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.persistence.db import reset_database_state


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'inventory.db'}")
    reset_database_state()
    app = create_app()

    with TestClient(app) as test_client:
        test_client.post(
            "/api/auth/signup",
            json={
                "email": "inventory@example.com",
                "password": "password123",
                "display_name": "Inventory Owner",
            },
        )
        yield test_client

    reset_database_state()


def test_inventory_endpoint_returns_seeded_bundle_payload(client: TestClient) -> None:
    response = client.get("/api/inventory/trip-leisure-kyoto-draft")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trip_id"] == "trip-leisure-kyoto-draft"
    assert payload["bundle_count"] == 2
    assert payload["bundles"][0]["bundle_id"] == "bundle-osaka-gateway"
    assert payload["summary"]["bundles"][1]["title"] == "Kyoto cultural anchor"
    assert payload["summary"]["bundles"][1]["option_count"] == 3


def test_inventory_endpoint_returns_not_found_for_unknown_trip(client: TestClient) -> None:
    response = client.get("/api/inventory/trip-unknown")

    assert response.status_code == 404


def test_inventory_endpoint_assembles_bundles_for_persisted_trip(client: TestClient) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Chicago kickoff",
            "summary": "Persisted trip inventory should use the adapter-backed assembly path.",
            "mode": "business",
            "trip_frame": {
                "start_date": "2026-05-04",
                "end_date": "2026-05-06",
                "duration_days": 3,
                "primary_regions": ["Chicago"],
            },
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]

    response = client.get(f"/api/inventory/{trip_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trip_id"] == trip_id
    assert payload["bundle_count"] == 1
    assert payload["bundles"][0]["bundle_id"].startswith("bundle-")
    assert payload["summary"]["runtime_state"]["status"] == "ready"
    assert any(
        "adapter-backed inventory assembly seam" in note for note in payload["summary"]["notes"]
    )


def test_inventory_endpoint_surfaces_partial_runtime_state_when_trip_dates_are_missing(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Chicago kickoff draft",
            "summary": "Regions exist, but dates do not yet.",
            "mode": "business",
            "trip_frame": {
                "primary_regions": ["Chicago"],
            },
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]

    response = client.get(f"/api/inventory/{trip_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["bundle_count"] == 0
    assert payload["summary"]["runtime_state"]["status"] == "partial"
    assert "duration" in payload["summary"]["notes"][0].lower()


def test_inventory_endpoint_returns_bounded_empty_fallback_for_partial_trip_input(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Unscoped trip",
            "summary": "Missing region context should not crash inventory assembly.",
            "mode": "leisure",
            "trip_frame": {
                "traveler_party": {
                    "kind": "solo",
                    "traveler_count": 1,
                    "notes": "",
                },
                "primary_regions": [],
            },
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]

    response = client.get(f"/api/inventory/{trip_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trip_id"] == trip_id
    assert payload["bundle_count"] == 0
    assert payload["summary"]["runtime_state"]["status"] == "empty"
    assert "Primary regions are still missing" in payload["summary"]["notes"][0]
