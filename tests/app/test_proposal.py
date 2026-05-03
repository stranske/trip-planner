import json
import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Literal, cast
import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.integrations.tpp import client as tpp_client_module
from trip_planner.persistence.db import get_session_factory, reset_database_state
from trip_planner.persistence.models.proposal import PersistedProposalState


def _fixture_path(*parts: str) -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / "integrations" / "tpp" / Path(*parts)


def _load_fixture(*parts: str) -> dict:
    return json.loads(_fixture_path(*parts).read_text(encoding="utf-8"))


class _FakeHTTPResponse:
    def __init__(self, status_code: int, payload: dict[str, object]) -> None:
        self.status = status_code
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> Literal[False]:
        del exc_type, exc, tb
        return False


def _install_fake_http(
    monkeypatch: pytest.MonkeyPatch,
    responses: list[_FakeHTTPResponse | Exception],
    *,
    captured_requests: list[dict[str, object]] | None = None,
) -> None:
    queue = list(responses)

    def _fake_urlopen(request, timeout=0):
        if captured_requests is not None:
            captured_requests.append(
                {
                    "full_url": request.full_url,
                    "method": request.get_method(),
                    "body": json.loads((request.data or b"{}").decode("utf-8")),
                }
            )
        del timeout
        response = queue.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(tpp_client_module.urllib_request, "urlopen", _fake_urlopen)


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
    evaluation_fixture["response"]["result_payload"]["evaluation_result"][
        "proposal_id"
    ] = f"proposal:{trip_id}"

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
    assert evaluated_payload["proposal_state"]["follow_up"]["status"] == "resolved"

    reloaded = client.get(f"/api/workspace/{trip_id}/proposal")
    assert reloaded.status_code == 200
    reloaded_payload = reloaded.json()
    assert reloaded_payload["proposal_state"]["proposal"]["proposal_id"] == f"proposal:{trip_id}"
    assert (
        reloaded_payload["proposal_state"]["evaluation"]["evaluation_result"]["evaluation_id"]
        == "eval-approved-001"
    )


