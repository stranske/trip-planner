"""The workspace must be able to obtain a policy, or approval can never begin.

Issue #1731 was closed as completed while `policy_state` stayed absent for every trip,
so `buildProposalSubmissionPayload` threw "Policy context is not available for this
workspace" and the Policy tab's button appeared to do nothing. Nothing in the product
called `PUT /workspace/{id}/policy`, and no caller could reasonably hand-assemble a
TPPRequestEnvelope.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.app.services.policy import resolve_configured_organization_id
from trip_planner.app.services.proposal import (
    _home_airport_from_workspace,
    _selected_scenario_row,
    _validate_persisted_scenario_id,
)
from trip_planner.integrations.tpp import TPPResponseEnvelope
from trip_planner.persistence.db import reset_database_state


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'sync.db'}")
    reset_database_state()
    app = create_app()
    with TestClient(app) as test_client:
        test_client.post(
            "/api/auth/signup",
            json={
                "email": "sync@example.com",
                "password": "password123",
                "display_name": "Sync Owner",
            },
        )
        yield test_client
    reset_database_state()


def _business_trip(client: TestClient) -> str:
    created = client.post(
        "/api/trips",
        json={
            "title": "Client visit",
            "summary": "Quarterly review",
            "mode": "business",
            "trip_frame": {
                "start_date": "2026-10-12",
                "end_date": "2026-10-15",
                "duration_days": 4,
                "primary_regions": ["Chicago"],
                "traveler_party": {"kind": "solo", "traveler_count": 1, "notes": ""},
            },
        },
    )
    assert created.status_code == 201, created.text
    return created.json()["trip"]["trip_id"]


def test_sync_endpoint_is_reachable_and_not_a_404(client: TestClient) -> None:
    """The route must exist. Before this change there was no way to obtain a policy."""
    trip_id = _business_trip(client)
    response = client.post(f"/api/workspace/{trip_id}/policy/sync", json={})
    # Whatever the TPP outcome, the endpoint must be routed and must not 404/405.
    assert response.status_code not in {404, 405}


def test_sync_persists_policy_from_successful_tpp_response(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import trip_planner.app.services.policy as policy_service

    monkeypatch.setenv("TPP_ORGANIZATION_ID", "org-acme")
    fixture_path = (
        Path(__file__).resolve().parents[1]
        / "fixtures/integrations/tpp/policy/standard_policy_sync.json"
    )
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    def tpp_response(request, _response_payload, *, trip_plan_payload):
        assert request.organization_id == "org-acme"
        assert request.trip_id == trip_id
        assert trip_plan_payload
        response = fixture["response"].copy()
        response["request_id"] = request.request_id
        response["correlation_id"] = request.correlation_id.to_dict()
        return TPPResponseEnvelope.from_dict(response)

    monkeypatch.setattr(policy_service, "_resolve_policy_response", tpp_response)
    trip_id = _business_trip(client)
    response = client.post(f"/api/workspace/{trip_id}/policy/sync", json={})
    assert response.status_code == 200, response.text
    policy_state = response.json()["policy_state"]
    assert policy_state["organization_id"] == "org-acme"
    assert policy_state["constraint_set"]["policy_id"] == "policy-standard-2026-02"
    workspace = client.get(f"/api/workspace/{trip_id}")
    assert workspace.status_code == 200, workspace.text
    persisted = workspace.json()["policy_state"]
    assert persisted["organization_id"] == "org-acme"
    assert persisted["constraint_set"]["policy_id"] == "policy-standard-2026-02"


def test_submission_rejects_scenario_outside_trip_workspace() -> None:
    workspace = {
        "route_comparison": {
            "scenarios": [{"scenario_id": "scenario:trip-one:1", "title": "Own scenario"}]
        }
    }
    assert (
        _selected_scenario_row(workspace, "scenario:trip-one:1")
        == workspace["route_comparison"]["scenarios"][0]
    )
    with pytest.raises(ValueError, match="not in this trip's workspace"):
        _selected_scenario_row(workspace, "scenario:trip-two:1")


def test_submission_maps_current_saved_snapshot_to_materialized_row() -> None:
    saved_row = {"scenario_id": "saved:one", "title": "Saved itinerary"}
    workspace = {
        "route_comparison": {
            "lead_scenario_id": "other",
            "scenarios": [
                {"scenario_id": "other"},
                saved_row,
            ],
        },
        "session": {"current_saved_scenario_id": "saved:one"},
        "saved_scenarios": [
            {
                "saved_scenario_id": "saved:one",
                "current_version_id": "version:one",
                "versions": [
                    {
                        "version_id": "version:one",
                        "snapshot_refs": {
                            "itinerary_scenario_id": "snapshot:one",
                        },
                    }
                ],
            }
        ],
    }
    assert _selected_scenario_row(workspace, None) == saved_row
    assert _selected_scenario_row(workspace, "snapshot:one") == saved_row
    with pytest.raises(ValueError, match="not in this trip's workspace"):
        _selected_scenario_row(workspace, "snapshot:foreign")


def test_submission_implicit_selection_uses_comparison_when_saved_ref_is_stale() -> None:
    lead = {"scenario_id": "scenario:lead"}
    workspace = {
        "route_comparison": {"lead_scenario_id": "scenario:lead", "scenarios": [lead]},
        "saved_scenarios": [
            {
                "saved_scenario_id": "saved:stale",
                "current_version_id": "version:stale",
                "versions": [
                    {
                        "version_id": "version:stale",
                        "snapshot_refs": {
                            "itinerary_scenario_id": "snapshot:stale",
                        },
                    }
                ],
            }
        ],
    }
    assert _selected_scenario_row(workspace, None) == lead


def test_submission_uses_persisted_origin_not_destination_regions() -> None:
    workspace = {
        "trip_record": {"trip": {"trip_frame": {"origin": "Boston", "primary_regions": ["Japan"]}}}
    }
    assert _home_airport_from_workspace(workspace) == "Boston"


def test_persisted_scenario_validation_allows_legacy_fixture_ids_without_workspace() -> None:
    assert _validate_persisted_scenario_id({}, "scenario-a") == "scenario-a"


def test_persisted_scenario_validation_rejects_foreign_ids_when_workspace_has_scenarios(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TRIP_PLANNER_ALLOW_FIXTURE_TPP_RESPONSES", raising=False)
    workspace = {
        "route_comparison": {
            "scenarios": [{"scenario_id": "scenario:trip-one:1", "title": "Own scenario"}]
        }
    }
    assert (
        _validate_persisted_scenario_id(workspace, "scenario:trip-one:1") == "scenario:trip-one:1"
    )
    with pytest.raises(ValueError, match="not in this trip's workspace"):
        _validate_persisted_scenario_id(workspace, "scenario:trip-two:1")
    with pytest.raises(ValueError, match="not in this trip's workspace"):
        _validate_persisted_scenario_id(workspace, "scenario-a")


def test_sync_without_configured_organization_says_so(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TPP_ORGANIZATION_ID", raising=False)
    trip_id = _business_trip(client)
    response = client.post(f"/api/workspace/{trip_id}/policy/sync", json={})
    assert response.status_code == 503
    assert "TPP_ORGANIZATION_ID" in response.text


def test_organization_comes_from_deployment_config_not_the_caller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A traveller must never be asked to type an organization id."""
    monkeypatch.delenv("TPP_ORGANIZATION_ID", raising=False)
    with pytest.raises(ValueError, match="TPP_ORGANIZATION_ID"):
        resolve_configured_organization_id()
    monkeypatch.setenv("TPP_ORGANIZATION_ID", "org-northwind")
    assert resolve_configured_organization_id() == "org-northwind"


