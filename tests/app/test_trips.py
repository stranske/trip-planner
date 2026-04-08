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
