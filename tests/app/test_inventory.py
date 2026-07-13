import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.app.services.inventory import (
    _build_inventory_assembly_input,
    assemble_inventory_bundles_for_trip,
    build_inventory_summary_payload,
    lookup_region_coordinates,
)
from trip_planner.persistence.db import reset_database_state
from trip_planner.persistence.models.trip import PersistedTrip

_LEGACY_FIXTURE_BUNDLE_IDS = {
    "bundle-osaka-gateway",
    "bundle-kyoto-culture-day",
    "bundle-osaka-arrival",
}
_FIXTURE_ADAPTER_MARKERS = {
    "PersistedTripInventoryFixtureAdapter",
    "persisted-trip-fixture-inventory",
}


def test_known_region_coordinates_match_specific_route_aliases_first() -> None:
    assert lookup_region_coordinates("dest-gateway-washington-dc") == (
        38.8512,
        -77.0402,
    )
    assert lookup_region_coordinates("dest-city-washington-dc") == (
        38.9072,
        -77.0369,
    )
    assert lookup_region_coordinates("unlisted-place") is None


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


def test_inventory_assembly_prefers_persisted_trip_context_over_seeded_trip_id() -> None:
    persisted_trip = PersistedTrip(
        trip_id="trip-leisure-kyoto-draft",
        user_id="user-test",
        title="Lisbon override for seeded ID",
        summary="Persisted context should drive runtime inventory adapter selection.",
        mode="leisure",
        status="draft",
        start_date="2026-07-01",
        end_date="2026-07-05",
        duration_days=5,
        primary_regions=["Lisbon"],
        traveler_party_kind="solo",
        traveler_count=2,
        traveler_notes="",
    )

    assembly_input = _build_inventory_assembly_input(
        trip_id=persisted_trip.trip_id,
        trip_mode=persisted_trip.mode,
        persisted_trip=persisted_trip,
        allow_fixture_fallback=True,
    )

    assert assembly_input.snapshot.adapter_id == "persisted-trip-source-inventory"
    assert assembly_input.query.destination == "Lisbon"
    assert assembly_input.query.traveler_segment == "solo"
    assert assembly_input.record_payloads
    assert assembly_input.snapshot.records[0].payload_type == "runtime_bundle_seed"
    assert assembly_input.fixture_names == ()


def test_seeded_trip_inventory_assembly_uses_record_payload_contract() -> None:
    assembly_input = _build_inventory_assembly_input(
        trip_id="trip-leisure-kyoto-draft",
        trip_mode="leisure",
        primary_regions=("Kyoto",),
        duration_days=4,
    )

    assert assembly_input.snapshot.adapter_id == "persisted-trip-fixture-inventory"
    assert assembly_input.record_payloads
    assert assembly_input.record_payloads[0]["bundle_payloads"]

    bundles = assemble_inventory_bundles_for_trip(assembly_input=assembly_input)

    assert len(bundles) == 2
    assert bundles[0].bundle_id == "bundle-osaka-gateway"


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
    source_metadata = payload["summary"]["source_metadata"]
    assert source_metadata["source_type"] == "persisted_trip"
    assert source_metadata["origin"] == "runtime"
    assert source_metadata["adapter_name"] == "persisted-trip-source-inventory"
    provenance_context = source_metadata["provenance_context"]
    assert provenance_context["trip_id"] == trip_id
    assert provenance_context["trip_mode"] == "business"
    assert provenance_context["source_id"] == "persisted-trip-runtime-source"
    assert provenance_context["query_id"] == f"inventory-query:{trip_id}"
    assert provenance_context["handoff_id"] == f"handoff:{trip_id}:inventory"
    assert provenance_context["input_record_ids"]
    assert provenance_context["issue_codes"] == []
    assert provenance_context["filters"]["trip_mode"] == "business"
    assert provenance_context["notes"]
    serialized_source_metadata = json.dumps(source_metadata, sort_keys=True).lower()
    for forbidden_marker in ("fixture", "seed", "demo", "persistedtripinventoryfixtureadapter"):
        assert forbidden_marker not in serialized_source_metadata


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


def test_inventory_summary_source_metadata_is_runtime_derived_for_persisted_trip() -> None:
    persisted_trip = PersistedTrip(
        trip_id="trip-runtime-provenance-check",
        user_id="user-test",
        title="Chicago workshop",
        summary="Verify runtime source metadata shape.",
        mode="business",
        status="draft",
        start_date="2026-05-04",
        end_date="2026-05-06",
        duration_days=3,
        primary_regions=["Chicago"],
        traveler_party_kind="team",
        traveler_count=3,
        traveler_notes="",
    )
    assembly_input = _build_inventory_assembly_input(
        trip_id=persisted_trip.trip_id,
        trip_mode=persisted_trip.mode,
        persisted_trip=persisted_trip,
        allow_fixture_fallback=False,
    )
    bundles = assemble_inventory_bundles_for_trip(assembly_input=assembly_input)

    summary = build_inventory_summary_payload(bundles, assembly_input=assembly_input)

    source_metadata = summary["source_metadata"]
    assert source_metadata["source_type"] == "persisted_trip"
    assert source_metadata["origin"] == "runtime"
    assert source_metadata["adapter_name"] == "persisted-trip-source-inventory"
    provenance_context = source_metadata["provenance_context"]
    assert provenance_context["trip_id"] == persisted_trip.trip_id
    assert provenance_context["trip_mode"] == "business"
    assert provenance_context["source_id"] == "persisted-trip-runtime-source"
    assert provenance_context["query_id"] == f"inventory-query:{persisted_trip.trip_id}"
    assert provenance_context["handoff_id"] == f"handoff:{persisted_trip.trip_id}:inventory"
    assert provenance_context["input_record_ids"]
    assert provenance_context["issue_codes"] == []
    assert provenance_context["filters"]["trip_mode"] == "business"
    assert provenance_context["notes"]
    serialized_source_metadata = json.dumps(source_metadata, sort_keys=True).lower()
    for forbidden_marker in ("fixture", "seed", "demo", "persistedtripinventoryfixtureadapter"):
        assert forbidden_marker not in serialized_source_metadata