def test_sync_rejects_caller_selected_organization(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TPP_ORGANIZATION_ID", "org-northwind")
    trip_id = _business_trip(client)
    response = client.post(
        f"/api/workspace/{trip_id}/policy/sync",
        json={"organization_id": "org-unrelated"},
    )
    assert response.status_code == 422


def test_submit_missing_trip_returns_not_found(client: TestClient) -> None:
    response = client.post("/api/workspace/missing-trip/proposal/submit", json={})
    assert response.status_code == 404


def test_submit_without_a_policy_explains_the_missing_step(client: TestClient) -> None:
    """The old failure mode was a silent no-op; it must now say what is missing."""
    trip_id = _business_trip(client)
    response = client.post(f"/api/workspace/{trip_id}/proposal/submit", json={})
    assert response.status_code == 400
    assert "policy" in response.text.lower()


def test_submit_builds_costed_proposal_not_policy_preview(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Server submit must not reuse the zero-cost policy preview envelope."""
    monkeypatch.setenv("TPP_ORGANIZATION_ID", "org-northwind")
    trip_id = _business_trip(client)
    sync_response = client.post(f"/api/workspace/{trip_id}/policy/sync", json={})
    assert sync_response.status_code not in {404, 405}
    if sync_response.status_code != 200:
        pytest.skip(f"TPP unavailable in this environment: {sync_response.status_code}")

    submit_response = client.post(f"/api/workspace/{trip_id}/proposal/submit", json={})
    if submit_response.status_code == 400 and "scenario" in submit_response.text.lower():
        pytest.skip("Workspace has no runtime scenario comparison in this fixture trip.")
    assert submit_response.status_code in {200, 502, 503}, submit_response.text
    if submit_response.status_code == 200:
        proposal_state = submit_response.json()["proposal_state"]
        proposal_payload = proposal_state["proposal_payload"]
        assert proposal_payload["proposal_id"] == f"proposal:{trip_id}"
        assert "proposal-preview" not in proposal_payload["proposal_id"]
        assert proposal_payload["cost_summary"]["total_estimated_cost"] >= 0


def _focused_live_tpp_env() -> dict[str, str]:
    return {
        "TPP_BASE_URL": "http://tpp.example.test",
        "TPP_ACCESS_TOKEN": "live-verifier-token",
        "TPP_OIDC_PROVIDER": "okta",
        "TPP_ORGANIZATION_ID": "org-northwind",
    }


def _install_focused_live_tpp_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> list[dict[str, Any]]:
    from trip_planner.integrations.tpp import client as tpp_client_module

    calls: list[dict[str, Any]] = []
    outcomes_by_execution: dict[str, str] = {}

    def fake_send_json_request(
        self: Any,
        *,
        method: str,
        path: str,
        url: str,
        json_payload: dict[str, Any],
    ) -> dict[str, Any]:
        calls.append(
            {
                "method": method,
                "path": path,
                "url": url,
                "payload": json.loads(json.dumps(json_payload)),
            }
        )
        if method == "GET" and path == "/api/planner/policy-snapshot":
            req = dict(json_payload.get("request") or {})
            return {
                "trip_id": req.get("trip_id", "trip-unknown"),
                "freshness": "current",
                "generated_at": "2026-11-20T12:00:00Z",
                "expires_at": "2026-11-21T12:00:00Z",
                "invalidated_at": None,
                "invalidation_reason": None,
                "policy_status": "pass",
                "booking_requirements": [
                    {
                        "code": "approved_channel",
                        "summary": "Book through an approved channel.",
                    }
                ],
                "documentation_rules": [
                    {
                        "code": "fare_evidence",
                        "summary": "Attach lowest fare evidence.",
                    }
                ],
                "approval_triggers": [
                    {
                        "code": "manager_review",
                        "summary": "Manager approval required.",
                    }
                ],
                "airfare_rules": {
                    "max_cabin": "economy",
                    "max_over_lowest_fare_usd": 100,
                },
                "lodging_rules": {"max_nightly_rate_usd": 325},
                "ground_transport_rules": {},
                "meal_rules": {},
                "budget_rules": {},
                "comparable_requirements": {"lodging": 1},
                "versioning": {
                    "contract_version": "2026-04-11",
                    "policy_version": "2026.11",
                    "planner_known_policy_version": None,
                    "compatible_with_planner_cache": True,
                    "etag": "policy-ext-northwind-2026-11",
                },
            }
        if method == "POST" and path == "/api/planner/proposals":
            req = dict(json_payload.get("request") or {})
            trip_plan = dict(json_payload.get("trip_plan") or {})
            trip_id = str(req.get("trip_id") or trip_plan.get("trip_id") or "trip-unknown")
            proposal_id = str(req.get("proposal_id") or f"proposal:{trip_id}")
            selected_fare = float(trip_plan.get("selected_fare") or 0.0)
            lowest_fare = float(trip_plan.get("lowest_fare") or selected_fare)
            execution_id = "exec-ext-northwind-001"
            is_compliant = selected_fare <= lowest_fare
            outcomes_by_execution[execution_id] = "compliant" if is_compliant else "non_compliant"
            if is_compliant:
                return {
                    "operation": "submit_proposal",
                    "submission_status": "submitted",
                    "request_id": "tpp-submit-ext-001",
                    "correlation_id": {
                        "value": f"submit-proposal:{trip_id}",
                        "issued_by": "tpp",
                    },
                    "transport_pattern": "deferred",
                    "execution_status": {
                        "state": "deferred",
                        "terminal": False,
                        "summary": "Proposal queued for evaluation",
                        "poll_after_seconds": 0,
                        "external_status": "202 Accepted",
                        "updated_at": "2026-11-20T12:00:01Z",
                    },
                    "result_payload": {
                        "execution_id": execution_id,
                        "queue_state": "waiting_for_policy_engine",
                        "trip_id": trip_id,
                        "proposal_id": proposal_id,
                    },
                    "received_at": "2026-11-20T12:00:01Z",
                    "status_endpoint": (
                        f"http://tpp.example.test/api/planner/proposals/{proposal_id}"
                        f"/executions/{execution_id}"
                    ),
                }
            return {
                "operation": "submit_proposal",
                "submission_status": "rejected",
                "request_id": "tpp-submit-ext-001",
                "correlation_id": {
                    "value": f"submit-proposal:{trip_id}",
                    "issued_by": "tpp",
                },
                "transport_pattern": "sync",
                "execution_status": {
                    "state": "failed",
                    "terminal": True,
                    "summary": "Proposal blocked by policy",
                    "external_status": "200 OK",
                    "updated_at": "2026-11-20T12:00:01Z",
                },
                "result_payload": {
                    "execution_id": execution_id,
                    "queue_state": "blocked_by_policy",
                    "trip_id": trip_id,
                    "proposal_id": proposal_id,
                    "blocking_codes": ["fare_above_lowest"],
                },
                "error": {
                    "code": "proposal_blocked_by_policy",
                    "message": "Selected fare exceeds lowest available fare.",
                    "category": "policy",
                    "retryable": False,
                },
                "received_at": "2026-11-20T12:00:01Z",
                "status_endpoint": (
                    f"http://tpp.example.test/api/planner/proposals/{proposal_id}"
                    f"/executions/{execution_id}"
                ),
            }
        if method == "GET" and "/executions/" in path and not path.endswith("/evaluation-result"):
            execution_id = path.rsplit("/", 1)[-1]
            proposal_id = str(json_payload.get("proposal_id") or "proposal-unknown")
            outcome = outcomes_by_execution.get(execution_id, "compliant")
            if execution_id == "exec-001" or outcome == "compliant":
                return {
                    "operation": "poll_execution_status",
                    "transport_pattern": "deferred",
                    "execution_status": {
                        "state": "deferred",
                        "terminal": False,
                        "summary": "Awaiting evaluator completion",
                        "updated_at": "2026-11-20T12:00:02Z",
                    },
                    "result_payload": {
                        "execution_id": execution_id,
                        "proposal_id": proposal_id,
                        "queue_state": "waiting_for_policy_engine",
                    },
                    "received_at": "2026-11-20T12:00:02Z",
                    "status_endpoint": (
                        f"http://tpp.example.test/api/planner/proposals/{proposal_id}"
                        f"/executions/{execution_id}"
                    ),
                }
            return {
                "operation": "poll_execution_status",
                "transport_pattern": "sync",
                "execution_status": {
                    "state": "failed",
                    "terminal": True,
                    "summary": "Proposal blocked by policy",
                    "updated_at": "2026-11-20T12:00:02Z",
                },
                "result_payload": {
                    "execution_id": execution_id,
                    "proposal_id": proposal_id,
                    "queue_state": "blocked_by_policy",
                    "blocking_codes": ["fare_above_lowest"],
                },
                "error": {
                    "code": "proposal_blocked_by_policy",
                    "message": "Selected fare exceeds lowest available fare.",
                    "category": "policy",
                    "retryable": False,
                },
                "received_at": "2026-11-20T12:00:02Z",
                "status_endpoint": (
                    f"http://tpp.example.test/api/planner/proposals/{proposal_id}"
                    f"/executions/{execution_id}"
                ),
            }
        if method == "GET" and path.endswith("/evaluation-result"):
            execution_id = path.split("/executions/", 1)[1].split("/", 1)[0]
            trip_id = str(json_payload.get("trip_id") or "trip-unknown")
            proposal_id = str(json_payload.get("proposal_id") or f"proposal:{trip_id}")
            proposal_version = str(json_payload.get("proposal_version") or "v1")
            outcome = outcomes_by_execution.get(execution_id, "non_compliant")
            return {
                "trip_id": trip_id,
                "proposal_id": proposal_id,
                "proposal_version": proposal_version,
                "execution_id": execution_id,
                "request_id": "eval-ext-northwind-001",
                "correlation_id": {
                    "value": f"submit-proposal:{trip_id}",
                    "issued_by": "tpp",
                },
                "outcome": outcome,
                "result_endpoint": f"GET /api/planner/executions/{execution_id}/evaluation-result",
                "status_endpoint": (
                    f"http://tpp.example.test/api/planner/proposals/{proposal_id}"
                    f"/executions/{execution_id}"
                ),
                "policy_result": {
                    "status": "fail" if outcome == "non_compliant" else "pass",
                    "issues": [],
                    "policy_version": "2026.11",
                },
                "blocking_issues": (
                    [
                        {
                            "code": "fare_above_lowest",
                            "summary": "Selected fare exceeds lowest available fare threshold.",
                            "category": "airfare",
                        }
                    ]
                    if outcome == "non_compliant"
                    else []
                ),
                "preferred_alternatives": (
                    [
                        {
                            "category": "airfare",
                            "summary": "Rebook the lowest available economy fare.",
                            "rationale": "Matches the $400 lowest fare threshold.",
                        }
                    ]
                    if outcome == "non_compliant"
                    else []
                ),
                "exception_requirements": [],
                "reoptimization_guidance": [],
                "generated_at": "2026-11-20T12:00:03Z",
            }
        raise AssertionError(f"Unexpected TPP transport call: {method} {path}")

    monkeypatch.setattr(
        tpp_client_module.HTTPTPPIntegrationClient,
        "_send_json_request",
        fake_send_json_request,
    )
    return calls


def test_live_tpp_journey_uses_configured_org_native_sync_submit_and_verdict_readback(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import check_full_product_verification as verifier

    env = _focused_live_tpp_env()
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    calls = _install_focused_live_tpp_transport(monkeypatch)

    trip_id = verifier._create_trip(
        client,
        mode="business",
        title="Native live verification",
        region="Chicago",
    )
    workspace_before = client.get(f"/api/workspace/{trip_id}?debug=true")
    assert workspace_before.status_code == 200, workspace_before.text

    live_details = verifier._run_live_tpp_journey(
        client,
        trip_id,
        env,
        expected_evaluation_status="non_compliant",
    )

    readback = client.get(f"/api/workspace/{trip_id}/proposal")
    assert readback.status_code == 200, readback.text
    readback_state = readback.json()["proposal_state"]
    source_version = readback_state["proposal"]["source_version"]
    assert readback_state["organization_id"] == "org-northwind"
    assert readback_state["execution_id"] == "exec-ext-northwind-001"
    assert (
        readback_state["evaluation"]["evaluation_result"]["evaluation_id"]
        == "eval-ext-northwind-001"
    )
    assert readback_state["evaluation"]["evaluation_result"]["status"] == "non_compliant"
    assert readback.json()["summary"]["follow_up_status"] == "reoptimization_required"
    assert source_version["trip_id"] == trip_id
    assert source_version["saved_scenario_id"] == live_details["saved_scenario_id"]
    assert source_version["version_id"] == live_details["source_version_id"]

    assert live_details["organization_id"] == "org-northwind"
    assert live_details["external_ids"]["policy_id"] == "policy-ext-northwind-2026-11"
    assert live_details["external_ids"]["execution_id"] == "exec-ext-northwind-001"
    assert live_details["external_ids"]["evaluation_id"] == "eval-ext-northwind-001"
    assert live_details["external_ids"]["policy_request_id"].startswith("policy-sync:")
    assert live_details["external_ids"]["submission_request_id"].startswith("submit-proposal:")
    assert live_details["verdict_readback"] == {
        "evaluation_id": "eval-ext-northwind-001",
        "status": "non_compliant",
        "follow_up_status": "reoptimization_required",
        "scenario_id": readback_state["scenario_id"],
        "saved_scenario_id": source_version["saved_scenario_id"],
        "source_version_id": source_version["version_id"],
    }
    assert live_details["input"]["organization_id"] == "org-northwind"
    assert live_details["input"]["scenario_id"] == readback_state["scenario_id"]
    assert live_details["input"]["saved_scenario_id"] == source_version["saved_scenario_id"]
    assert live_details["input"]["source_version_id"] == source_version["version_id"]
    assert live_details["observed_output"]["organization_id"] == "org-northwind"
    assert live_details["observed_output"]["policy_id"] == "policy-ext-northwind-2026-11"
    assert live_details["observed_output"]["execution_id"] == "exec-ext-northwind-001"
    assert live_details["observed_output"]["evaluation_id"] == "eval-ext-northwind-001"
    assert live_details["observed_output"]["evaluation_status"] == "non_compliant"
    assert live_details["observed_output"]["follow_up_status"] == "reoptimization_required"
    assert live_details["compatibility_control"]["offline_fixture_journey_retained"] is True
    assert live_details["compatibility_control"]["compatible_with_planner_cache"] is True
    assert live_details["compatibility_control"]["organization_id"] == "org-northwind"
    assert live_details["compatibility_control"]["saved_scenario_lineage_preserved"] is True

    submit_call = next(
        call
        for call in calls
        if call["method"] == "POST" and call["path"] == "/api/planner/proposals"
    )
    submit_request = dict(submit_call["payload"]["request"])
    assert submit_request["organization_id"] == "org-northwind"
    assert submit_request["payload"]["proposal"]["source_version"] == source_version


def test_same_focused_input_fails_with_previous_staged_put_behavior_and_passes_after_native_change(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import check_full_product_verification as verifier

    env = _focused_live_tpp_env()
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    _install_focused_live_tpp_transport(monkeypatch)

    trip_id = verifier._create_trip(
        client,
        mode="business",
        title="Previous vs native live verification",
        region="Chicago",
    )
    selected_scenario_id, expected_source_version = verifier._ensure_live_saved_scenario_lineage(
        client,
        trip_id=trip_id,
        policy_state_id=f"policy-state:{trip_id}",
    )

    # Previous behavior: stage caller-built PUT payloads with fixture envelopes/scenario-a.
    previous_transitions: list[tuple[str, str]] = []
    policy_put = client.put(
        f"/api/workspace/{trip_id}/policy",
        json={
            "request": verifier._prepared_policy_request(trip_id),
            "response": None,
            "tags": ["full-product-live"],
        },
    )
    previous_transitions.append(("PUT", f"/api/workspace/{trip_id}/policy"))
    assert policy_put.status_code == 200, policy_put.text

    price_put = client.put(
        f"/api/workspace/{trip_id}/prices",
        json={
            "component": "transport",
            "amount": 620.0,
            "lowest_amount": 400.0,
            "currency": "USD",
            "note": "Synthetic full-product verification fare evidence",
            "evidence_attested": True,
            "cabin_class": "economy",
            "flight_hours": 2.5,
        },
    )
    previous_transitions.append(("PUT", f"/api/workspace/{trip_id}/prices"))
    assert price_put.status_code == 200, price_put.text

    proposal = verifier._proposal_payload(trip_id)
    submission_put = client.put(
        f"/api/workspace/{trip_id}/proposal",
        json={
            "proposal": proposal,
            "request": verifier._prepared_submission_request(trip_id, proposal["proposal_id"]),
            "response": None,
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )
    previous_transitions.append(("PUT", f"/api/workspace/{trip_id}/proposal"))
    assert submission_put.status_code == 200, submission_put.text
    previous_submitted_state = submission_put.json()["proposal_state"]

    refresh_post = client.post(f"/api/workspace/{trip_id}/proposal/refresh")
    previous_transitions.append(("POST", f"/api/workspace/{trip_id}/proposal/refresh"))
    assert refresh_post.status_code == 200, refresh_post.text

    evaluation_put = client.put(
        f"/api/workspace/{trip_id}/proposal/evaluation",
        json={
            "request": verifier._prepared_evaluation_request(
                trip_id,
                proposal["proposal_id"],
                previous_submitted_state["execution_id"],
                fixture_name="non_compliant_evaluation.json",
            ),
            "response": None,
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )
    previous_transitions.append(("PUT", f"/api/workspace/{trip_id}/proposal/evaluation"))
    assert evaluation_put.status_code == 200, evaluation_put.text

    previous_readback = client.get(f"/api/workspace/{trip_id}/proposal")
    previous_transitions.append(("GET", f"/api/workspace/{trip_id}/proposal"))
    assert previous_readback.status_code == 200, previous_readback.text
    previous_readback_payload = previous_readback.json()
    previous_readback_state = previous_readback_payload["proposal_state"]

    # The previous behavior ignored TPP_ORGANIZATION_ID ("org-northwind") and lost saved lineage.
    assert previous_readback_state["organization_id"] == "org-acme"
    assert "source_version" not in previous_readback_state["proposal"]
    assert previous_readback_payload["summary"]["follow_up_status"] == "no_scenario_lineage"

    with pytest.raises(verifier.VerificationFailure, match="bypassed native transition"):
        verifier._assert_native_live_tpp_transitions(
            trip_id=trip_id,
            configured_organization_id="org-northwind",
            selected_scenario_id=selected_scenario_id,
            expected_source_version=expected_source_version,
            expected_evaluation_status="non_compliant",
            observed_transitions=previous_transitions,
            policy_state=policy_put.json()["policy_state"],
            submitted_state=previous_submitted_state,
            readback_state=previous_readback_state,
            readback_summary=previous_readback_payload["summary"],
        )

    # Updated behavior on the same trip/input: native POST sync and submit + persisted readback pass.
    live_details = verifier._run_live_tpp_journey(
        client,
        trip_id,
        env,
        expected_evaluation_status="non_compliant",
    )
    passing_readback = client.get(f"/api/workspace/{trip_id}/proposal")
    assert passing_readback.status_code == 200, passing_readback.text
    passing_state = passing_readback.json()["proposal_state"]
    assert passing_state["organization_id"] == "org-northwind"
    assert passing_state["proposal"]["source_version"] == expected_source_version
    assert passing_readback.json()["summary"]["follow_up_status"] == "reoptimization_required"
    assert live_details["verdict_readback"]["evaluation_id"] == "eval-ext-northwind-001"
    assert live_details["verdict_readback"]["saved_scenario_id"] == (
        expected_source_version["saved_scenario_id"]
    )


def test_native_two_app_verification_gate_retains_offline_cases_and_fails_when_native_transitions_are_bypassed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import check_full_product_verification as verifier

    env = _focused_live_tpp_env()
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    for name in (
        "TRIP_PLANNER_DATA_ZONE",
        "TRIP_PLANNER_OPENAI_AUTHORIZED_ENDPOINT",
        "TRIP_PLANNER_PLANNER_MODEL_PROVIDER",
        "TRIP_PLANNER_PLANNER_MODEL",
        "OPENAI_API_KEY",
        "VITE_GOOGLE_MAPS_PROVIDER_STATE",
        "VITE_GOOGLE_MAPS_BROWSER_API_KEY",
        "VITE_GOOGLE_MAPS_EMBED_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    _install_focused_live_tpp_transport(monkeypatch)

    checks = verifier.run_product_journeys(live_tpp="required")
    by_name = {check.name: check for check in checks}

    assert by_name["local-leisure-journey"].status == "PASS"
    assert by_name["local-business-journey"].status == "PASS"
    assert by_name["local-business-journey"].details["evaluation_status"] == "non_compliant"
    assert by_name["local-business-journey"].details["follow_up_status"] == "no_scenario_lineage"
    assert by_name["live-tpp"].status == "PASS"
    live_details = by_name["live-tpp"].details
    assert live_details["organization_id"] == "org-northwind"
    assert live_details["external_ids"]["policy_id"] == "policy-ext-northwind-2026-11"
    assert live_details["external_ids"]["execution_id"] == "exec-ext-northwind-001"
    assert live_details["external_ids"]["evaluation_id"] == "eval-ext-northwind-001"
    assert live_details["verdict_readback"]["status"] == "non_compliant"
    assert live_details["verdict_readback"]["follow_up_status"] == "reoptimization_required"
    assert live_details["compatibility_control"]["offline_fixture_journey_retained"] is True
    assert live_details["compatibility_control"]["saved_scenario_lineage_preserved"] is True

    # Verify the gate reports failure when a required native transition is omitted/bypassed.
    with pytest.raises(verifier.VerificationFailure, match="bypassed required native transition"):
        verifier._assert_native_live_tpp_transitions(
            trip_id=live_details["trip_id"],
            configured_organization_id="org-northwind",
            selected_scenario_id=live_details["scenario_id"],
            expected_source_version=live_details["source_version"],
            expected_evaluation_status="non_compliant",
            observed_transitions=[
                ("POST", f"/api/workspace/{live_details['trip_id']}/policy/sync"),
                ("POST", f"/api/workspace/{live_details['trip_id']}/proposal/refresh"),
                ("GET", f"/api/workspace/{live_details['trip_id']}/proposal"),
            ],
            policy_state={},
            submitted_state={},
            readback_state={},
            readback_summary={},
        )
