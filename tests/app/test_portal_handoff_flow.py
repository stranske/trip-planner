"""Exercise handoff preparation through the Policy tab's submit/refresh routes."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.app.tpp_intercept import seed_policy
from trip_planner.integrations.tpp.client import HTTPTPPIntegrationClient
from trip_planner.integrations.tpp.contracts import TPPResponseEnvelope
from trip_planner.persistence.db import get_session_factory
from trip_planner.persistence.models.account import UserAccount


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


@pytest.mark.parametrize("outcome", ["compliant", "non_compliant"])
def test_saved_text_reaches_server_owned_form_without_url_encoding_or_html_escaping(
    tpp_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
) -> None:
    monkeypatch.delenv("TRIP_PLANNER_ALLOW_FIXTURE_TPP_RESPONSES", raising=False)
    monkeypatch.setenv("TPP_PORTAL_BASE_URL", "https://tpp.example")
    traveler = "Dana José 陳"
    purpose = 'Review R&D = Q4 + forecasts <with "client">'
    destination = "Montréal & Québec"
    note = 'Hôtel quote: taxes + fees = $612.00 & breakfast\nReference <Q4> "confirmed"'
    with get_session_factory()() as session:
        account = session.query(UserAccount).filter_by(email="p@example.com").one()
        account.display_name = traveler
        session.commit()

    created = tpp_client.post(
        "/api/trips",
        json={
            "title": "Québec client visit",
            "summary": purpose,
            "mode": "business",
            "trip_frame": {
                "origin": "Seattle",
                "start_date": "2027-01-05",
                "end_date": "2027-01-07",
                "duration_days": 3,
                "primary_regions": [destination],
            },
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]
    seed_policy(tpp_client, trip_id)
    assert (
        tpp_client.put(
            f"/api/workspace/{trip_id}/prices",
            json={"component": "lodging", "amount": 612.0, "note": note},
        ).status_code
        == 200
    )
    path = f"/api/workspace/{trip_id}/proposal"
    assert tpp_client.post(f"{path}/submit", json={}).status_code == 200
    _install_verdict_transport(monkeypatch, outcome)
    assert tpp_client.post(f"{path}/refresh").status_code == 200
    monkeypatch.setenv("TRIP_PLANNER_ENV", "production")

    forms = []
    for _ in range(2):
        response = tpp_client.post(f"{path}/handoff", json={})
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        form = response.json()
        assert form["action_url"] == "https://tpp.example/portal/handoff"
        assert form["method"] == "POST"
        assert form["fields"]["traveler_name"] == traveler
        assert form["fields"]["business_purpose"] == purpose
        assert form["fields"]["city_state"] == destination
        assert note in form["fields"]["notes"]
        assert f"status={outcome}" in form["fields"]["notes"]
        assert "source_snapshot" not in form["handoff"]
        assert form["handoff"]["manager_submission_status"] == "unknown"
        assert form["handoff"]["manager_decision"] is None
        assert tpp_client.get(path).json()["proposal_state"]["portal_handoff"] == form["handoff"]
        forms.append(form)
    assert forms[0]["fields"] == forms[1]["fields"]
    assert forms[0]["handoff"]["source_snapshot_hash"] == (
        forms[1]["handoff"]["source_snapshot_hash"]
    )


@pytest.mark.parametrize(
    ("previous_outcome", "new_outcome"),
    [("compliant", "non_compliant"), ("non_compliant", "compliant")],
)
def test_new_policy_check_requires_its_own_verdict_before_preparing_another_form(
    tpp_client: TestClient,
    submitted_trip: str,
    monkeypatch: pytest.MonkeyPatch,
    previous_outcome: str,
    new_outcome: str,
) -> None:
    previous_operations = _install_verdict_transport(monkeypatch, previous_outcome)
    proposal_path = f"/api/workspace/{submitted_trip}/proposal"
    assert tpp_client.post(f"{proposal_path}/refresh").status_code == 200
    previous_form = tpp_client.post(f"{proposal_path}/handoff", json={})
    assert previous_form.status_code == 200
    previous_hash = previous_form.json()["handoff"]["source_snapshot_hash"]

    # Model a separate producer execution even when the traveler checks unchanged facts.
    submit = HTTPTPPIntegrationClient.submit_proposal

    def submit_again(self, request):
        response = submit(self, request).to_dict()
        response["result_payload"]["execution_id"] = "exec-recheck"
        return TPPResponseEnvelope.from_dict(response)

    monkeypatch.setattr(HTTPTPPIntegrationClient, "submit_proposal", submit_again)
    submitted = tpp_client.post(f"{proposal_path}/submit", json={})
    assert submitted.status_code == 200
    pending = submitted.json()
    assert pending["proposal_state"]["execution_id"] == "exec-recheck"
    assert pending["proposal_state"]["evaluation"] == {}
    assert pending["proposal_state"]["summary"]["evaluation_result_status"] is None
    metadata = pending["proposal_state"]["portal_handoff"]
    assert metadata["status"] == "awaiting_evaluation"
    assert metadata["prepared_at"] is None
    assert metadata["manager_submission_status"] == "unknown"
    assert metadata["manager_decision"] is None

    # The previous saved verdict and preparation cannot authorize the new execution.
    refused = tpp_client.post(f"{proposal_path}/handoff", json={})
    assert refused.status_code == 409
    assert "Run the policy check again" in refused.json()["detail"]
    assert tpp_client.get(proposal_path).json() == pending

    new_operations = _install_verdict_transport(monkeypatch, new_outcome)
    refreshed = tpp_client.post(f"{proposal_path}/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["proposal_state"]["summary"]["evaluation_result_status"] == new_outcome
    prepared = tpp_client.post(f"{proposal_path}/handoff", json={})
    assert prepared.status_code == 200
    payload = prepared.json()
    assert payload["action_url"] == "https://tpp.example/portal/handoff"
    assert payload["method"] == "POST"
    assert f"status={new_outcome};" in payload["fields"]["notes"]
    assert f"status={previous_outcome};" not in payload["fields"]["notes"]
    assert "execution=exec-recheck." in payload["fields"]["notes"]
    assert payload["handoff"]["source_snapshot_hash"] != previous_hash
    assert payload["handoff"]["status"] == "prepared"
    assert payload["handoff"]["manager_submission_status"] == "unknown"
    assert payload["handoff"]["manager_decision"] is None
    assert (
        tpp_client.get(proposal_path).json()["proposal_state"]["portal_handoff"]
        == payload["handoff"]
    )
    assert (
        previous_operations
        == new_operations
        == ["poll_execution_status", "fetch_evaluation_result"]
    )


@pytest.mark.parametrize("outcome", ["compliant", "non_compliant"])
@pytest.mark.parametrize("already_prepared", [False, True])
@pytest.mark.parametrize(
    "mapping_failure",
    [
        "raised",
        "missing_fields",
        "empty_fields",
        "invalid_field_value",
        "private_snapshot",
        "unsupported_field",
    ],
)
def test_failed_form_preparation_preserves_saved_state_and_can_be_retried(
    tpp_client: TestClient,
    submitted_trip: str,
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
    already_prepared: bool,
    mapping_failure: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    operations = _install_verdict_transport(monkeypatch, outcome)
    refreshed = tpp_client.post(f"/api/workspace/{submitted_trip}/proposal/refresh")
    assert refreshed.status_code == 200
    path = f"/api/workspace/{submitted_trip}/proposal/handoff"
    if already_prepared:
        assert tpp_client.post(path, json={}).status_code == 200
    before = tpp_client.get(f"/api/workspace/{submitted_trip}/proposal").json()

    def cannot_build_fields(snapshot):
        if mapping_failure == "raised":
            raise ValueError("Portal form mapping failed")
        if mapping_failure == "missing_fields":
            return None
        if mapping_failure == "empty_fields":
            return {}
        if mapping_failure == "private_snapshot":
            return {
                "traveler_name": snapshot["traveler_name"],
                "source_snapshot": json.dumps(
                    {**snapshot, "internal_note": "Private traveler fact"}
                ),
            }
        if mapping_failure == "unsupported_field":
            return {
                "traveler_name": snapshot["traveler_name"],
                "return_url": "https://caller.example/Private traveler fact",
            }
        return {"traveler_name": ["Private traveler fact"]}

    with monkeypatch.context() as failed_mapping:
        failed_mapping.setattr(
            "trip_planner.app.services.proposal.build_portal_fields", cannot_build_fields
        )
        failed = tpp_client.post(path, json={})
    assert failed.status_code == 422
    assert "Private traveler fact" not in failed.text
    assert "Private traveler fact" not in caplog.text
    assert tpp_client.get(f"/api/workspace/{submitted_trip}/proposal").json() == before

    # The same saved verdict remains usable once form generation recovers.
    retried = tpp_client.post(path, json={})
    assert retried.status_code == 200
    payload = retried.json()
    assert payload["action_url"] == "https://tpp.example/portal/handoff"
    assert payload["fields"]["traveler_name"] == "Dana Chen"
    assert f"status={outcome}" in payload["fields"]["notes"]
    assert payload["handoff"]["status"] == "prepared"
    assert payload["handoff"]["manager_submission_status"] == "unknown"
    assert payload["handoff"]["manager_decision"] is None
    assert (
        payload["handoff"]["source_snapshot_hash"]
        == before["proposal_state"]["portal_handoff"]["source_snapshot_hash"]
    )
    assert operations == ["poll_execution_status", "fetch_evaluation_result"]


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


@pytest.mark.parametrize("outcome", ["compliant", "non_compliant"])
def test_unchanged_verdict_refresh_preserves_prepared_handoff(
    tpp_client: TestClient,
    submitted_trip: str,
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
) -> None:
    operations = _install_verdict_transport(monkeypatch, outcome)
    refresh_path = f"/api/workspace/{submitted_trip}/proposal/refresh"
    assert tpp_client.post(refresh_path).status_code == 200
    prepared = tpp_client.post(f"/api/workspace/{submitted_trip}/proposal/handoff", json={})
    assert prepared.status_code == 200
    metadata = prepared.json()["handoff"]

    for _ in range(2):
        refreshed = tpp_client.post(refresh_path)
        assert refreshed.status_code == 200
        assert refreshed.json()["proposal_state"]["portal_handoff"] == metadata
        reloaded = tpp_client.get(f"/api/workspace/{submitted_trip}/proposal")
        assert reloaded.status_code == 200
        assert reloaded.json()["proposal_state"]["portal_handoff"] == metadata

    assert metadata["status"] == "prepared"
    assert metadata["prepared_at"] is not None
    assert metadata["manager_submission_status"] == "unknown"
    assert metadata["manager_decision"] is None
    assert "source_snapshot" not in metadata
    assert operations == ["poll_execution_status", "fetch_evaluation_result"] * 3


@pytest.mark.parametrize(
    ("old_outcome", "new_outcome"),
    [("compliant", "non_compliant"), ("non_compliant", "compliant")],
)
def test_changed_verdict_refresh_requires_new_handoff_preparation(
    tpp_client: TestClient,
    submitted_trip: str,
    monkeypatch: pytest.MonkeyPatch,
    old_outcome: str,
    new_outcome: str,
) -> None:
    _install_verdict_transport(monkeypatch, old_outcome)
    refresh_path = f"/api/workspace/{submitted_trip}/proposal/refresh"
    handoff_path = f"/api/workspace/{submitted_trip}/proposal/handoff"
    assert tpp_client.post(refresh_path).status_code == 200
    prepared = tpp_client.post(handoff_path, json={})
    assert prepared.status_code == 200
    old_metadata = prepared.json()["handoff"]

    operations = _install_verdict_transport(monkeypatch, new_outcome)
    refreshed = tpp_client.post(refresh_path)
    assert refreshed.status_code == 200
    metadata = refreshed.json()["proposal_state"]["portal_handoff"]
    assert metadata["status"] == "eligible"
    assert metadata["prepared_at"] is None
    assert metadata["source_snapshot_hash"] != old_metadata["source_snapshot_hash"]
    assert metadata["manager_submission_status"] == "unknown"
    assert metadata["manager_decision"] is None
    assert "source_snapshot" not in metadata
    assert (
        tpp_client.get(f"/api/workspace/{submitted_trip}/proposal").json()["proposal_state"][
            "portal_handoff"
        ]
        == metadata
    )

    prepared_again = tpp_client.post(handoff_path, json={})
    assert prepared_again.status_code == 200
    payload = prepared_again.json()
    assert payload["handoff"]["status"] == "prepared"
    assert payload["handoff"]["source_snapshot_hash"] == metadata["source_snapshot_hash"]
    assert f"status={new_outcome};" in payload["fields"]["notes"]
    assert operations == ["poll_execution_status", "fetch_evaluation_result"]


@pytest.mark.parametrize("outcome", ["compliant", "non_compliant"])
@pytest.mark.parametrize(
    "caller_payload",
    [
        {"action_url": "https://caller.example/portal/handoff"},
        {"fields": {"traveler_name": "Caller", "destination_zip": "99999"}},
        {"method": "GET"},
        {"handoff": {"status": "sent", "manager_decision": "approved"}},
    ],
)
def test_production_handoff_rejects_overrides_without_mutating_the_saved_verdict(
    tpp_client: TestClient,
    submitted_trip: str,
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
    caller_payload: dict,
) -> None:
    operations = _install_verdict_transport(monkeypatch, outcome)
    refreshed = tpp_client.post(f"/api/workspace/{submitted_trip}/proposal/refresh")
    assert refreshed.status_code == 200
    before = refreshed.json()
    assert before["proposal_state"]["portal_handoff"]["status"] == "eligible"
    monkeypatch.setenv("TRIP_PLANNER_ENV", "production")
    monkeypatch.setenv("TPP_PORTAL_BASE_URL", "https://traveler-portal.example")

    def unavailable(*args, **kwargs):
        pytest.fail("Handoff preparation must use the saved verdict without contacting TPP")

    for operation in (
        "fetch_policy_constraints",
        "submit_proposal",
        "poll_execution_status",
        "fetch_evaluation_result",
    ):
        monkeypatch.setattr(HTTPTPPIntegrationClient, operation, unavailable)

    path = f"/api/workspace/{submitted_trip}/proposal/handoff"
    rejected = tpp_client.post(path, json=caller_payload)
    assert rejected.status_code == 422
    assert all(error["type"] == "extra_forbidden" for error in rejected.json()["detail"])
    assert tpp_client.get(f"/api/workspace/{submitted_trip}/proposal").json() == before

    # Rejection must leave a valid saved verdict available for the browser's empty request.
    prepared = tpp_client.post(path, json={})
    assert prepared.status_code == 200
    assert prepared.headers["cache-control"] == "no-store"
    payload = prepared.json()
    assert payload["action_url"] == "https://traveler-portal.example/portal/handoff"
    assert payload["method"] == "POST"
    assert payload["fields"]["traveler_name"] == "Dana Chen"
    assert "destination_zip" not in payload["fields"]
    assert f"status={outcome}" in payload["fields"]["notes"]
    assert payload["handoff"]["status"] == "prepared"
    assert payload["handoff"]["manager_submission_status"] == "unknown"
    assert payload["handoff"]["manager_decision"] is None
    assert (
        payload["handoff"]["source_snapshot_hash"]
        == before["proposal_state"]["portal_handoff"]["source_snapshot_hash"]
    )
    assert operations == ["poll_execution_status", "fetch_evaluation_result"]


def test_production_handoff_uses_requested_trip_not_travelers_latest_policy_check(
    tpp_client: TestClient, submitted_trip: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_operations = _install_verdict_transport(monkeypatch, "compliant")
    assert tpp_client.post(f"/api/workspace/{submitted_trip}/proposal/refresh").status_code == 200
    first_before = tpp_client.get(f"/api/workspace/{submitted_trip}/proposal").json()

    created = tpp_client.post(
        "/api/trips",
        json={
            "title": "Boston planning visit",
            "summary": "Review the Boston team's annual plan",
            "mode": "business",
            "trip_frame": {
                "origin": "Portland",
                "start_date": "2027-02-08",
                "end_date": "2027-02-10",
                "duration_days": 3,
                "primary_regions": ["Boston"],
            },
        },
    )
    assert created.status_code == 201
    second_trip = created.json()["trip"]["trip_id"]
    seed_policy(tpp_client, second_trip)
    assert (
        tpp_client.put(
            f"/api/workspace/{second_trip}/prices",
            json={"component": "lodging", "amount": 825.0, "note": "Boston hotel quote"},
        ).status_code
        == 200
    )
    assert (
        tpp_client.post(f"/api/workspace/{second_trip}/proposal/submit", json={}).status_code == 200
    )
    second_before = tpp_client.get(f"/api/workspace/{second_trip}/proposal").json()

    # Another trip's saved verdict cannot authorize this still-pending proposal.
    assert (
        tpp_client.post(f"/api/workspace/{second_trip}/proposal/handoff", json={}).status_code
        == 409
    )
    assert tpp_client.get(f"/api/workspace/{second_trip}/proposal").json() == second_before
    assert tpp_client.get(f"/api/workspace/{submitted_trip}/proposal").json() == first_before

    second_operations = _install_verdict_transport(monkeypatch, "non_compliant")
    assert tpp_client.post(f"/api/workspace/{second_trip}/proposal/refresh").status_code == 200
    second_before = tpp_client.get(f"/api/workspace/{second_trip}/proposal").json()
    monkeypatch.setenv("TRIP_PLANNER_ENV", "production")

    def unavailable(*args, **kwargs):
        pytest.fail("Preparing either trip must use its own saved verdict without contacting TPP")

    for operation in (
        "fetch_policy_constraints",
        "submit_proposal",
        "poll_execution_status",
        "fetch_evaluation_result",
    ):
        monkeypatch.setattr(HTTPTPPIntegrationClient, operation, unavailable)

    prepared_forms = []
    for trip_id, city, purpose, price, outcome, before in (
        (
            submitted_trip,
            "Chicago",
            "Review the client's quarterly plan",
            "USD 612.00",
            "compliant",
            first_before,
        ),
        (
            second_trip,
            "Boston",
            "Review the Boston team's annual plan",
            "USD 825.00",
            "non_compliant",
            second_before,
        ),
    ):
        other_trip = second_trip if trip_id == submitted_trip else submitted_trip
        other_saved = tpp_client.get(f"/api/workspace/{other_trip}/proposal").json()
        response = tpp_client.post(f"/api/workspace/{trip_id}/proposal/handoff", json={})
        assert response.status_code == 200
        payload = response.json()
        prepared_forms.append(payload)
        assert payload["action_url"] == "https://tpp.example/portal/handoff"
        assert payload["method"] == "POST"
        assert payload["fields"]["city_state"] == city
        assert payload["fields"]["business_purpose"] == purpose
        assert price in payload["fields"]["notes"]
        assert f"trip={trip_id};" in payload["fields"]["notes"]
        assert f"trip={other_trip};" not in payload["fields"]["notes"]
        assert f"status={outcome};" in payload["fields"]["notes"]
        assert (
            payload["handoff"]["source_snapshot_hash"]
            == before["proposal_state"]["portal_handoff"]["source_snapshot_hash"]
        )
        assert payload["handoff"]["manager_submission_status"] == "unknown"
        assert payload["handoff"]["manager_decision"] is None
        assert "source_snapshot" not in payload["handoff"]
        reloaded = tpp_client.get(f"/api/workspace/{trip_id}/proposal").json()
        assert reloaded["proposal_state"]["portal_handoff"] == payload["handoff"]
        assert reloaded["proposal_state"]["evaluation"] == before["proposal_state"]["evaluation"]
        assert tpp_client.get(f"/api/workspace/{other_trip}/proposal").json() == other_saved

    assert prepared_forms[0]["handoff"]["source_snapshot_hash"] != (
        prepared_forms[1]["handoff"]["source_snapshot_hash"]
    )
    assert (
        first_operations
        == second_operations
        == ["poll_execution_status", "fetch_evaluation_result"]
    )


@pytest.mark.parametrize("outcome", ["compliant", "non_compliant"])
@pytest.mark.parametrize(
    "origin",
    [None, "http://traveler-portal.example", "https://traveler-portal.example/unaccepted-path"],
    ids=["not-configured", "insecure-origin", "not-an-origin"],
)
def test_first_production_handoff_recovers_from_configuration_failure(
    tpp_client: TestClient,
    submitted_trip: str,
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
    origin: str | None,
) -> None:
    operations = _install_verdict_transport(monkeypatch, outcome)
    refreshed = tpp_client.post(f"/api/workspace/{submitted_trip}/proposal/refresh")
    assert refreshed.status_code == 200
    before = refreshed.json()
    metadata = before["proposal_state"]["portal_handoff"]
    assert metadata["status"] == "eligible"
    assert metadata["prepared_at"] is None

    # Preparation must use the saved result even when the policy API is unavailable.
    def unavailable(*args, **kwargs):
        pytest.fail("Configuration recovery must not repeat the saved policy check")

    for operation in (
        "fetch_policy_constraints",
        "submit_proposal",
        "poll_execution_status",
        "fetch_evaluation_result",
    ):
        monkeypatch.setattr(HTTPTPPIntegrationClient, operation, unavailable)
    monkeypatch.setenv("TRIP_PLANNER_ENV", "production")
    monkeypatch.delenv("TPP_BASE_URL", raising=False)
    monkeypatch.delenv("TPP_PORTAL_BASE_URL", raising=False)
    if origin is not None:
        monkeypatch.setenv("TPP_PORTAL_BASE_URL", origin)

    path = f"/api/workspace/{submitted_trip}/proposal/handoff"
    failed = tpp_client.post(path, json={})
    assert failed.status_code == 503
    assert failed.json()["detail"].startswith("The approver portal handoff is not configured.")
    assert tpp_client.get(f"/api/workspace/{submitted_trip}/proposal").json() == before

    monkeypatch.setenv("TPP_PORTAL_BASE_URL", "https://traveler-portal.example:8443/")
    retried = tpp_client.post(path, json={})
    assert retried.status_code == 200
    assert retried.headers["cache-control"] == "no-store"
    payload = retried.json()
    assert payload["action_url"] == "https://traveler-portal.example:8443/portal/handoff"
    assert payload["method"] == "POST"
    assert payload["fields"]["traveler_name"] == "Dana Chen"
    assert "USD 612.00" in payload["fields"]["notes"]
    assert f"status={outcome}" in payload["fields"]["notes"]
    assert payload["handoff"]["source_snapshot_hash"] == metadata["source_snapshot_hash"]
    assert payload["handoff"]["status"] == "prepared"
    assert payload["handoff"]["prepared_at"] is not None
    assert payload["handoff"]["manager_submission_status"] == "unknown"
    assert payload["handoff"]["manager_decision"] is None
    assert "source_snapshot" not in payload["handoff"]

    reloaded = tpp_client.get(f"/api/workspace/{submitted_trip}/proposal").json()
    assert reloaded["proposal_state"]["portal_handoff"] == payload["handoff"]
    assert reloaded["proposal_state"]["evaluation"] == before["proposal_state"]["evaluation"]
    assert operations == ["poll_execution_status", "fetch_evaluation_result"]