def test_workspace_proposal_evaluation_derives_reoptimization_follow_up(client: TestClient) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Reoptimization workspace",
            "summary": "Persist follow-up state for non-compliant policy results.",
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
    client.put(
        f"/api/workspace/{trip_id}/proposal",
        json={
            "proposal": _proposal_payload(trip_id),
            "request": submission_fixture["request"],
            "response": submission_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )

    evaluation_fixture = _load_fixture("results", "non_compliant_evaluation.json")
    evaluation_fixture["request"]["trip_id"] = trip_id
    evaluation_fixture["request"]["proposal_id"] = f"proposal:{trip_id}"
    evaluation_fixture["response"]["result_payload"]["trip_id"] = trip_id
    evaluation_fixture["response"]["result_payload"]["proposal_id"] = f"proposal:{trip_id}"
    evaluation_fixture["response"]["result_payload"]["evaluation_result"][
        "proposal_id"
    ] = f"proposal:{trip_id}"

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
    follow_up = evaluated.json()["proposal_state"]["follow_up"]
    assert follow_up["status"] == "reoptimization_required"
    assert follow_up["recommended_action"] == "reoptimize"
    assert follow_up["alternatives"][0]["category"] == "lodging"
    assert follow_up["selected_alternative"]["summary"] == "Use a compliant downtown property"


def test_workspace_proposal_evaluation_derives_exception_follow_up(client: TestClient) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Exception follow-up workspace",
            "summary": "Persist deterministic exception guidance from live policy results.",
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
    client.put(
        f"/api/workspace/{trip_id}/proposal",
        json={
            "proposal": _proposal_payload(trip_id),
            "request": submission_fixture["request"],
            "response": submission_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )

    evaluation_fixture = _load_fixture("results", "approved_evaluation.json")
    evaluation_fixture["request"]["trip_id"] = trip_id
    evaluation_fixture["request"]["proposal_id"] = f"proposal:{trip_id}"
    evaluation_fixture["response"]["result_payload"]["trip_id"] = trip_id
    evaluation_fixture["response"]["result_payload"]["proposal_id"] = f"proposal:{trip_id}"
    evaluation_fixture["response"]["result_payload"]["evaluation_result"][
        "proposal_id"
    ] = f"proposal:{trip_id}"
    evaluation_fixture["response"]["result_payload"]["evaluation_result"][
        "status"
    ] = "exception_required"
    evaluation_fixture["response"]["result_payload"]["evaluation_result"][
        "approval_requirements"
    ] = [
        {
            "role": "manager",
            "reason": "Operational exception requires manager approval",
            "mandatory": True,
        },
        {
            "role": "finance",
            "reason": "Lodging cap exception requires finance review",
            "mandatory": True,
        },
    ]
    evaluation_fixture["response"]["result_payload"]["evaluation_result"]["failure_reasons"] = [
        {
            "code": "lodging_cap_exception",
            "message": "Selected lodging exceeds the nightly cap.",
            "severity": "warning",
            "related_category": "lodging",
        }
    ]
    evaluation_fixture["response"]["result_payload"]["evaluation_result"][
        "preferred_alternatives"
    ] = [
        {
            "category": "lodging",
            "summary": "Use the lower-cost comparable if the exception is denied.",
            "rationale": "Preserves site access with a lower nightly cost ceiling.",
            "comparable_ref": "lodging-alt-2",
        }
    ]
    evaluation_fixture["response"]["result_payload"]["evaluation_result"]["exception_guidance"] = [
        "Retain the lower-cost comparable in the approval packet.",
        "Document the operational-safety rationale in the manager approval request.",
    ]
    evaluation_fixture["response"]["result_payload"]["evaluation_result"]["notes"] = [
        "Proposal is exception-eligible if the fatigue-management rationale is approved."
    ]
    evaluation_fixture["response"]["result_payload"]["evaluation_result"]["compliance_score"] = 0.68

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
    payload = evaluated.json()["proposal_state"]
    follow_up = payload["follow_up"]
    assert follow_up["status"] == "exception_required"
    assert follow_up["path"] == "exception"
    assert follow_up["recommended_action"] == "request_exception"
    assert follow_up["approval_requirements"][0]["role"] == "manager"
    assert follow_up["alternatives"][0]["category"] == "lodging"
    assert follow_up["guidance"] == [
        "Retain the lower-cost comparable in the approval packet.",
        "Document the operational-safety rationale in the manager approval request.",
    ]
    assert payload["summary"]["evaluation_result_status"] == "exception_required"
    assert payload["summary"]["approval_ready"] is False
    assert payload["summary"]["follow_up_status"] == "exception_required"


def test_workspace_proposal_submission_clears_stale_evaluation_state(client: TestClient) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Proposal resubmission workspace",
            "summary": "New proposal submissions should reset evaluation state.",
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

    first_submission = client.put(
        f"/api/workspace/{trip_id}/proposal",
        json={
            "proposal": _proposal_payload(trip_id),
            "request": submission_fixture["request"],
            "response": submission_fixture["response"],
            "proposal_version": "proposal-v1",
            "scenario_id": "scenario-a",
        },
    )
    assert first_submission.status_code == 200

    evaluation_fixture = _load_fixture("results", "approved_evaluation.json")
    evaluation_fixture["request"]["trip_id"] = trip_id
    evaluation_fixture["request"]["proposal_id"] = f"proposal:{trip_id}"
    evaluation_fixture["response"]["result_payload"]["trip_id"] = trip_id
    evaluation_fixture["response"]["result_payload"]["proposal_id"] = f"proposal:{trip_id}"
    evaluation_fixture["response"]["result_payload"]["proposal_version"] = "proposal-v1"
    evaluation_fixture["response"]["result_payload"]["evaluation_result"][
        "proposal_id"
    ] = f"proposal:{trip_id}"

    evaluated = client.put(
        f"/api/workspace/{trip_id}/proposal/evaluation",
        json={
            "request": evaluation_fixture["request"],
            "response": evaluation_fixture["response"],
            "proposal_version": "proposal-v1",
            "scenario_id": "scenario-a",
        },
    )
    assert evaluated.status_code == 200
    assert evaluated.json()["proposal_state"]["summary"]["approval_ready"] is True

    resubmitted = client.put(
        f"/api/workspace/{trip_id}/proposal",
        json={
            "proposal": _proposal_payload(trip_id),
            "request": submission_fixture["request"],
            "response": submission_fixture["response"],
            "proposal_version": "proposal-v2",
            "scenario_id": "scenario-b",
        },
    )
    assert resubmitted.status_code == 200
    proposal_state = resubmitted.json()["proposal_state"]
    assert proposal_state["proposal_version"] == "proposal-v2"
    assert proposal_state["evaluation"] == {}
    assert proposal_state["evaluation_status"] is None
    assert proposal_state["summary"]["approval_ready"] is False
    assert proposal_state["summary"]["evaluation_result_status"] is None


def test_workspace_proposal_evaluation_rejects_mismatched_submission_linkage(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Proposal evaluation linkage",
            "summary": "Evaluation linkage must match the stored submission.",
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

    evaluation_fixture = _load_fixture("results", "approved_evaluation.json")
    evaluation_fixture["request"]["trip_id"] = trip_id
    evaluation_fixture["request"]["proposal_id"] = f"proposal:{trip_id}"
    evaluation_fixture["response"]["result_payload"]["trip_id"] = trip_id
    evaluation_fixture["response"]["result_payload"]["proposal_id"] = "proposal:other-trip"
    evaluation_fixture["response"]["result_payload"]["proposal_version"] = "proposal-v3"
    evaluation_fixture["response"]["result_payload"]["evaluation_result"][
        "proposal_id"
    ] = "proposal:other-trip"

    evaluated = client.put(
        f"/api/workspace/{trip_id}/proposal/evaluation",
        json={
            "request": evaluation_fixture["request"],
            "response": evaluation_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )
    assert evaluated.status_code == 400
    assert "persisted proposal" in evaluated.json()["detail"]


def test_workspace_proposal_evaluation_normalizes_stale_request_linkage(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Proposal evaluation request normalization",
            "summary": "Stale request linkage should be repaired from the stored submission.",
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

    evaluation_fixture = _load_fixture("results", "approved_evaluation.json")
    evaluation_fixture["request"]["trip_id"] = "trip-stale"
    evaluation_fixture["request"]["proposal_id"] = "proposal:stale"
    evaluation_fixture["request"]["organization_id"] = "org-stale"
    evaluation_fixture["request"]["payload"]["proposal_version"] = "proposal-v1"
    evaluation_fixture["response"]["result_payload"]["trip_id"] = trip_id
    evaluation_fixture["response"]["result_payload"]["proposal_id"] = f"proposal:{trip_id}"
    evaluation_fixture["response"]["result_payload"]["proposal_version"] = "proposal-v3"
    evaluation_fixture["response"]["result_payload"]["evaluation_result"][
        "proposal_id"
    ] = f"proposal:{trip_id}"

    evaluated = client.put(
        f"/api/workspace/{trip_id}/proposal/evaluation",
        json={
            "request": evaluation_fixture["request"],
            "response": evaluation_fixture["response"],
            "proposal_version": "proposal-v1",
            "scenario_id": "scenario-a",
        },
    )
    assert evaluated.status_code == 200
    evaluation = evaluated.json()["proposal_state"]["evaluation"]
    assert evaluation["request_payload"] == {
        "execution_id": "exec-001",
        "proposal_version": "proposal-v3",
    }
    assert evaluation["linkage"]["trip_id"] == trip_id
    assert evaluation["linkage"]["proposal_id"] == f"proposal:{trip_id}"
    assert (
        evaluation["linkage"]["organization_id"] == submission_fixture["request"]["organization_id"]
    )


def test_workspace_proposal_evaluation_rejects_mismatched_scenario_and_organization(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Proposal evaluation linkage",
            "summary": "Evaluation scenario and organization must match the stored submission.",
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

    scenario_fixture = _load_fixture("results", "approved_evaluation.json")
    scenario_fixture["request"]["trip_id"] = trip_id
    scenario_fixture["request"]["proposal_id"] = f"proposal:{trip_id}"
    scenario_fixture["response"]["result_payload"]["trip_id"] = trip_id
    scenario_fixture["response"]["result_payload"]["proposal_id"] = f"proposal:{trip_id}"
    scenario_fixture["response"]["result_payload"]["proposal_version"] = "proposal-v3"
    scenario_fixture["response"]["result_payload"]["scenario_id"] = "scenario-b"
    scenario_fixture["response"]["result_payload"]["evaluation_result"][
        "proposal_id"
    ] = f"proposal:{trip_id}"

    scenario_response = client.put(
        f"/api/workspace/{trip_id}/proposal/evaluation",
        json={
            "request": scenario_fixture["request"],
            "response": scenario_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )
    assert scenario_response.status_code == 400
    assert "scenario_id" in scenario_response.json()["detail"]

    organization_fixture = _load_fixture("results", "approved_evaluation.json")
    organization_fixture["request"]["trip_id"] = trip_id
    organization_fixture["request"]["proposal_id"] = f"proposal:{trip_id}"
    organization_fixture["request"]["organization_id"] = "org-other"
    organization_fixture["response"]["result_payload"]["trip_id"] = trip_id
    organization_fixture["response"]["result_payload"]["proposal_id"] = f"proposal:{trip_id}"
    organization_fixture["response"]["result_payload"]["proposal_version"] = "proposal-v3"
    organization_fixture["response"]["result_payload"]["evaluation_result"][
        "proposal_id"
    ] = f"proposal:{trip_id}"

    organization_response = client.put(
        f"/api/workspace/{trip_id}/proposal/evaluation",
        json={
            "request": organization_fixture["request"],
            "response": organization_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )
    assert organization_response.status_code == 200
    assert organization_response.json()["proposal_state"]["evaluation"]["request_payload"] == {
        "execution_id": "exec-001",
        "proposal_version": "proposal-v3",
    }
    assert organization_response.json()["proposal_state"]["evaluation"]["linkage"][
        "organization_id"
    ] == (submission_fixture["request"]["organization_id"])


def test_workspace_proposal_follow_up_patch_persists_exception_request(client: TestClient) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Exception follow-up workspace",
            "summary": "Persist exception request follow-up after policy review.",
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
    client.put(
        f"/api/workspace/{trip_id}/proposal",
        json={
            "proposal": _proposal_payload(trip_id),
            "request": submission_fixture["request"],
            "response": submission_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )

    updated = client.patch(
        f"/api/workspace/{trip_id}/proposal/follow-up",
        json={
            "status": "exception_requested",
            "title": "Exception packet drafted",
            "summary": "Preserve the faster arrival path and route the packet for manager review.",
            "notes": ["Traveler needs the earlier arrival buffer for the client meeting."],
            "requested_exception": {
                "exception_type": "schedule_protection",
                "reason": "Preserve the faster arrival path and route the packet for manager review.",
                "requested_approval_roles": ["manager"],
                "notes": ["Attach the compliant comparable for review."],
            },
        },
    )

    assert updated.status_code == 200
    payload = updated.json()["proposal_state"]
    assert payload["follow_up"]["status"] == "exception_requested"
    assert payload["follow_up"]["requested_exception"]["exception_type"] == "schedule_protection"
    assert payload["proposal"]["requested_exception"]["requested_approval_roles"] == ["manager"]


def test_workspace_proposal_follow_up_patch_accepts_awaiting_evaluation_status(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Pending evaluation workspace",
            "summary": "Allow explicit pending follow-up updates before the policy result arrives.",
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
    client.put(
        f"/api/workspace/{trip_id}/proposal",
        json={
            "proposal": _proposal_payload(trip_id),
            "request": submission_fixture["request"],
            "response": submission_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )

    updated = client.patch(
        f"/api/workspace/{trip_id}/proposal/follow-up",
        json={
            "status": "awaiting_evaluation",
            "title": "Awaiting policy verdict",
            "summary": "Carrier response is stored while the workspace waits for policy evaluation.",
            "notes": ["Keep the current proposal visible until the evaluator posts a result."],
        },
    )

    assert updated.status_code == 200
    payload = updated.json()["proposal_state"]
    assert payload["follow_up"]["status"] == "awaiting_evaluation"
    assert payload["follow_up"]["path"] == "pending"


def test_workspace_proposal_follow_up_patch_rejects_malformed_exception_payload(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Malformed exception workspace",
            "summary": "Reject invalid exception payload containers.",
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
    client.put(
        f"/api/workspace/{trip_id}/proposal",
        json={
            "proposal": _proposal_payload(trip_id),
            "request": submission_fixture["request"],
            "response": submission_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )

    updated = client.patch(
        f"/api/workspace/{trip_id}/proposal/follow-up",
        json={
            "status": "exception_requested",
            "title": "Exception packet drafted",
            "summary": "Preserve the faster arrival path and route the packet for manager review.",
            "requested_exception": {
                "exception_type": "schedule_protection",
                "reason": "Preserve the faster arrival path and route the packet for manager review.",
                "requested_approval_roles": "manager",
                "notes": ["Attach the compliant comparable for review."],
            },
        },
    )

    assert updated.status_code == 422


def test_workspace_proposal_follow_up_patch_preserves_existing_path_for_resolved_status(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Resolved reoptimization workspace",
            "summary": "Resolve the active reoptimization lane without losing the path.",
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
    client.put(
        f"/api/workspace/{trip_id}/proposal",
        json={
            "proposal": _proposal_payload(trip_id),
            "request": submission_fixture["request"],
            "response": submission_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )

    evaluation_fixture = _load_fixture("results", "non_compliant_evaluation.json")
    evaluation_fixture["request"]["trip_id"] = trip_id
    evaluation_fixture["request"]["proposal_id"] = f"proposal:{trip_id}"
    evaluation_fixture["response"]["result_payload"]["trip_id"] = trip_id
    evaluation_fixture["response"]["result_payload"]["proposal_id"] = f"proposal:{trip_id}"
    evaluation_fixture["response"]["result_payload"]["evaluation_result"][
        "proposal_id"
    ] = f"proposal:{trip_id}"
    client.put(
        f"/api/workspace/{trip_id}/proposal/evaluation",
        json={
            "request": evaluation_fixture["request"],
            "response": evaluation_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )

    updated = client.patch(
        f"/api/workspace/{trip_id}/proposal/follow-up",
        json={
            "status": "resolved",
            "title": "Reoptimization finished",
            "summary": "The compliant alternative is now ready for the next approval handoff.",
            "selected_alternative": {
                "category": "lodging",
                "summary": "Use a compliant downtown property",
                "rationale": "Alternative meets nightly cap and booking-channel requirements.",
                "comparable_ref": "lodging-alt-2",
            },
        },
    )

    assert updated.status_code == 200
    payload = updated.json()["proposal_state"]
    assert payload["follow_up"]["status"] == "resolved"
    assert payload["follow_up"]["path"] == "reoptimization"


def test_workspace_proposal_get_derives_follow_up_when_legacy_summary_is_missing(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Legacy proposal workspace",
            "summary": "Backfill a follow-up response for older persisted records.",
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
    client.put(
        f"/api/workspace/{trip_id}/proposal",
        json={
            "proposal": _proposal_payload(trip_id),
            "request": submission_fixture["request"],
            "response": submission_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )

    evaluation_fixture = _load_fixture("results", "approved_evaluation.json")
    evaluation_fixture["request"]["trip_id"] = trip_id
    evaluation_fixture["request"]["proposal_id"] = f"proposal:{trip_id}"
    evaluation_fixture["response"]["result_payload"]["trip_id"] = trip_id
    evaluation_fixture["response"]["result_payload"]["proposal_id"] = f"proposal:{trip_id}"
    evaluation_fixture["response"]["result_payload"]["evaluation_result"][
        "proposal_id"
    ] = f"proposal:{trip_id}"
    client.put(
        f"/api/workspace/{trip_id}/proposal/evaluation",
        json={
            "request": evaluation_fixture["request"],
            "response": evaluation_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )

    session = get_session_factory()()
    try:
        record = session.query(PersistedProposalState).filter_by(trip_id=trip_id).one()
        summary = dict(record.summary)
        summary.pop("follow_up", None)
        record.summary = summary
        session.commit()
    finally:
        session.close()

    reloaded = client.get(f"/api/workspace/{trip_id}/proposal")

    assert reloaded.status_code == 200
    payload = reloaded.json()["proposal_state"]
    assert payload["follow_up"]["status"] == "resolved"
    assert payload["follow_up"]["path"] == "approval"


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


def test_workspace_proposal_submission_and_evaluation_use_live_tpp_transport(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TPP_BASE_URL", "https://tpp.example.test")
    monkeypatch.setenv("TPP_ACCESS_TOKEN", "token-123")
    monkeypatch.setenv("TPP_OIDC_PROVIDER", "okta")
    captured_requests: list[dict[str, object]] = []
    submission_response = _FakeHTTPResponse(
        200,
        {
            "operation": "submit_proposal",
            "submission_status": "submitted",
            "request_id": "ignored-submit",
            "correlation_id": {"value": "ignored", "issued_by": "tpp"},
            "transport_pattern": "deferred",
            "execution_status": {
                "state": "deferred",
                "terminal": False,
                "summary": "Proposal queued for evaluation",
                "poll_after_seconds": 30,
                "external_status": "202 Accepted",
                "updated_at": "2026-04-03T00:41:01Z",
            },
            "result_payload": {
                "execution_id": "exec-live-001",
                "queue_state": "waiting_for_policy_engine",
            },
            "retry": {
                "attempt": 0,
                "max_attempts": 5,
                "retryable": True,
                "backoff_seconds": 30,
                "next_retry_at": "2026-04-03T00:41:31Z",
                "reason": "Await evaluator completion",
            },
            "received_at": "2026-04-03T00:41:01Z",
            "status_endpoint": "https://tpp.example.test/api/planner/proposals/proposal-live/executions/exec-live-001",
        },
    )
    evaluation_response = _FakeHTTPResponse(
        200,
        {
            "trip_id": "trip-placeholder",
            "proposal_id": "proposal:trip-placeholder",
            "proposal_version": "proposal-v3",
            "execution_id": "exec-live-001",
            "request_id": "ignored-eval",
            "correlation_id": {"value": "ignored", "issued_by": "tpp"},
            "outcome": "compliant",
            "result_endpoint": "GET /api/planner/executions/exec-live-001/evaluation-result",
            "status_endpoint": "https://tpp.example.test/api/planner/proposals/proposal-live/executions/exec-live-001",
            "policy_result": {
                "status": "pass",
                "issues": [],
                "policy_version": "policy-v1",
            },
            "blocking_issues": [],
            "preferred_alternatives": [],
            "exception_requirements": [],
            "reoptimization_guidance": [],
            "generated_at": "2026-04-03T02:15:04Z",
        },
    )
    _install_fake_http(
        monkeypatch,
        [submission_response, evaluation_response],
        captured_requests=captured_requests,
    )

    created = client.post(
        "/api/trips",
        json={
            "title": "Live proposal transport",
            "summary": "Use runtime TPP HTTP transport.",
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
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )
    assert submitted.status_code == 200
    assert submitted.json()["proposal_state"]["execution_id"] == "exec-live-001"

    evaluation_fixture = _load_fixture("results", "approved_evaluation.json")
    evaluation_fixture["request"]["trip_id"] = "trip-stale"
    evaluation_fixture["request"]["proposal_id"] = "proposal:stale"
    evaluation_fixture["request"]["organization_id"] = "org-stale"
    evaluation_fixture["request"]["payload"]["proposal_version"] = "proposal-stale"
    evaluation_response._payload["trip_id"] = trip_id
    evaluation_response._payload["proposal_id"] = f"proposal:{trip_id}"
    evaluation_response.text = json.dumps(evaluation_response._payload)

    evaluated = client.put(
        f"/api/workspace/{trip_id}/proposal/evaluation",
        json={
            "request": evaluation_fixture["request"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )
    assert evaluated.status_code == 200
    payload = evaluated.json()["proposal_state"]
    assert payload["evaluation"]["evaluation_result"]["status"] == "compliant"
    assert payload["summary"]["approval_ready"] is True
    assert captured_requests[0] == {
        "full_url": "https://tpp.example.test/api/planner/proposals",
        "method": "POST",
        "body": {
            "trip_plan": {
                "trip_id": trip_id,
                "traveler_name": "Proposal Owner",
                "traveler_role": "employee",
                "department": "policy-standard-2026-02",
                "destination": "Chicago",
                "origin_city": "ORD",
                "destination_city": "Chicago",
                "departure_date": "2026-05-04",
                "return_date": "2026-05-06",
                "purpose": "Use runtime TPP HTTP transport.",
                "transportation_mode": "air",
                "expected_costs": {"airfare": 620.0},
                "funding_source": "policy-standard-2026-02",
                "estimated_cost": 620.0,
                "status": "submitted",
                "expense_breakdown": {"airfare": 620.0},
                "selected_fare": 620.0,
                "flight_cost": 620.0,
                "comparable_hotels": None,
                "selected_providers": {"airfare": "United"},
                "validation_results": [],
                "approval_history": [],
                "exception_requests": [],
            },
            "request": {
                "trip_id": trip_id,
                "proposal_id": f"proposal:{trip_id}",
                "proposal_version": "proposal-v3",
                "payload": {
                    "proposal_ref": f"proposal:{trip_id}",
                    "submission_mode": "queue",
                },
                "request_id": submission_fixture["request"]["request_id"],
                "correlation_id": submission_fixture["request"]["correlation_id"],
                "transport_pattern": submission_fixture["request"]["transport_pattern"],
                "organization_id": submission_fixture["request"]["organization_id"],
                "submitted_at": submission_fixture["request"]["submitted_at"],
            },
        },
    }
    assert captured_requests[1] == {
        "full_url": "https://tpp.example.test/api/planner/executions/exec-live-001/evaluation-result",
        "method": "GET",
        "body": {
            "execution_id": "exec-live-001",
            "trip_id": trip_id,
            "proposal_id": f"proposal:{trip_id}",
            "proposal_version": "proposal-v3",
            "request_id": evaluation_fixture["request"]["request_id"],
            "requested_at": evaluation_fixture["request"]["submitted_at"],
        },
    }
    assert payload["evaluation"]["request_payload"] == {
        "execution_id": "exec-live-001",
        "proposal_version": "proposal-v3",
    }
    assert payload["evaluation"]["linkage"]["trip_id"] == trip_id
    assert payload["evaluation"]["linkage"]["proposal_id"] == f"proposal:{trip_id}"
    assert (
        payload["evaluation"]["linkage"]["organization_id"]
        == submission_fixture["request"]["organization_id"]
    )


def test_workspace_proposal_live_transport_rejects_invalid_upstream_contract(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TPP_BASE_URL", "https://tpp.example.test")
    monkeypatch.setenv("TPP_ACCESS_TOKEN", "token-123")
    monkeypatch.setenv("TPP_OIDC_PROVIDER", "okta")
    _install_fake_http(
        monkeypatch,
        [_FakeHTTPResponse(200, {"submission_status": "submitted"})],
    )

    created = client.post(
        "/api/trips",
        json={
            "title": "Invalid proposal transport",
            "summary": "Surface invalid live TPP contracts.",
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

    response = client.put(
        f"/api/workspace/{trip_id}/proposal",
        json={
            "proposal": _proposal_payload(trip_id),
            "request": submission_fixture["request"],
            "proposal_version": "proposal-v3",
        },
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "result_payload.execution_id is required for non-terminal submissions"
    )


def test_workspace_proposal_submission_persists_stored_policy_when_live_tpp_times_out(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TPP_BASE_URL", "https://tpp.example.test")
    monkeypatch.setenv("TPP_ACCESS_TOKEN", "token-123")
    monkeypatch.setenv("TPP_OIDC_PROVIDER", "okta")
    monkeypatch.setenv("TPP_TRANSPORT_MAX_ATTEMPTS", "1")
    _install_fake_http(monkeypatch, [socket.timeout("slow response")])

    created = client.post(
        "/api/trips",
        json={
            "title": "Timeout fallback workspace",
            "summary": "Persist stored-policy posture when live TPP times out.",
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

    response = client.put(
        f"/api/workspace/{trip_id}/proposal",
        json={
            "proposal": _proposal_payload(trip_id),
            "request": submission_fixture["request"],
            "proposal_version": "proposal-v3",
        },
    )

    assert response.status_code == 200
    payload = response.json()["proposal_state"]
    assert payload["submission_status"] == "retry_scheduled"
    assert payload["summary"]["submission_error"]["code"] == "timeout"
    assert payload["summary"]["submission_error"]["details"]["error_code"] == "timeout"
    assert payload["summary"]["submission_error"]["details"]["status_code"] == "504"
    assert "timed out" in payload["summary"]["submission_error"]["message"]
    assert "stored-policy posture" in payload["summary"]["submission_summary"]
    assert payload["summary"]["submission_retry"]["retryable"] is True


def test_workspace_proposal_submission_persists_stored_policy_when_breaker_is_open(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TPP_BASE_URL", "https://tpp.example.test")
    monkeypatch.setenv("TPP_ACCESS_TOKEN", "token-123")
    monkeypatch.setenv("TPP_OIDC_PROVIDER", "okta")

    def _raise_breaker_open(self, request):
        del self, request
        raise tpp_client_module.TPPTransportError(
            "TPP circuit breaker is open for https://tpp.example.test:443.",
            error_code="breaker_open",
            status_code=503,
            retryable=True,
        )

    monkeypatch.setattr(
        tpp_client_module.HTTPTPPIntegrationClient,
        "submit_proposal",
        _raise_breaker_open,
    )

    created = client.post(
        "/api/trips",
        json={
            "title": "Breaker fallback workspace",
            "summary": "Persist stored-policy posture when live TPP breaker is open.",
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

    response = client.put(
        f"/api/workspace/{trip_id}/proposal",
        json={
            "proposal": _proposal_payload(trip_id),
            "request": submission_fixture["request"],
            "proposal_version": "proposal-v3",
        },
    )

    assert response.status_code == 200
    payload = response.json()["proposal_state"]
    assert payload["submission_status"] == "retry_scheduled"
    assert payload["summary"]["submission_error"]["code"] == "breaker_open"
    assert payload["summary"]["submission_error"]["details"]["error_code"] == "breaker_open"
    assert payload["summary"]["submission_error"]["details"]["status_code"] == "503"
    assert "circuit breaker is open" in payload["summary"]["submission_error"]["message"]
    assert "stored-policy posture" in payload["summary"]["submission_summary"]


def test_workspace_proposal_evaluation_persists_stored_policy_when_live_tpp_times_out(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TPP_BASE_URL", "https://tpp.example.test")
    monkeypatch.setenv("TPP_ACCESS_TOKEN", "token-123")
    monkeypatch.setenv("TPP_OIDC_PROVIDER", "okta")

    created = client.post(
        "/api/trips",
        json={
            "title": "Evaluation timeout fallback workspace",
            "summary": "Persist stored-policy posture when live evaluation fetch times out.",
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

    def _raise_timeout(self, request):
        del self, request
        raise socket.timeout("evaluation read timeout")

    monkeypatch.setattr(
        tpp_client_module.HTTPTPPIntegrationClient,
        "fetch_evaluation_result",
        _raise_timeout,
    )

    evaluation_fixture = _load_fixture("results", "approved_evaluation.json")
    evaluation_fixture["request"]["trip_id"] = trip_id
    evaluation_fixture["request"]["proposal_id"] = f"proposal:{trip_id}"

    evaluated = client.put(
        f"/api/workspace/{trip_id}/proposal/evaluation",
        json={
            "request": evaluation_fixture["request"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )

    assert evaluated.status_code == 200
    payload = evaluated.json()["proposal_state"]
    assert payload["evaluation_status"] == "retry_scheduled"
    assert payload["summary"]["evaluation_error"]["code"] == "timeout"
    assert payload["summary"]["evaluation_error"]["details"]["error_code"] == "timeout"
    assert payload["summary"]["evaluation_error"]["details"]["status_code"] == "504"
    assert "timed out" in payload["summary"]["evaluation_error"]["message"]
    assert "stored-policy posture" in payload["summary"]["follow_up_summary"]


def test_workspace_proposal_refresh_polls_live_status_and_persists_evaluation(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TPP_BASE_URL", "https://tpp.example.test")
    monkeypatch.setenv("TPP_ACCESS_TOKEN", "token-123")
    monkeypatch.setenv("TPP_OIDC_PROVIDER", "okta")
    captured_requests: list[dict[str, object]] = []
    submission_response = _FakeHTTPResponse(
        200,
        {
            "transport_pattern": "deferred",
            "execution_status": {
                "state": "deferred",
                "terminal": False,
                "summary": "Proposal queued for evaluation",
                "poll_after_seconds": 30,
                "external_status": "202 Accepted",
                "updated_at": "2026-04-03T00:41:01Z",
            },
            "result_payload": {
                "execution_id": "exec-live-002",
                "queue_state": "waiting_for_policy_engine",
            },
            "retry": {
                "attempt": 0,
                "max_attempts": 5,
                "retryable": True,
                "backoff_seconds": 30,
                "next_retry_at": "2026-04-03T00:41:31Z",
                "reason": "Await evaluator completion",
            },
            "received_at": "2026-04-03T00:41:01Z",
            "status_endpoint": "https://tpp.example.test/api/planner/proposals/proposal-live/executions/exec-live-002",
        },
    )
    poll_response = _FakeHTTPResponse(
        200,
        {
            "transport_pattern": "async",
            "execution_status": {
                "state": "succeeded",
                "terminal": True,
                "summary": "Policy evaluation completed",
                "external_status": "200 OK",
                "updated_at": "2026-04-03T00:42:11Z",
            },
            "result_payload": {
                "execution_id": "exec-live-002",
                "queue_state": "completed",
            },
            "received_at": "2026-04-03T00:42:11Z",
            "status_endpoint": "https://tpp.example.test/api/planner/proposals/proposal-live/executions/exec-live-002",
        },
    )
    evaluation_response = _FakeHTTPResponse(
        200,
        {
            "trip_id": "trip-placeholder",
            "proposal_id": "proposal:trip-placeholder",
            "proposal_version": "proposal-v3",
            "execution_id": "exec-live-002",
            "request_id": "ignored-eval",
            "correlation_id": {"value": "ignored", "issued_by": "tpp"},
            "outcome": "non_compliant",
            "result_endpoint": "GET /api/planner/executions/exec-live-002/evaluation-result",
            "status_endpoint": "https://tpp.example.test/api/planner/proposals/proposal-live/executions/exec-live-002",
            "policy_result": {
                "status": "fail",
                "issues": [],
                "policy_version": "policy-v1",
            },
            "blocking_issues": [
                {
                    "code": "lodging_cap_exceeded",
                    "summary": "Nightly lodging exceeds the allowed cap.",
                    "category": "lodging",
                }
            ],
            "preferred_alternatives": [
                {
                    "category": "lodging",
                    "summary": "Use a compliant downtown property",
                    "rationale": "Alternative meets nightly cap and booking-channel requirements.",
                    "comparable_ref": "lodging-alt-2",
                }
            ],
            "exception_requirements": [],
            "reoptimization_guidance": [
                {
                    "summary": "Keep the lower-cost lodging alternative attached to the next submission."
                }
            ],
            "generated_at": "2026-04-03T00:42:13Z",
        },
    )
    _install_fake_http(
        monkeypatch,
        [submission_response, poll_response, evaluation_response],
        captured_requests=captured_requests,
    )

    created = client.post(
        "/api/trips",
        json={
            "title": "Refresh proposal status",
            "summary": "Advance a deferred live TPP execution from the workspace.",
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
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )
    assert submitted.status_code == 200

    evaluation_response._payload["trip_id"] = trip_id
    evaluation_response._payload["proposal_id"] = f"proposal:{trip_id}"
    evaluation_response.text = json.dumps(evaluation_response._payload)

    refreshed = client.post(f"/api/workspace/{trip_id}/proposal/refresh")

    assert refreshed.status_code == 200
    payload = refreshed.json()["proposal_state"]
    assert payload["submission_status"] == "succeeded"
    assert payload["evaluation_status"] == "succeeded"
    assert payload["summary"]["submission_requires_polling"] is False
    assert payload["summary"]["evaluation_transport_status"] == "succeeded"
    assert payload["follow_up"]["status"] == "reoptimization_required"
    assert payload["follow_up"]["selected_alternative"]["summary"] == (
        "Use a compliant downtown property"
    )
    assert captured_requests[1]["full_url"] == (
        f"https://tpp.example.test/api/planner/proposals/proposal:{trip_id}/executions/exec-live-002"
    )
    assert captured_requests[1]["method"] == "GET"
    poll_request_body = cast(dict[str, object], captured_requests[1]["body"])
    assert poll_request_body["proposal_version"] == "proposal-v3"
    assert captured_requests[2]["full_url"] == (
        "https://tpp.example.test/api/planner/executions/exec-live-002/evaluation-result"
    )


def test_workspace_proposal_refresh_persists_failed_remote_status(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TPP_BASE_URL", "https://tpp.example.test")
    monkeypatch.setenv("TPP_ACCESS_TOKEN", "token-123")
    monkeypatch.setenv("TPP_OIDC_PROVIDER", "okta")
    poll_response = _FakeHTTPResponse(
        200,
        {
            "transport_pattern": "async",
            "execution_status": {
                "state": "failed",
                "terminal": True,
                "summary": "Evaluator returned an integration error",
                "external_status": "502 Bad Gateway",
                "updated_at": "2026-04-03T00:42:02Z",
            },
            "error": {
                "code": "upstream_unavailable",
                "message": "Travel-Plan-Permission did not return a valid evaluation payload.",
                "category": "upstream",
                "retryable": True,
                "details": {
                    "provider": "Travel-Plan-Permission",
                    "http_status": 502,
                },
            },
            "retry": {
                "attempt": 1,
                "max_attempts": 4,
                "retryable": True,
                "backoff_seconds": 60,
                "next_retry_at": "2026-04-03T00:43:02Z",
                "reason": "Transient upstream outage",
            },
            "received_at": "2026-04-03T00:42:02Z",
            "status_endpoint": "https://tpp.example.test/api/planner/proposals/proposal-live/executions/exec-failed-001",
        },
    )
    _install_fake_http(monkeypatch, [poll_response])

    created = client.post(
        "/api/trips",
        json={
            "title": "Refresh proposal failure",
            "summary": "Persist live TPP execution failures in the workspace.",
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
    submission_fixture["response"]["result_payload"]["execution_id"] = "exec-failed-001"
    submission_fixture["response"][
        "status_endpoint"
    ] = "https://tpp.example.test/api/planner/proposals/proposal-live/executions/exec-failed-001"

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

    refreshed = client.post(f"/api/workspace/{trip_id}/proposal/refresh")

    assert refreshed.status_code == 200
    payload = refreshed.json()["proposal_state"]
    assert payload["submission_status"] == "failed"
    assert payload["evaluation"] == {}
    assert payload["summary"]["submission_requires_polling"] is False
    assert payload["summary"]["evaluation_transport_status"] is None
    assert payload["summary"]["submission_summary"] == "Evaluator returned an integration error"
    assert payload["summary"]["submission_error"]["code"] == "upstream_unavailable"
    assert payload["summary"]["submission_error"]["category"] == "upstream"
    assert payload["summary"]["submission_error"]["retryable"] is True
    assert (
        payload["summary"]["submission_error"]["message"]
        == "Travel-Plan-Permission did not return a valid evaluation payload."
    )
    assert payload["summary"]["submission_retry"]["reason"] == "Transient upstream outage"


def test_workspace_proposal_refresh_persists_configuration_failure_for_reload(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TPP_BASE_URL", raising=False)
    monkeypatch.delenv("TPP_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("TPP_OIDC_PROVIDER", raising=False)

    created = client.post(
        "/api/trips",
        json={
            "title": "Refresh proposal config blocker",
            "summary": "Persist live TPP config failures in workspace state.",
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
    submission_fixture["response"]["result_payload"]["execution_id"] = "exec-config-001"
    submission_fixture["response"][
        "status_endpoint"
    ] = "https://tpp.example.test/api/planner/proposals/proposal-live/executions/exec-config-001"

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

    refreshed = client.post(f"/api/workspace/{trip_id}/proposal/refresh")

    assert refreshed.status_code == 200
    payload = refreshed.json()["proposal_state"]
    assert payload["submission_status"] == "failed"
    assert payload["summary"]["submission_requires_polling"] is False
    assert payload["summary"]["submission_error"]["code"] == (
        "submission_refresh_configuration_failed"
    )
    assert payload["summary"]["submission_error"]["category"] == "configuration"
    assert payload["summary"]["submission_error"]["retryable"] is True
    assert "TPP_BASE_URL" in payload["summary"]["submission_error"]["message"]
    assert payload["summary"]["submission_retry"]["retryable"] is True
    assert payload["submission"]["last_known_execution_status"]["state"] == "deferred"

    reloaded = client.get(f"/api/workspace/{trip_id}/proposal")
    assert reloaded.status_code == 200
    reloaded_payload = reloaded.json()["proposal_state"]
    assert reloaded_payload["summary"]["submission_error"]["category"] == "configuration"
    assert reloaded_payload["submission"]["last_poll_request_payload"] == {
        "proposal_version": "proposal-v3",
        "execution_id": "exec-config-001",
    }


def test_workspace_proposal_refresh_preserves_submission_and_retries_when_evaluation_ingestion_fails(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TPP_BASE_URL", "https://tpp.example.test")
    monkeypatch.setenv("TPP_ACCESS_TOKEN", "token-123")
    monkeypatch.setenv("TPP_OIDC_PROVIDER", "okta")
    captured_requests: list[dict[str, object]] = []
    submission_response = _FakeHTTPResponse(
        200,
        _load_fixture("proposal_submit_deferred.json")["response"],
    )
    submission_result_payload = cast(
        dict[str, object], submission_response._payload["result_payload"]
    )
    submission_result_payload["execution_id"] = "exec-live-002"
    submission_response._payload["status_endpoint"] = (
        "https://tpp.example.test/api/planner/proposals/proposal-live/executions/exec-live-002"
    )
    submission_response.text = json.dumps(submission_response._payload)
    poll_response = _FakeHTTPResponse(
        200,
        {
            "transport_pattern": "async",
            "execution_status": {
                "state": "succeeded",
                "terminal": True,
                "summary": "Policy execution completed and the evaluation result is ready.",
                "external_status": "completed",
                "updated_at": "2026-04-03T00:42:11Z",
            },
            "result_payload": {
                "execution_id": "exec-live-002",
                "queue_state": "completed",
            },
            "received_at": "2026-04-03T00:42:11Z",
            "status_endpoint": (
                "https://tpp.example.test/api/planner/proposals/proposal-live/executions/exec-live-002"
            ),
        },
    )
    malformed_evaluation_response = _FakeHTTPResponse(
        200,
        {
            "trip_id": "trip-placeholder",
            "proposal_id": "proposal:trip-placeholder",
            "proposal_version": "proposal-v3",
            "execution_id": "exec-live-002",
            "request_id": "ignored-eval",
            "correlation_id": {"value": "ignored", "issued_by": "tpp"},
            "outcome": "non_compliant",
            "result_endpoint": "GET /api/planner/executions/exec-live-002/evaluation-result",
            "status_endpoint": (
                "https://tpp.example.test/api/planner/proposals/proposal-live/executions/exec-live-002"
            ),
            "generated_at": "2026-04-03T00:42:13Z",
        },
    )
    _install_fake_http(
        monkeypatch,
        [submission_response, poll_response, malformed_evaluation_response],
        captured_requests=captured_requests,
    )

    created = client.post(
        "/api/trips",
        json={
            "title": "Refresh proposal retry",
            "summary": "Keep refresh retryable when evaluation ingestion fails.",
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
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )
    assert submitted.status_code == 200

    refreshed = client.post(f"/api/workspace/{trip_id}/proposal/refresh")

    assert refreshed.status_code == 200
    payload = refreshed.json()["proposal_state"]
    assert payload["submission"]["request_id"] == submission_fixture["request"]["request_id"]
    assert payload["submission"]["request_payload"]["proposal_ref"] == f"proposal:{trip_id}"
    assert payload["submission"]["last_poll_request_payload"] == {
        "proposal_version": "proposal-v3",
        "execution_id": "exec-live-002",
    }
    assert payload["submission_status"] == "succeeded"
    assert payload["evaluation_status"] == "retry_scheduled"
    assert payload["summary"]["submission_requires_polling"] is True
    assert payload["summary"]["evaluation_transport_status"] == "retry_scheduled"
    assert payload["summary"]["evaluation_result_status"] is None
    assert payload["follow_up"]["status"] == "awaiting_evaluation"
    assert payload["evaluation"]["error"]["code"] == "evaluation_refresh_failed"
    assert payload["evaluation"]["error"]["retryable"] is True
    assert captured_requests[2]["full_url"] == (
        "https://tpp.example.test/api/planner/executions/exec-live-002/evaluation-result"
    )


def test_evaluation_result_payload_complete_fields_are_persisted_and_reloadable(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Evaluation persistence workspace",
            "summary": "Verify all evaluation payload fields survive persist-reload cycle.",
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
    client.put(
        f"/api/workspace/{trip_id}/proposal",
        json={
            "proposal": _proposal_payload(trip_id),
            "request": submission_fixture["request"],
            "response": submission_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )

    evaluation_fixture = _load_fixture("results", "approved_evaluation.json")
    evaluation_fixture["request"]["trip_id"] = trip_id
    evaluation_fixture["request"]["proposal_id"] = f"proposal:{trip_id}"
    evaluation_fixture["response"]["result_payload"]["trip_id"] = trip_id
    evaluation_fixture["response"]["result_payload"]["proposal_id"] = f"proposal:{trip_id}"
    evaluation_fixture["response"]["result_payload"]["evaluation_result"][
        "proposal_id"
    ] = f"proposal:{trip_id}"
    client.put(
        f"/api/workspace/{trip_id}/proposal/evaluation",
        json={
            "request": evaluation_fixture["request"],
            "response": evaluation_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )

    reloaded = client.get(f"/api/workspace/{trip_id}/proposal")
    assert reloaded.status_code == 200
    evaluation = reloaded.json()["proposal_state"]["evaluation"]

    assert evaluation["linkage"]["trip_id"] == trip_id
    assert evaluation["linkage"]["proposal_id"] == f"proposal:{trip_id}"
    assert evaluation["linkage"]["proposal_version"] == "proposal-v3"
    assert evaluation["linkage"]["scenario_id"] == "scenario-a"
    assert evaluation["linkage"]["execution_id"] == "exec-approved-001"
    assert evaluation["linkage"]["organization_id"] == "org-acme"

    assert evaluation["transport_pattern"] == "async"
    assert evaluation["execution_status"]["state"] == "succeeded"
    assert evaluation["execution_status"]["terminal"] is True

    result = evaluation["evaluation_result"]
    assert result["status"] == "compliant"
    assert result["evaluation_id"] == "eval-approved-001"
    assert result["proposal_id"] == f"proposal:{trip_id}"
    assert result["approval_requirements"][0]["role"] == "manager"
    assert result["compliance_score"] == 0.98
    assert result["notes"] == ["Policy constraints satisfied."]

    assert "exec-approved-001" in evaluation["status_endpoint"]


def test_failed_evaluation_error_and_retry_fields_are_persisted_and_reloadable(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Failed evaluation persistence workspace",
            "summary": "Verify error and retry fields are reloadable from workspace state.",
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
    client.put(
        f"/api/workspace/{trip_id}/proposal",
        json={
            "proposal": _proposal_payload(trip_id),
            "request": submission_fixture["request"],
            "response": submission_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )

    failed_fixture = _load_fixture("results", "failed_execution.json")
    failed_fixture["request"]["trip_id"] = trip_id
    failed_fixture["request"]["proposal_id"] = f"proposal:{trip_id}"
    client.put(
        f"/api/workspace/{trip_id}/proposal/evaluation",
        json={
            "request": failed_fixture["request"],
            "response": failed_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )

    reloaded = client.get(f"/api/workspace/{trip_id}/proposal")
    assert reloaded.status_code == 200
    state = reloaded.json()["proposal_state"]
    evaluation = state["evaluation"]

    assert evaluation["execution_status"]["state"] == "failed"
    assert evaluation["execution_status"]["terminal"] is True
    assert evaluation["evaluation_result"] is None

    assert evaluation["error"]["code"] == "upstream_unavailable"
    assert evaluation["error"]["retryable"] is True
    assert evaluation["error"]["category"] == "upstream"

    assert evaluation["retry"]["attempt"] == 1
    assert evaluation["retry"]["max_attempts"] == 4
    assert evaluation["retry"]["retryable"] is True
    assert evaluation["retry"]["backoff_seconds"] == 60

    assert state["evaluation_status"] == "failed"
    assert state["summary"]["evaluation_result_status"] is None
