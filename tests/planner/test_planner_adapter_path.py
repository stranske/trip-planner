"""Tests that planner orchestration fetches inventory exclusively through production adapter interfaces.

For DB-backed trips, get_workspace_payload must route through PersistedTripSourceInventoryAdapter
regardless of whether the trip ID matches a known fixture ID.  These tests verify:

- The production adapter is selected for real persisted trips.
- The fixture path is bypassed even when the trip ID is a known fixture ID.
- Source metadata and provenance context reflect the runtime adapter, not the fixture adapter.
- No fixture-specific markers appear in serialized inventory for DB-backed trips.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.app.services.auth import AuthenticatedUser, create_account
from trip_planner.app.services.workspace import get_workspace_payload
from trip_planner.persistence.db import (
    ensure_database_ready,
    get_session_factory,
    reset_database_state,
)
from trip_planner.persistence.models.trip import PersistedTrip

_FIXTURE_TRIP_IDS = ("trip-leisure-kyoto-draft", "trip-business-client-summit")
_FIXTURE_ADAPTER_MARKERS = (
    "persistedtripinventoryfixtureadapter",
    "persisted-trip-fixture-inventory",
    "fixture-normalized-inventory",
)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'planner_adapter.db'}")
    reset_database_state()
    ensure_database_ready()
    app = create_app()

    with TestClient(app) as test_client:
        test_client.post(
            "/api/auth/signup",
            json={
                "email": "planner-adapter@example.com",
                "password": "password123",
                "display_name": "Adapter Test Owner",
            },
        )
        yield test_client

    reset_database_state()


@pytest.fixture
def db_session_with_fixture_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple]:
    """Yield (session, user, trip_id) with a fixture-named trip inserted into the DB."""
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'adapter_gap.db'}")
    reset_database_state()
    ensure_database_ready()

    factory = get_session_factory()
    with factory() as session:
        user = create_account(session, email="gap@example.com", password="password123", display_name="Gap")
        trip_id = "trip-leisure-kyoto-draft"
        record = PersistedTrip(
            trip_id=trip_id,
            user_id=user.user_id,
            title="Kyoto (DB-backed)",
            summary="Fixture ID in DB should use production adapter.",
            mode="leisure",
            status="draft",
            start_date="2026-06-01",
            end_date="2026-06-06",
            duration_days=5,
            primary_regions=["Kyoto"],
            traveler_party_kind="solo",
            traveler_count=1,
            traveler_notes="",
            leisure_profile_id=f"profile:{trip_id}:leisure",
            option_set_ids=[],
        )
        session.add(record)
        session.commit()
        yield session, user, trip_id

    reset_database_state()


def test_fixture_trip_id_in_db_routes_through_production_adapter(
    db_session_with_fixture_trip: tuple,
) -> None:
    """get_workspace_payload must use the production adapter when a fixture trip ID is in the DB."""
    session, user, trip_id = db_session_with_fixture_trip

    payload = get_workspace_payload(session, user=user, trip_id=trip_id)

    assert payload is not None
    source_metadata = payload["inventory_summary"]["source_metadata"]
    assert source_metadata["adapter_name"] == "persisted-trip-source-inventory", (
        "Production adapter must be used when a fixture trip ID is present in the DB. "
        f"Got: {source_metadata['adapter_name']!r}"
    )
    assert source_metadata["origin"] == "runtime"
    assert source_metadata["source_type"] == "persisted_trip"


def test_fixture_trip_id_in_db_provenance_reflects_runtime_context(
    db_session_with_fixture_trip: tuple,
) -> None:
    """Provenance context for a DB-backed fixture trip ID must reference the runtime source."""
    session, user, trip_id = db_session_with_fixture_trip

    payload = get_workspace_payload(session, user=user, trip_id=trip_id)

    assert payload is not None
    provenance = payload["inventory_summary"]["source_metadata"]["provenance_context"]
    assert provenance["trip_id"] == trip_id
    assert provenance["source_id"] == "persisted-trip-runtime-source"
    assert provenance["query_id"] == f"inventory-query:{trip_id}"


def test_fixture_trip_id_in_db_serialized_payload_contains_no_fixture_markers(
    db_session_with_fixture_trip: tuple,
) -> None:
    """Serialized inventory for a DB-backed fixture trip must not contain fixture adapter markers."""
    session, user, trip_id = db_session_with_fixture_trip

    payload = get_workspace_payload(session, user=user, trip_id=trip_id)

    assert payload is not None
    serialized = json.dumps(payload["inventory_summary"], sort_keys=True).lower()
    for marker in _FIXTURE_ADAPTER_MARKERS:
        assert marker not in serialized, (
            f"Fixture adapter marker {marker!r} must not appear in inventory_summary for a "
            "DB-backed trip; found in serialized payload."
        )


def test_persisted_leisure_trip_workspace_uses_production_adapter(client: TestClient) -> None:
    """Workspace for a newly created leisure trip must use the production inventory adapter."""
    created = client.post(
        "/api/trips",
        json={
            "title": "Osaka weekend getaway",
            "summary": "Verify planner adapter path for a new leisure trip.",
            "mode": "leisure",
            "trip_frame": {
                "start_date": "2026-07-04",
                "end_date": "2026-07-07",
                "duration_days": 4,
                "primary_regions": ["Osaka"],
                "traveler_party": {"kind": "solo", "traveler_count": 1, "notes": ""},
            },
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]
    assert all(fixture_id not in trip_id for fixture_id in _FIXTURE_TRIP_IDS)

    workspace = client.get(f"/api/workspace/{trip_id}")
    assert workspace.status_code == 200
    payload = workspace.json()

    source_metadata = payload["inventory_summary"]["source_metadata"]
    assert source_metadata["adapter_name"] == "persisted-trip-source-inventory"
    assert source_metadata["origin"] == "runtime"
    assert source_metadata["source_type"] == "persisted_trip"
    provenance = source_metadata["provenance_context"]
    assert provenance["trip_id"] == trip_id
    assert provenance["source_id"] == "persisted-trip-runtime-source"
    assert provenance["query_id"] == f"inventory-query:{trip_id}"


def test_persisted_business_trip_workspace_uses_production_adapter(client: TestClient) -> None:
    """Workspace for a newly created business trip must use the production inventory adapter."""
    created = client.post(
        "/api/trips",
        json={
            "title": "Barcelona team offsite",
            "summary": "Verify planner adapter path for a new business trip.",
            "mode": "business",
            "trip_frame": {
                "start_date": "2026-09-15",
                "end_date": "2026-09-18",
                "duration_days": 4,
                "primary_regions": ["Barcelona"],
                "traveler_party": {"kind": "team", "traveler_count": 5, "notes": "Strategy sprint"},
            },
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]
    assert all(fixture_id not in trip_id for fixture_id in _FIXTURE_TRIP_IDS)

    workspace = client.get(f"/api/workspace/{trip_id}")
    assert workspace.status_code == 200
    payload = workspace.json()

    source_metadata = payload["inventory_summary"]["source_metadata"]
    assert source_metadata["adapter_name"] == "persisted-trip-source-inventory"
    assert source_metadata["origin"] == "runtime"
    assert source_metadata["source_type"] == "persisted_trip"
    provenance = source_metadata["provenance_context"]
    assert provenance["trip_id"] == trip_id
    assert provenance["source_id"] == "persisted-trip-runtime-source"
    assert provenance["query_id"] == f"inventory-query:{trip_id}"


def test_persisted_trip_workspace_serialized_payload_contains_no_fixture_markers(
    client: TestClient,
) -> None:
    """Serialized workspace inventory for a DB trip must not contain fixture adapter markers."""
    created = client.post(
        "/api/trips",
        json={
            "title": "Vienna cultural tour",
            "summary": "Serialized payload must be free of fixture adapter artifacts.",
            "mode": "leisure",
            "trip_frame": {
                "start_date": "2026-10-01",
                "end_date": "2026-10-05",
                "duration_days": 5,
                "primary_regions": ["Vienna"],
            },
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]

    payload = client.get(f"/api/workspace/{trip_id}").json()
    serialized = json.dumps(payload["inventory_summary"], sort_keys=True).lower()

    for marker in _FIXTURE_ADAPTER_MARKERS:
        assert marker not in serialized, (
            f"Fixture adapter marker {marker!r} must not appear in inventory_summary; "
            "found in serialized workspace payload."
        )
    for fixture_trip_id in _FIXTURE_TRIP_IDS:
        assert fixture_trip_id not in serialized


def test_persisted_trip_workspace_inventory_contains_all_four_option_types(
    client: TestClient,
) -> None:
    """Production adapter must generate all four option types for a fully scoped persisted trip."""
    created = client.post(
        "/api/trips",
        json={
            "title": "Prague full itinerary",
            "summary": "All four option types must be present from production adapter.",
            "mode": "leisure",
            "trip_frame": {
                "start_date": "2026-11-10",
                "end_date": "2026-11-14",
                "duration_days": 5,
                "primary_regions": ["Prague"],
                "traveler_party": {"kind": "solo", "traveler_count": 1, "notes": ""},
            },
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]

    inventory = client.get(f"/api/inventory/{trip_id}").json()
    bundles = inventory["bundles"]
    assert bundles, "Production adapter must generate at least one bundle"

    bundle = bundles[0]
    assert bundle.get("lodging_options"), "Production adapter must generate lodging options"
    assert bundle.get("transport_options"), "Production adapter must generate transport options"
    assert bundle.get("activity_options"), "Production adapter must generate activity options"
