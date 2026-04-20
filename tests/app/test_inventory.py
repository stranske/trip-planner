from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.app.services import inventory as inventory_service
from trip_planner.app.services.inventory import (
    _build_inventory_assembly_input,
    assemble_inventory_bundles_for_trip,
)
from trip_planner.persistence.db import reset_database_state

_LEGACY_FIXTURE_BUNDLE_IDS = {
    "bundle-osaka-gateway",
    "bundle-kyoto-culture-day",
    "bundle-osaka-arrival",
}
_FIXTURE_ADAPTER_MARKERS = {
    "PersistedTripInventoryFixtureAdapter",
    "persisted-trip-fixture-inventory",
}


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


def test_seeded_inventory_assembly_uses_adapter_record_payloads_as_main_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assembly_input = _build_inventory_assembly_input(
        trip_id="trip-leisure-kyoto-draft",
        trip_mode="leisure",
        allow_fixture_fallback=True,
        prefer_persisted_context=False,
    )
    assert assembly_input.record_payloads

    def _fail_fixture_load(name: str) -> None:
        raise AssertionError(f"fixture file loader should not be used for main path: {name}")

    monkeypatch.setattr(inventory_service, "_load_mixed_option_fixture", _fail_fixture_load)

    bundles = assemble_inventory_bundles_for_trip(assembly_input=assembly_input)

    assert bundles
    assert bundles[0].bundle_id == "bundle-osaka-gateway"


def test_inventory_endpoint_returns_not_found_for_unknown_trip(client: TestClient) -> None:
    response = client.get("/api/inventory/trip-unknown")

    assert response.status_code == 404


def test_inventory_assembly_input_prefers_persisted_context_over_seeded_fixture_ids() -> None:
    assembly_input = _build_inventory_assembly_input(
        trip_id="trip-leisure-kyoto-draft",
        trip_mode="leisure",
        start_date="2026-09-10",
        end_date="2026-09-13",
        duration_days=4,
        primary_regions=["Lisbon"],
        traveler_party_kind="solo",
        traveler_count=1,
        allow_fixture_fallback=True,
        prefer_persisted_context=True,
    )

    assert assembly_input.snapshot.adapter_id == "persisted-trip-source-inventory"
    assert assembly_input.fixture_names == ()
    assert assembly_input.record_payloads
    first_payload = assembly_input.record_payloads[0]["bundle_payloads"][0]
    assert first_payload["bundle_id"] == "bundle-trip-leisure-kyoto-draft-runtime-1-1"
    assert first_payload["destinations"][0]["name"] == "Lisbon gateway"


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


def test_inventory_endpoint_avoids_legacy_fixture_bundle_ids_for_arbitrary_persisted_trip(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Lisbon weekend",
            "summary": "Arbitrary persisted trips should not reuse fixture bundle IDs.",
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
    trip_id = created.json()["trip"]["trip_id"]

    response = client.get(f"/api/inventory/{trip_id}")

    assert response.status_code == 200
    payload = response.json()
    bundle_ids = {bundle["bundle_id"] for bundle in payload["bundles"]}
    assert bundle_ids
    assert bundle_ids.isdisjoint(_LEGACY_FIXTURE_BUNDLE_IDS)
    bundle = payload["bundles"][0]
    assert bundle["destinations"][0]["geo"]["country_code"] == "PT"
    assert bundle["destinations"][0]["geo"]["time_zone"] == "Europe/Lisbon"
    assert bundle["transport_options"][0]["timing_summary"]["departure_local"] == (
        "2026-06-04T09:00:00Z"
    )
    assert bundle["transport_options"][0]["timing_summary"]["arrival_local"] == (
        "2026-06-04T09:45:00Z"
    )
    assert bundle["transport_options"][0]["source_refs"][0]["captured_at"] == (
        "2026-06-04T00:00:00Z"
    )
    serialized = str(payload["summary"])
    for marker in _FIXTURE_ADAPTER_MARKERS:
        assert marker not in serialized


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
