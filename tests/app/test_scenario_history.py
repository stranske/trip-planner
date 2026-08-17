from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.persistence.db import reset_database_state
from trip_planner.state.sessions import PlanningSessionState


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'trips.db'}")
    reset_database_state()
    app = create_app()

    with TestClient(app) as test_client:
        yield test_client

    reset_database_state()


def _signup(client: TestClient) -> None:
    response = client.post(
        "/api/auth/signup",
        json={
            "email": "owner@example.com",
            "password": "password123",
            "display_name": "Owner",
        },
    )
    assert response.status_code == 201


def test_domain_type_error_is_not_leaked_in_response_detail(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = "INTERNAL_TYPE_ERROR_SIGNATURE_SHOULD_NOT_LEAK"

    def _raise_type_error(payload: dict) -> PlanningSessionState:
        del payload
        raise TypeError(sentinel)

    monkeypatch.setattr(PlanningSessionState, "from_dict", _raise_type_error)

    _signup(client)
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

    response = client.post(
        f"/api/trips/{trip_id}/planning-sessions",
        json={"status": "active"},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert sentinel not in detail
    assert "Reference ID:" in detail
    match = re.search(r"Reference ID: ([0-9a-f]{32}).", detail)
    assert match is not None
