from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.persistence.db import reset_database_state


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv(
        "TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'trips.db'}"
    )
    reset_database_state()
    app = create_app()

    with TestClient(app) as test_client:
        yield test_client

    reset_database_state()


def signup(
    client: TestClient,
    *,
    email: str,
    display_name: str,
    password: str = "password123",
) -> None:
    response = client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": password,
            "display_name": display_name,
        },
    )
    assert response.status_code == 201


def test_trip_create_list_and_detail_flow(client: TestClient) -> None:
    signup(client, email="owner@example.com", display_name="Owner")

    create = client.post(
        "/api/trips",
        json={
            "title": "Kyoto Spring",
            "summary": "Food and gardens",
            "mode": "leisure",
            "trip_frame": {
                "start_date": "2026-04-20",
                "end_date": "2026-04-26",
                "duration_days": 7,
                "primary_regions": ["Kyoto", "Osaka"],
                "traveler_party": {
                    "kind": "solo",
                    "traveler_count": 1,
                    "notes": "Window seat preferred",
                },
            },
        },
    )

    assert create.status_code == 201
    trip = create.json()["trip"]
    assert trip["title"] == "Kyoto Spring"
    assert trip["profile_refs"]["leisure_profile_id"].startswith("profile:")

    listing = client.get("/api/trips")
    assert listing.status_code == 200
    assert listing.json()["trips"] == [trip]

    detail = client.get(f"/api/trips/{trip['trip_id']}")
    assert detail.status_code == 200
    assert detail.json()["trip"]["trip_id"] == trip["trip_id"]
    assert detail.json()["trip"]["trip_frame"]["traveler_party"]["notes"] == "Window seat preferred"


def test_trip_routes_require_authentication(client: TestClient) -> None:
    assert client.get("/api/trips").status_code == 401
    assert client.post(
        "/api/trips",
        json={
            "title": "Kyoto Spring",
            "summary": "",
            "mode": "leisure",
            "trip_frame": {},
        },
    ).status_code == 401


def test_trip_detail_hides_other_users_records(client: TestClient) -> None:
    signup(client, email="owner@example.com", display_name="Owner")
    create = client.post(
        "/api/trips",
        json={
            "title": "Kyoto Spring",
            "summary": "Food and gardens",
            "mode": "leisure",
            "trip_frame": {"duration_days": 7},
        },
    )
    trip_id = create.json()["trip"]["trip_id"]

    client.post("/api/auth/logout")
    signup(client, email="other@example.com", display_name="Other")

    detail = client.get(f"/api/trips/{trip_id}")
    assert detail.status_code == 404


