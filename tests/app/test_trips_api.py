"""A trip can be corrected after it is created, and a mis-shaped request is refused (issue 1841).

Every assertion reads the served API. Before this there was no way to edit a trip (setup
promised "You can change any of this later"), and POST /api/trips answered 201 for dates
and destinations sent beside `trip_frame`, silently dropping them.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.app.tpp_intercept import seed_policy

_FRAME = {
    "origin": "Seattle",
    "start_date": "2026-10-05",
    "end_date": "2026-10-07",
    "duration_days": 3,
    "primary_regions": ["Chicago, IL"],
}


@pytest.fixture
def client(tpp_client: TestClient) -> TestClient:
    # tpp_client (tests/app/conftest.py) intercepts TPP, so a real submission and saved
    # verdict record exist without a live policy service.
    return tpp_client


def _create(client: TestClient, **overrides: Any) -> str:
    body: dict[str, Any] = {
        "title": "Client review",
        "summary": "Quarterly review.",
        "mode": "business",
    }
    body.update(overrides)
    body.setdefault("trip_frame", _FRAME)
    response = client.post("/api/trips", json=body)
    assert response.status_code == 201, response.text
    return str(response.json()["trip"]["trip_id"])


def _lead(client: TestClient, trip_id: str) -> dict[str, Any]:
    (row,) = client.get(f"/api/workspace/{trip_id}").json()["runtime_scenario_comparison"][
        "scenarios"
    ]
    return dict(row)


def test_fields_sent_outside_trip_frame_are_refused_by_name(client: TestClient) -> None:
    response = client.post(
        "/api/trips",
        json={
            "title": "x",
            "summary": "x",
            "mode": "business",
            "start_date": "2026-10-05",
            "primary_regions": ["Chicago"],
        },
    )

    assert response.status_code == 422
    named = {tuple(item["loc"])[-1] for item in response.json()["detail"]}
    assert {"start_date", "primary_regions"} <= named


def test_an_unknown_trip_frame_field_is_refused(client: TestClient) -> None:
    response = client.post(
        "/api/trips",
        json={"title": "x", "mode": "business", "trip_frame": {"destination": "Chicago"}},
    )
    assert response.status_code == 422
    assert "destination" in response.text


def test_editing_the_destination_moves_the_measured_route(client: TestClient) -> None:
    trip_id = _create(client)
    before = _lead(client, trip_id)

    edited = client.patch(
        f"/api/trips/{trip_id}", json={"trip_frame": {"primary_regions": ["Denver, CO"]}}
    )

    assert edited.status_code == 200, edited.text
    frame = edited.json()["trip"]["trip_frame"]
    assert frame["primary_regions"] == ["Denver, CO"]
    # Untouched fields keep their values.
    assert frame["origin"] == "Seattle" and frame["start_date"] == "2026-10-05"
    after = _lead(client, trip_id)
    assert after["metrics"]["travel_minutes"] != before["metrics"]["travel_minutes"]
    assert any("denver" in stop for stop in after["route_sequence"])


def test_a_changed_trip_loses_the_verdict_reached_before_the_change(client: TestClient) -> None:
    trip_id = _create(client)
    seed_policy(client, trip_id)
    client.put(f"/api/workspace/{trip_id}/prices", json={"component": "lodging", "amount": 400.0})
    submitted = client.post(f"/api/workspace/{trip_id}/proposal/submit", json={})
    assert submitted.status_code == 200, submitted.text
    assert client.get(f"/api/workspace/{trip_id}").json()["proposal_state"] is not None

    # A title is not sent to the policy service: the submission stands.
    renamed = client.patch(f"/api/trips/{trip_id}", json={"title": "Chicago client review"})
    assert renamed.json()["verdict_cleared"] is False
    assert client.get(f"/api/workspace/{trip_id}").json()["proposal_state"] is not None

    # New dates are a different request: the old verdict no longer describes the trip.
    redated = client.patch(
        f"/api/trips/{trip_id}",
        json={"trip_frame": {"start_date": "2026-11-02", "end_date": "2026-11-04"}},
    )
    assert redated.json()["verdict_cleared"] is True
    assert client.get(f"/api/workspace/{trip_id}").json()["proposal_state"] is None


def test_a_blank_title_and_an_unknown_field_are_refused_on_edit(client: TestClient) -> None:
    trip_id = _create(client)
    assert client.patch(f"/api/trips/{trip_id}", json={"title": "   "}).status_code == 400
    assert client.patch(f"/api/trips/{trip_id}", json={"mode": "leisure"}).status_code == 422


def test_deleting_a_trip_removes_its_prices(client: TestClient) -> None:
    trip_id = _create(client)
    client.put(f"/api/workspace/{trip_id}/prices", json={"component": "lodging", "amount": 400.0})

    assert client.delete(f"/api/trips/{trip_id}").status_code == 200

    from trip_planner.persistence.db import get_session_factory
    from trip_planner.persistence.models.trip_price import PersistedTripPrice

    with get_session_factory()() as session:
        assert session.query(PersistedTripPrice).filter_by(trip_id=trip_id).count() == 0
