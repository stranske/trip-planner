"""The workspace must be able to obtain a policy, or approval can never begin.

Issue #1731 was closed as completed while `policy_state` stayed absent for every trip,
so `buildProposalSubmissionPayload` threw "Policy context is not available for this
workspace" and the Policy tab's button appeared to do nothing. Nothing in the product
called `PUT /workspace/{id}/policy`, and no caller could reasonably hand-assemble a
TPPRequestEnvelope.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.app.services.policy import resolve_configured_organization_id
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


def test_submit_without_a_policy_explains_the_missing_step(client: TestClient) -> None:
    """The old failure mode was a silent no-op; it must now say what is missing."""
    trip_id = _business_trip(client)
    response = client.post(f"/api/workspace/{trip_id}/proposal/submit", json={})
    assert response.status_code == 400
    assert "policy" in response.text.lower()