def test_trip_create_rejects_invalid_mode(client: TestClient) -> None:
    signup(client, email="owner@example.com", display_name="Owner")

    response = client.post(
        "/api/trips",
        json={
            "title": "Kyoto Spring",
            "summary": "",
            "mode": "unsupported",
            "trip_frame": {"duration_days": 7},
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Trip mode must be either 'leisure' or 'business'."


def test_trip_create_truncates_generated_trip_id_to_model_limit(client: TestClient) -> None:
    signup(client, email="owner@example.com", display_name="Owner")

    response = client.post(
        "/api/trips",
        json={
            "title": "a" * 160,
            "summary": "",
            "mode": "leisure",
            "trip_frame": {"duration_days": 7},
        },
    )

    assert response.status_code == 201
    assert len(response.json()["trip"]["trip_id"]) <= 96


def test_trip_create_rejects_invalid_traveler_party_kind(client: TestClient) -> None:
    signup(client, email="owner@example.com", display_name="Owner")

    response = client.post(
        "/api/trips",
        json={
            "title": "Kyoto Spring",
            "summary": "",
            "mode": "leisure",
            "trip_frame": {
                "traveler_party": {
                    "kind": "unsupported",
                    "traveler_count": 2,
                    "notes": "",
                }
            },
        },
    )

    assert response.status_code == 422


def test_trip_scenario_history_create_list_and_reload_flow(client: TestClient) -> None:
    signup(client, email="owner@example.com", display_name="Owner")
    create_trip = client.post(
        "/api/trips",
        json={
            "title": "Kyoto Spring",
            "summary": "Food and gardens",
            "mode": "leisure",
            "trip_frame": {"duration_days": 7},
        },
    )
    trip_id = create_trip.json()["trip"]["trip_id"]

    create_scenario = client.post(
        f"/api/trips/{trip_id}/saved-scenarios",
        json={
            "title": "Kyoto baseline",
            "label": "baseline",
            "summary": "Persist the calm Kyoto-first route for future comparison.",
            "snapshot_refs": {
                "scenario_search_id": "scenario-search:kyoto-spring",
                "itinerary_scenario_id": f"scenario:{trip_id}:1",
                "leisure_profile_id": f"profile:{trip_id}:leisure",
            },
        },
    )
    assert create_scenario.status_code == 201
    saved_scenario = create_scenario.json()["saved_scenario"]

    create_history = client.post(
        f"/api/trips/{trip_id}/planning-history",
        json={
            "event_kind": "scenario_saved",
            "summary": "Saved the Kyoto baseline after the first ranking pass.",
            "actor": "planner",
            "saved_scenario_id": saved_scenario["saved_scenario_id"],
            "metadata": {"surface": "trip-detail"},
        },
    )
    assert create_history.status_code == 201

    listing = client.get(f"/api/trips/{trip_id}/scenario-history")
    assert listing.status_code == 200
    payload = listing.json()
    assert payload["saved_scenarios"][0]["saved_scenario_id"] == saved_scenario["saved_scenario_id"]
    assert payload["saved_scenarios"][0]["versions"][0]["title"] == "Kyoto baseline"
    assert payload["planning_history"][0]["event_kind"] == "scenario_saved"
    assert payload["planning_history"][0]["saved_scenario_id"] == saved_scenario["saved_scenario_id"]

    repeat_listing = client.get(f"/api/trips/{trip_id}/scenario-history")
    assert repeat_listing.status_code == 200
    assert repeat_listing.json() == payload


def test_trip_scenario_history_routes_hide_other_users_records(client: TestClient) -> None:
    signup(client, email="owner@example.com", display_name="Owner")
    create_trip = client.post(
        "/api/trips",
        json={
            "title": "Kyoto Spring",
            "summary": "Food and gardens",
            "mode": "leisure",
            "trip_frame": {"duration_days": 7},
        },
    )
    trip_id = create_trip.json()["trip"]["trip_id"]

    scenario = client.post(
        f"/api/trips/{trip_id}/saved-scenarios",
        json={
            "title": "Kyoto baseline",
            "label": "baseline",
            "snapshot_refs": {
                "scenario_search_id": "scenario-search:kyoto-spring",
                "itinerary_scenario_id": f"scenario:{trip_id}:1",
                "leisure_profile_id": f"profile:{trip_id}:leisure",
            },
        },
    )
    assert scenario.status_code == 201

    client.post("/api/auth/logout")
    signup(client, email="other@example.com", display_name="Other")

    assert client.get(f"/api/trips/{trip_id}/scenario-history").status_code == 404
    assert (
        client.post(
            f"/api/trips/{trip_id}/saved-scenarios",
            json={
                "title": "Other user scenario",
                "label": "baseline",
                "snapshot_refs": {
                    "scenario_search_id": "scenario-search:kyoto-spring",
                    "itinerary_scenario_id": f"scenario:{trip_id}:1",
                    "leisure_profile_id": f"profile:{trip_id}:leisure",
                },
            },
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/trips/{trip_id}/planning-history",
            json={
                "event_kind": "scenario_saved",
                "summary": "Blocked by ownership guard.",
            },
        ).status_code
        == 404
    )
