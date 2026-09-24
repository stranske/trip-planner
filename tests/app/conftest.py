"""Shared fixtures for the app tests.

`tpp_client` is an app client whose TPP transport is intercepted: submissions are
captured in `TPP_SENT` and answered "queued", and a policy sync returns the standard
fixture. It lets a test create a real submission and verdict record without a live
policy service.
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.integrations.tpp import client as tpp_client_module
from trip_planner.integrations.tpp.contracts import TPPResponseEnvelope

from tests.app.tpp_intercept import TPP_SENT, _blocked_response
from trip_planner.persistence.db import ensure_database_ready, reset_database_state


@pytest.fixture
def tpp_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'payload.db'}")
    monkeypatch.setenv("TPP_BASE_URL", "http://tpp.invalid")
    monkeypatch.setenv("TPP_ACCESS_TOKEN", "test-token-long-enough")
    monkeypatch.setenv("TPP_ORGANIZATION_ID", "org-acme")
    monkeypatch.setenv("TPP_OIDC_PROVIDER", "okta")

    def capture(self: Any, request: Any) -> TPPResponseEnvelope:
        if request.operation == "submit_proposal":
            TPP_SENT.append(dict(request.payload.get("trip_plan") or {}))
        return _blocked_response(request)

    monkeypatch.setattr(tpp_client_module.HTTPTPPIntegrationClient, "submit_proposal", capture)

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
    TPP_SENT.clear()
    reset_database_state()
    ensure_database_ready()
    with TestClient(create_app()) as test_client:
        test_client.post(
            "/api/auth/signup",
            json={"email": "p@example.com", "password": "password123", "display_name": "Dana Chen"},
        )
        yield test_client
    reset_database_state()
