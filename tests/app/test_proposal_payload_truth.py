"""The gate for issue 1846: send TPP what its rules read, and nothing invented.

Before this, every submission was blocked whatever the trip. TPP's fare and expense rules
fail on ABSENT data, and trip-planner never sent the lowest fare, the evidence flag or the
expense lines. It sent the traveller's flight as one "itinerary" line filed as `other`, the
placeholder "workspace" as the origin city, and the policy id as the department.

These tests capture the trip plan exactly as it would go over the wire, by intercepting the
TPP client, and assert on that — not on an internal helper.
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.integrations.tpp import client as tpp_client
from trip_planner.integrations.tpp.contracts import TPPResponseEnvelope
from trip_planner.persistence.db import ensure_database_ready, reset_database_state

_SENT: list[dict[str, Any]] = []


def _blocked_response(request: Any) -> TPPResponseEnvelope:
    return TPPResponseEnvelope.from_dict(
        {
            "operation": request.operation,
            "request_id": request.request_id,
            "correlation_id": request.correlation_id.to_dict(),
            "transport_pattern": "sync",
            "execution_status": {"state": "accepted", "terminal": False, "summary": "queued"},
            "result_payload": {"execution_id": "exec-test", "queue_state": "queued"},
        }
    )


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'payload.db'}")
    monkeypatch.setenv("TPP_BASE_URL", "http://tpp.invalid")
    monkeypatch.setenv("TPP_ACCESS_TOKEN", "test-token-long-enough")
    monkeypatch.setenv("TPP_ORGANIZATION_ID", "org-acme")
    monkeypatch.setenv("TPP_OIDC_PROVIDER", "okta")

    def capture(self: Any, request: Any) -> TPPResponseEnvelope:
        if request.operation == "submit_proposal":
            _SENT.append(dict(request.payload.get("trip_plan") or {}))
        return _blocked_response(request)

    monkeypatch.setattr(tpp_client.HTTPTPPIntegrationClient, "submit_proposal", capture)

    import trip_planner.app.services.policy as policy_service

    fixture = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "fixtures/integrations/tpp/policy/standard_policy_sync.json"
        ).read_text(encoding="utf-8")
    )

    def policy_response(request: Any, _response_payload: Any, *, trip_plan_payload: Any) -> Any:
        response = fixture["response"].copy()
        response["request_id"] = request.request_id
        response["correlation_id"] = request.correlation_id.to_dict()
        return TPPResponseEnvelope.from_dict(response)

    monkeypatch.setattr(policy_service, "_resolve_policy_response", policy_response)
    _SENT.clear()
    reset_database_state()
    ensure_database_ready()
    with TestClient(create_app()) as test_client:
        test_client.post(
            "/api/auth/signup",
            json={"email": "p@example.com", "password": "password123", "display_name": "Dana Chen"},
        )
        yield test_client
    reset_database_state()


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


def _seed_policy(client: TestClient, trip_id: str) -> None:
    response = client.post(f"/api/workspace/{trip_id}/policy/sync", json={})
    assert response.status_code == 200, response.text


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
