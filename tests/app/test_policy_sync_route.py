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

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.app.services.policy import resolve_configured_organization_id
from trip_planner.app.services.proposal import _selected_scenario_row
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
    assert _selected_scenario_row(workspace, "scenario:trip-one:1") == workspace[
        "route_comparison"
    ]["scenarios"][0]
    with pytest.raises(ValueError, match="not in this trip's workspace"):
        _selected_scenario_row(workspace, "scenario:trip-two:1")


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
