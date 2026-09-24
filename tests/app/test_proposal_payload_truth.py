"""The gate for issue 1846: send TPP what its rules read, and nothing invented.

Before this, every submission was blocked whatever the trip. TPP's fare and expense rules
fail on ABSENT data, and trip-planner never sent the lowest fare, the evidence flag or the
expense lines. It sent the traveller's flight as one "itinerary" line filed as `other`, the
placeholder "workspace" as the origin city, and the policy id as the department.

These tests capture the trip plan exactly as it would go over the wire, by intercepting the
TPP client, and assert on that — not on an internal helper.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.app.tpp_intercept import TPP_SENT, seed_policy

_SENT = TPP_SENT


@pytest.fixture
def client(tpp_client: TestClient) -> TestClient:
    return tpp_client


def _business_trip(client: TestClient) -> str:
    response = client.post(
        "/api/trips",
        json={
            "title": "Chicago client review",
            "summary": "Quarterly review with the client team.",
            "mode": "business",
            "trip_frame": {
                "origin": "Seattle",
                "start_date": "2026-10-05",
                "end_date": "2026-10-07",
                "duration_days": 3,
                "primary_regions": ["Chicago"],
            },
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["trip"]["trip_id"])


_seed_policy = seed_policy


def _submit(client: TestClient, trip_id: str) -> Any:
    workspace = client.get(f"/api/workspace/{trip_id}").json()
    scenario_id = workspace["runtime_scenario_comparison"]["scenarios"][0]["scenario_id"]
    return client.post(
        f"/api/workspace/{trip_id}/proposal/submit", json={"scenario_id": scenario_id}
    )


def test_the_trip_plan_carries_what_tpp_rules_read(client: TestClient) -> None:
    trip_id = _business_trip(client)
    _seed_policy(client, trip_id)
    client.put(
        f"/api/workspace/{trip_id}/prices",
        json={
            "component": "transport",
            "amount": 486.0,
            "note": "United.com economy",
            "lowest_amount": 470.0,
            "evidence_attested": True,
            "cabin_class": "economy",
            "flight_hours": 4.5,
        },
    )
    client.put(
        f"/api/workspace/{trip_id}/prices",
        json={"component": "lodging", "amount": 612.0, "note": "Hyatt corporate rate"},
    )

    response = _submit(client, trip_id)
    assert response.status_code == 200, response.text
    assert _SENT, "no trip plan reached the TPP client"
    plan = _SENT[-1]

    assert plan["origin_city"] == "Seattle"
    assert plan["selected_fare"] == 486.0
    assert plan["flight_cost"] == 486.0
    assert plan["lowest_fare"] == 470.0
    assert plan["fare_evidence_attached"] is True
    assert plan["cabin_class"] == "economy"
    assert plan["flight_duration_hours"] == 4.5
    assert plan["transportation_mode"] == "air"
    assert plan["estimated_cost"] == pytest.approx(1098.0)
    assert {item["category"] for item in plan["expenses"]} == {"airfare", "lodging"}
    assert "department" not in plan
    assert "funding_source" not in plan


def test_an_absent_attestation_is_sent_as_absent_not_as_true(client: TestClient) -> None:
    """A rule that fails for want of evidence must keep failing until the traveller says so."""

    trip_id = _business_trip(client)
    _seed_policy(client, trip_id)
    client.put(f"/api/workspace/{trip_id}/prices", json={"component": "transport", "amount": 486.0})

    assert _submit(client, trip_id).status_code == 200
    plan = _SENT[-1]
    assert plan["fare_evidence_attached"] is False
    assert plan["lowest_fare"] is None


def test_an_unpriced_trip_is_refused_rather_than_sent_as_zero(client: TestClient) -> None:
    """The old path fell back to the budget cap or 0.0, and a $0 trip passes every spend rule."""

    trip_id = _business_trip(client)
    _seed_policy(client, trip_id)

    response = _submit(client, trip_id)
    assert response.status_code == 422, response.text
    assert "no price yet" in response.json()["detail"]
    assert _SENT == []


def test_a_missing_origin_is_sent_as_missing_not_as_a_placeholder(client: TestClient) -> None:
    """`home_airport` is a required internal field that falls back to "workspace"; that
    placeholder reached TPP as the city of departure. With no origin, send none."""

    response = client.post(
        "/api/trips",
        json={
            "title": "No origin given",
            "summary": "Client review.",
            "mode": "business",
            "trip_frame": {
                "start_date": "2026-10-05",
                "end_date": "2026-10-07",
                "duration_days": 3,
                "primary_regions": ["Chicago"],
            },
        },
    )
    assert response.status_code == 201, response.text
    trip_id = str(response.json()["trip"]["trip_id"])
    _seed_policy(client, trip_id)
    client.put(f"/api/workspace/{trip_id}/prices", json={"component": "lodging", "amount": 612.0})

    assert _submit(client, trip_id).status_code == 200
    plan = _SENT[-1]
    assert plan["origin_city"] is None
    assert "workspace" not in {str(value) for value in plan.values()}


def test_a_trip_the_planner_could_not_map_can_still_go_to_the_policy_check(
    client: TestClient,
) -> None:
    """Issue 1827: with no measured route there is no scenario, but the prices are the
    traveller's and so is the approval request. Nothing about the submission needs a route."""

    response = client.post(
        "/api/trips",
        json={
            "title": "Site visit",
            "summary": "Supplier audit.",
            "mode": "business",
            "trip_frame": {
                "origin": "Seattle",
                "start_date": "2026-10-05",
                "end_date": "2026-10-07",
                "duration_days": 3,
                "primary_regions": ["Zzqxwv Nonexistent Place"],
            },
        },
    )
    trip_id = str(response.json()["trip"]["trip_id"])
    _seed_policy(client, trip_id)
    client.put(f"/api/workspace/{trip_id}/prices", json={"component": "lodging", "amount": 400.0})
    workspace = client.get(f"/api/workspace/{trip_id}").json()
    assert workspace["runtime_scenario_comparison"]["scenarios"] == []

    submitted = client.post(f"/api/workspace/{trip_id}/proposal/submit", json={})

    assert submitted.status_code == 200, submitted.text
    assert len(_SENT) == 1
