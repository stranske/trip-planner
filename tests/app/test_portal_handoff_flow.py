"""Exercise handoff preparation through the Policy tab's submit/refresh routes."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.app.tpp_intercept import seed_policy
from trip_planner.integrations.tpp.client import HTTPTPPIntegrationClient
from trip_planner.integrations.tpp.contracts import TPPResponseEnvelope


@pytest.fixture
def submitted_trip(tpp_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> str:
    # The browser cannot inject a response envelope in the production flow.
    monkeypatch.delenv("TRIP_PLANNER_ALLOW_FIXTURE_TPP_RESPONSES", raising=False)
    monkeypatch.setenv("TPP_PORTAL_BASE_URL", "https://tpp.example")
    created = tpp_client.post(
        "/api/trips",
        json={
            "title": "Chicago client visit",
            "summary": "Review the client's quarterly plan",
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
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]
    seed_policy(tpp_client, trip_id)
    priced = tpp_client.put(
        f"/api/workspace/{trip_id}/prices",
        json={"component": "lodging", "amount": 612.0, "note": "Hyatt corporate quote"},
    )
    assert priced.status_code == 200
    submitted = tpp_client.post(f"/api/workspace/{trip_id}/proposal/submit", json={})
    assert submitted.status_code == 200
    assert submitted.json()["proposal_state"]["portal_handoff"]["status"] == "awaiting_evaluation"
    assert tpp_client.post(f"/api/workspace/{trip_id}/proposal/handoff", json={}).status_code == 409
    return trip_id


def _install_verdict_transport(
    monkeypatch: pytest.MonkeyPatch, outcome: str, policy_signal: str = "queue"
) -> list[str]:
    operations: list[str] = []

    def poll(self, request):
        operations.append(request.operation)
        failed = outcome != "compliant"
        response = {
            "operation": request.operation,
            "request_id": request.request_id,
            "correlation_id": request.correlation_id.to_dict(),
            "transport_pattern": request.transport_pattern,
            "execution_status": {"state": "failed" if failed else "deferred", "terminal": failed},
            "result_payload": {
                "execution_id": request.payload["execution_id"],
                "queue_state": (
                    "blocked_by_policy"
                    if outcome == "non_compliant" and policy_signal == "queue"
                    else "queued"
                ),
            },
        }
        if failed:
            response["error"] = {
                "code": "proposal_blocked_by_policy" if outcome == "non_compliant" else "timeout",
                "category": (
                    "policy"
                    if outcome == "non_compliant" and policy_signal == "error"
                    else "transport"
                ),
                "message": (
                    "Policy refused the proposal" if outcome == "non_compliant" else "Timeout"
                ),
                "retryable": False,
            }
        return TPPResponseEnvelope.from_dict(response)

    def fetch(self, request):
        operations.append(request.operation)
        fixture_name = (
            "approved_evaluation.json"
            if outcome == "compliant"
            else "non_compliant_evaluation.json"
        )
        fixture = Path(__file__).resolve().parents[1] / "fixtures/integrations/tpp/results"
        response = json.loads((fixture / fixture_name).read_text())["response"]
        response.update(
            request_id=request.request_id,
            correlation_id=request.correlation_id.to_dict(),
            transport_pattern=request.transport_pattern,
        )
        response["result_payload"].update(
            trip_id=request.trip_id,
            proposal_id=request.proposal_id,
            proposal_version=request.payload["proposal_version"],
            scenario_id=request.payload.get("scenario_id"),
            execution_id=request.payload["execution_id"],
        )
        response["result_payload"]["evaluation_result"]["proposal_id"] = request.proposal_id
        return TPPResponseEnvelope.from_dict(response)

    monkeypatch.setattr(HTTPTPPIntegrationClient, "poll_execution_status", poll)
    monkeypatch.setattr(HTTPTPPIntegrationClient, "fetch_evaluation_result", fetch)
    return operations


@pytest.mark.parametrize(
    ("outcome", "policy_signal"),
    [
        ("compliant", "queue"),
        ("non_compliant", "queue"),
        ("non_compliant", "error"),
        ("transport_failed", "error"),
    ],
)
def test_policy_tab_verdict_controls_browser_handoff(
    tpp_client: TestClient,
    submitted_trip: str,
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
    policy_signal: str,
) -> None:
    operations = _install_verdict_transport(monkeypatch, outcome, policy_signal)
    refreshed = tpp_client.post(f"/api/workspace/{submitted_trip}/proposal/refresh")
    assert refreshed.status_code == 200
    prepared = tpp_client.post(f"/api/workspace/{submitted_trip}/proposal/handoff", json={})
    if outcome == "transport_failed":
        assert operations == ["poll_execution_status"]
        assert prepared.status_code == 409
        return

    assert operations == ["poll_execution_status", "fetch_evaluation_result"]
    assert refreshed.json()["proposal_state"]["summary"]["evaluation_result_status"] == outcome
    assert prepared.status_code == 200
    payload = prepared.json()
    assert payload["action_url"] == "https://tpp.example/portal/handoff"
    assert payload["method"] == "POST"
    assert payload["fields"]["traveler_name"] == "Dana Chen"
    assert payload["fields"]["business_purpose"] == "Review the client's quarterly plan"
    assert "USD 612.00" in payload["fields"]["notes"]
    assert f"status={outcome}" in payload["fields"]["notes"]
    metadata = payload["handoff"]
    assert metadata["status"] == "prepared"
    assert metadata["manager_submission_status"] == "unknown"
    assert metadata["manager_decision"] is None
    assert "source_snapshot" not in metadata
    reloaded = tpp_client.get(f"/api/workspace/{submitted_trip}/proposal")
    assert reloaded.json()["proposal_state"]["portal_handoff"] == metadata


def test_refresh_does_not_authorize_prices_changed_after_policy_submission(
    tpp_client: TestClient, submitted_trip: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_verdict_transport(monkeypatch, "compliant")
    updated = tpp_client.put(
        f"/api/workspace/{submitted_trip}/prices",
        json={"component": "lodging", "amount": 700.0, "note": "Updated Hyatt quote"},
    )
    assert updated.status_code == 200
    refreshed = tpp_client.post(f"/api/workspace/{submitted_trip}/proposal/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["proposal_state"]["summary"]["evaluation_result_status"] == "compliant"
    prepared = tpp_client.post(f"/api/workspace/{submitted_trip}/proposal/handoff", json={})
    assert prepared.status_code == 409
    assert "Run the policy check again" in prepared.json()["detail"]


@pytest.mark.parametrize("outcome", ["compliant", "non_compliant"])
def test_saved_verdict_handoff_does_not_call_the_policy_api(
    tpp_client: TestClient,
    submitted_trip: str,
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
) -> None:
    operations = _install_verdict_transport(monkeypatch, outcome)
    refreshed = tpp_client.post(f"/api/workspace/{submitted_trip}/proposal/refresh")
    assert refreshed.status_code == 200
    before = refreshed.json()["proposal_state"]
    assert before["summary"]["evaluation_result_status"] == outcome
    bound_hash = before["portal_handoff"]["source_snapshot_hash"]

    # Once a verdict is saved, only the browser contacts the portal. Preparation
    # must not depend on the policy API being available or resubmit the proposal.
    def unavailable(*args, **kwargs):
        pytest.fail("Preparing a saved-verdict handoff called the policy API")

    for operation in (
        "fetch_policy_constraints",
        "submit_proposal",
        "poll_execution_status",
        "fetch_evaluation_result",
    ):
        monkeypatch.setattr(HTTPTPPIntegrationClient, operation, unavailable)
    monkeypatch.delenv("TPP_BASE_URL", raising=False)
    monkeypatch.setenv("TRIP_PLANNER_ENV", "production")
    monkeypatch.setenv("TPP_PORTAL_BASE_URL", "https://traveler-portal.example:8443/")

    for _ in range(2):
        prepared = tpp_client.post(f"/api/workspace/{submitted_trip}/proposal/handoff", json={})
        assert prepared.status_code == 200
        assert prepared.headers["cache-control"] == "no-store"
        payload = prepared.json()
        assert payload["action_url"] == "https://traveler-portal.example:8443/portal/handoff"
        assert payload["method"] == "POST"
        assert payload["fields"]["traveler_name"] == "Dana Chen"
        assert "USD 612.00" in payload["fields"]["notes"]
        assert f"status={outcome}" in payload["fields"]["notes"]
        assert payload["handoff"]["source_snapshot_hash"] == bound_hash
        assert payload["handoff"]["status"] == "prepared"
        assert payload["handoff"]["manager_submission_status"] == "unknown"
        assert payload["handoff"]["manager_decision"] is None
        assert "source_snapshot" not in payload["handoff"]

    reloaded = tpp_client.get(f"/api/workspace/{submitted_trip}/proposal")
    assert reloaded.status_code == 200
    assert reloaded.json()["proposal_state"]["portal_handoff"] == payload["handoff"]
    assert reloaded.json()["proposal_state"]["evaluation"] == before["evaluation"]
    assert operations == ["poll_execution_status", "fetch_evaluation_result"]
