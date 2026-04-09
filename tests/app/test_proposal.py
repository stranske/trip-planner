import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.persistence.db import reset_database_state


def _fixture_path(*parts: str) -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / "integrations" / "tpp" / Path(*parts)


def _load_fixture(*parts: str) -> dict:
    return json.loads(_fixture_path(*parts).read_text(encoding="utf-8"))


def _proposal_payload(trip_id: str) -> dict:
    return {
        "proposal_id": f"proposal:{trip_id}",
        "trip_id": trip_id,
        "mode": "business",
        "traveler_context": {
            "employee_type": "employee",
            "traveler_experience": "frequent",
            "home_airport": "ORD",
            "loyalty_programs": ["United"],
            "mobility_or_access_needs": [],
        },
        "selected_options": [
            {
                "category": "airfare",
                "option_id": "flight-1",
                "label": "United 123",
                "vendor": "United",
                "booking_channel": "Navan",
                "estimated_cost": {
                    "currency": "USD",
                    "typical_amount": 620.0,
                    "min_amount": 620.0,
                    "max_amount": 620.0,
                },
                "justification_refs": ["fare-policy"],
            }
        ],
        "cost_summary": {
            "currency": "USD",
            "total_estimated_cost": 620.0,
            "category_estimates": {"airfare": 620.0},
            "notes": ["Costs include taxes."],
        },
        "comparables": [
            {
                "category": "airfare",
                "label": "Flexible fare",
                "vendor": "United",
                "booking_channel": "Concur",
                "estimated_cost": {
                    "currency": "USD",
                    "typical_amount": 710.0,
                    "min_amount": 710.0,
                    "max_amount": 710.0,
                },
                "notes": ["Refundable alternative."],
            }
        ],
        "approval_notes": ["Manager review required before booking."],
        "constraint_set_id": "policy-standard-2026-02",
    }


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'proposal.db'}")
    reset_database_state()
    app = create_app()

    with TestClient(app) as test_client:
        test_client.post(
            "/api/auth/signup",
            json={
                "email": "proposal@example.com",
                "password": "password123",
                "display_name": "Proposal Owner",
            },
        )
        yield test_client

    reset_database_state()


def test_workspace_proposal_submission_and_evaluation_persist(client: TestClient) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Proposal-backed workspace",
            "summary": "Persist proposal submission state for the workspace.",
            "mode": "business",
            "trip_frame": {
                "start_date": "2026-05-04",
                "end_date": "2026-05-06",
                "duration_days": 3,
                "primary_regions": ["Chicago"],
            },
        },
    )
    trip_id = created.json()["trip"]["trip_id"]

    submission_fixture = _load_fixture("proposal_submit_deferred.json")
    submission_fixture["request"]["trip_id"] = trip_id
    submission_fixture["request"]["proposal_id"] = f"proposal:{trip_id}"
    submission_fixture["request"]["payload"]["proposal_ref"] = f"proposal:{trip_id}"

    submitted = client.put(
        f"/api/workspace/{trip_id}/proposal",
        json={
            "proposal": _proposal_payload(trip_id),
            "request": submission_fixture["request"],
            "response": submission_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )
    assert submitted.status_code == 200
    submitted_payload = submitted.json()
    assert submitted_payload["proposal_state"]["summary"]["submission_status"] == "deferred"
    assert submitted_payload["proposal_state"]["summary"]["comparable_count"] == 1

    evaluation_fixture = _load_fixture("results", "approved_evaluation.json")
    evaluation_fixture["request"]["trip_id"] = trip_id
    evaluation_fixture["request"]["proposal_id"] = f"proposal:{trip_id}"
    evaluation_fixture["response"]["result_payload"]["trip_id"] = trip_id
    evaluation_fixture["response"]["result_payload"]["proposal_id"] = f"proposal:{trip_id}"
    evaluation_fixture["response"]["result_payload"]["evaluation_result"]["proposal_id"] = (
        f"proposal:{trip_id}"
    )

    evaluated = client.put(
        f"/api/workspace/{trip_id}/proposal/evaluation",
        json={
            "request": evaluation_fixture["request"],
            "response": evaluation_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )
    assert evaluated.status_code == 200
    evaluated_payload = evaluated.json()
    assert (
        evaluated_payload["proposal_state"]["evaluation"]["evaluation_result"]["status"]
        == "compliant"
    )
    assert evaluated_payload["proposal_state"]["summary"]["approval_ready"] is True

    reloaded = client.get(f"/api/workspace/{trip_id}/proposal")
    assert reloaded.status_code == 200
    reloaded_payload = reloaded.json()
    assert reloaded_payload["proposal_state"]["proposal"]["proposal_id"] == f"proposal:{trip_id}"
    assert (
        reloaded_payload["proposal_state"]["evaluation"]["evaluation_result"]["evaluation_id"]
        == "eval-approved-001"
    )


def test_workspace_proposal_submission_rejects_leisure_trip(client: TestClient) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Leisure trip",
            "summary": "Should not accept proposal submissions.",
            "mode": "leisure",
            "trip_frame": {"duration_days": 2, "primary_regions": ["Kyoto"]},
        },
    )
    trip_id = created.json()["trip"]["trip_id"]
    submission_fixture = _load_fixture("proposal_submit_deferred.json")
    submission_fixture["request"]["trip_id"] = trip_id
    submission_fixture["request"]["proposal_id"] = f"proposal:{trip_id}"
    submission_fixture["request"]["payload"]["proposal_ref"] = f"proposal:{trip_id}"

    response = client.put(
        f"/api/workspace/{trip_id}/proposal",
        json={
            "proposal": _proposal_payload(trip_id),
            "request": submission_fixture["request"],
            "response": submission_fixture["response"],
            "proposal_version": "proposal-v1",
        },
    )

    assert response.status_code == 400
    assert "business trips" in response.json()["detail"]
