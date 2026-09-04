import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal
from urllib import error as urllib_error

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.app.routes import errors as route_errors
from trip_planner.app.routes import policy as policy_routes
from trip_planner.app.services.auth import AuthenticatedUser
from trip_planner.app.services.policy import _tpp_trip_plan_payload
from trip_planner.integrations.tpp import TPPTransportError
from trip_planner.integrations.tpp import client as tpp_client_module
from trip_planner.persistence.db import get_session_factory, reset_database_state
from trip_planner.persistence.models.policy import PersistedPolicyState
from trip_planner.persistence.models.trip import PersistedTrip


def _fixture_path(name: str) -> Path:
    return (
        Path(__file__).resolve().parents[1] / "fixtures" / "integrations" / "tpp" / "policy" / name
    )


def _load_fixture(name: str) -> dict:
    return json.loads(_fixture_path(name).read_text(encoding="utf-8"))


def test_tpp_trip_plan_payload_falls_back_to_owner_profile_department() -> None:
    record = PersistedTrip(
        trip_id="trip-leisure-1",
        user_id="user-1",
        title="Leisure policy sync",
        summary="Check fallback department.",
        mode="leisure",
        start_date="2026-05-04",
        end_date="2026-05-06",
        duration_days=3,
        primary_regions=["Chicago"],
        leisure_profile_id="profile:trip-leisure-1:leisure",
        business_profile_id=None,
    )
    user = AuthenticatedUser(
        user_id="user-1",
        email="owner@example.test",
        display_name="Policy Owner",
    )

    payload = _tpp_trip_plan_payload(record, user=user)

    assert payload["department"] == "profile:trip-leisure-1:leisure"


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
    captured_requests: list[dict[str, Any]] | None = None,
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


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'policy.db'}")
    reset_database_state()
    app = create_app()

    with TestClient(app) as test_client:
        test_client.post(
            "/api/auth/signup",
            json={
                "email": "policy@example.com",
                "password": "password123",
                "display_name": "Policy Owner",
            },
        )
        yield test_client

    reset_database_state()


def test_workspace_policy_import_persists_constraint_set_and_readiness(client: TestClient) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Client policy sync",
            "summary": "Import policy inputs for the workspace.",
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
    fixture = _load_fixture("standard_policy_sync.json")

    imported = client.put(
        f"/api/workspace/{trip_id}/policy",
        json={
            "request": fixture["request"],
            "response": fixture["response"],
            "source_kind": "tpp_sync",
            "tags": ["business-policy"],
            "notes": ["Imported from TPP fixture for workspace readiness."],
        },
    )

    assert imported.status_code == 200
    payload = imported.json()
    assert payload["policy_state"]["trip_id"] == trip_id
    assert payload["policy_state"]["policy_id"] == "policy-standard-2026-02"
    assert payload["summary"]["required_booking_channels"] == ["Navan", "Concur"]
    assert payload["summary"]["policy_status"] == "pass"
    assert payload["summary"]["booking_requirements"][0]["code"] == "approved_booking_channel"
    assert payload["policy_evaluation"]["status"] == "compliant"
    assert payload["proposal"]["constraint_set_id"] == "policy-standard-2026-02"

    reloaded = client.get(f"/api/workspace/{trip_id}/policy")
    assert reloaded.status_code == 200
    reloaded_payload = reloaded.json()
    assert reloaded_payload["policy_state"]["policy_state_id"] == f"policy-state:{trip_id}"
    assert "Persisted policy storage is limited" in reloaded_payload["policy_state"]["notes"][-2]


def test_workspace_policy_import_maps_tpp_failure_to_blocking_reasons(client: TestClient) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Denied policy import",
            "summary": "Keep TPP denial reasons visible in the workspace.",
            "mode": "business",
            "trip_frame": {"duration_days": 2, "primary_regions": ["Chicago"]},
        },
    )
    trip_id = created.json()["trip"]["trip_id"]
    fixture = _load_fixture("standard_policy_sync.json")
    context = fixture["response"]["result_payload"]["organization_context"]
    context["policy_status"] = "fail"
    context["blocking_issues"] = [
        {
            "code": "BUD-001",
            "summary": "Trip cost exceeds the approved budget cap.",
            "severity": "blocking",
        }
    ]

    imported = client.put(
        f"/api/workspace/{trip_id}/policy",
        json={"request": fixture["request"], "response": fixture["response"]},
    )

    assert imported.status_code == 200
    evaluation = imported.json()["policy_evaluation"]
    assert evaluation["status"] == "non_compliant"
    assert evaluation["failure_reasons"][0] == {
        "code": "BUD-001",
        "message": "Trip cost exceeds the approved budget cap.",
        "severity": "blocking",
        "related_category": "policy_sync",
    }


def test_workspace_policy_reload_treats_blocking_issues_without_pass_status_as_non_compliant(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Incomplete stored policy verdict",
            "summary": "Do not treat an incomplete persisted policy as compliant.",
            "mode": "business",
            "trip_frame": {"duration_days": 2, "primary_regions": ["Chicago"]},
        },
    )
    trip_id = created.json()["trip"]["trip_id"]
    fixture = _load_fixture("standard_policy_sync.json")
    imported = client.put(
        f"/api/workspace/{trip_id}/policy",
        json={"request": fixture["request"], "response": fixture["response"]},
    )
    assert imported.status_code == 200

    with get_session_factory()() as db_session:
        state = db_session.get(PersistedPolicyState, f"policy-state:{trip_id}")
        assert state is not None
        state.organization_context = {
            **state.organization_context,
            "blocking_issues": [
                {
                    "code": "BUD-001",
                    "summary": "Trip cost exceeds the approved budget cap.",
                    "severity": "blocking",
                }
            ],
        }
        state.organization_context.pop("policy_status")
        db_session.commit()

    reloaded = client.get(f"/api/workspace/{trip_id}/policy")

    assert reloaded.status_code == 200
    payload = reloaded.json()
    assert payload["policy_evaluation"]["status"] == "policy_unavailable"
    assert payload["summary"]["status"] == "policy_state_invalid"
    assert "policy_status must be one of" in payload["summary"]["validation_error"]


def test_workspace_policy_invalid_persisted_blocking_issue_is_unavailable(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Invalid stored policy",
            "summary": "Keep malformed persisted policy details visible.",
            "mode": "business",
            "trip_frame": {"duration_days": 2, "primary_regions": ["Chicago"]},
        },
    )
    trip_id = created.json()["trip"]["trip_id"]
    fixture = _load_fixture("standard_policy_sync.json")
    imported = client.put(
        f"/api/workspace/{trip_id}/policy",
        json={"request": fixture["request"], "response": fixture["response"]},
    )
    assert imported.status_code == 200

    with get_session_factory()() as db_session:
        state = db_session.get(PersistedPolicyState, f"policy-state:{trip_id}")
        assert state is not None
        state.organization_context = {
            **state.organization_context,
            "blocking_issues": [
                {
                    "code": "BUD-001",
                    "summary": "Malformed persisted severity should remain visible.",
                    "severity": "critical",
                }
            ],
        }
        db_session.commit()

    response = client.get(f"/api/workspace/{trip_id}/policy")

    assert response.status_code == 200
    payload = response.json()
    assert payload["policy_evaluation"]["status"] == "policy_unavailable"
    assert payload["policy_evaluation"]["failure_reasons"] == [
        {
            "code": "invalid_persisted_policy_state",
            "message": (
                "Stored TPP policy requirements are invalid and cannot be used for compliance "
                "evaluation: organization_context.blocking_issues[0] is invalid: severity must be "
                "'warning' or 'blocking'"
            ),
            "severity": "blocking",
            "related_category": "policy_sync",
        }
    ]
    assert payload["summary"]["status"] == "policy_state_invalid"


@pytest.mark.parametrize(
    ("field", "value", "expected_error"),
    [
        (
            "blocking_issues",
            False,
            "organization_context.blocking_issues must be provided as a list",
        ),
        (
            "compatible_with_planner_cache",
            "false",
            "compatible_with_planner_cache must be a boolean",
        ),
    ],
)
def test_workspace_policy_invalid_persisted_context_is_unavailable(
    client: TestClient, field: str, value: object, expected_error: str
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Invalid stored policy context",
            "summary": "Reject malformed persisted policy fields.",
            "mode": "business",
            "trip_frame": {"duration_days": 2, "primary_regions": ["Chicago"]},
        },
    )
    trip_id = created.json()["trip"]["trip_id"]
    fixture = _load_fixture("standard_policy_sync.json")
    imported = client.put(
        f"/api/workspace/{trip_id}/policy",
        json={"request": fixture["request"], "response": fixture["response"]},
    )
    assert imported.status_code == 200

    with get_session_factory()() as db_session:
        state = db_session.get(PersistedPolicyState, f"policy-state:{trip_id}")
        assert state is not None
        state.organization_context = {**state.organization_context, field: value}
        db_session.commit()

    response = client.get(f"/api/workspace/{trip_id}/policy")

    assert response.status_code == 200
    payload = response.json()
    assert payload["policy_evaluation"]["status"] == "policy_unavailable"
    assert payload["summary"]["validation_error"] == expected_error


def test_workspace_policy_import_preserves_cached_state_when_tpp_rejects_cache(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Cache compatibility import",
            "summary": "Do not replace a policy cache with an incompatible snapshot.",
            "mode": "business",
            "trip_frame": {"duration_days": 2, "primary_regions": ["Chicago"]},
        },
    )
    trip_id = created.json()["trip"]["trip_id"]
    fixture = _load_fixture("standard_policy_sync.json")
    seeded = client.put(
        f"/api/workspace/{trip_id}/policy",
        json={"request": fixture["request"], "response": fixture["response"]},
    )
    assert seeded.status_code == 200
    fixture["response"]["result_payload"]["constraint_set"]["policy_id"] = "policy-new"
    fixture["response"]["result_payload"]["organization_context"][
        "compatible_with_planner_cache"
    ] = False

    incompatible = client.put(
        f"/api/workspace/{trip_id}/policy",
        json={"request": fixture["request"], "response": fixture["response"]},
    )

    assert incompatible.status_code == 200
    payload = incompatible.json()
    assert payload["policy_state"]["policy_id"] == "policy-standard-2026-02"
    assert payload["summary"]["status"] == "cache_incompatible"
    assert payload["policy_evaluation"]["status"] == "policy_unavailable"


def test_workspace_policy_import_rejects_leisure_trip(client: TestClient) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Leisure trip",
            "summary": "Should not accept policy imports.",
            "mode": "leisure",
            "trip_frame": {"duration_days": 2, "primary_regions": ["Kyoto"]},
        },
    )
    trip_id = created.json()["trip"]["trip_id"]
    fixture = _load_fixture("standard_policy_sync.json")

    response = client.put(
        f"/api/workspace/{trip_id}/policy",
        json={
            "request": fixture["request"],
            "response": fixture["response"],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"].startswith("The workspace policy request was invalid.")


def test_workspace_policy_import_uses_live_tpp_transport_when_response_is_omitted(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TPP_BASE_URL", "https://tpp.example.test")
    monkeypatch.setenv("TPP_ACCESS_TOKEN", "token-123")
    monkeypatch.setenv("TPP_OIDC_PROVIDER", "okta")
    captured_requests: list[dict[str, Any]] = []
    _install_fake_http(
        monkeypatch,
        [
            _FakeHTTPResponse(
                200,
                {
                    "trip_id": "placeholder",
                    "freshness": "current",
                    "generated_at": "2026-04-11T05:05:00Z",
                    "expires_at": "2026-04-12T05:05:00Z",
                    "invalidated_at": None,
                    "invalidation_reason": None,
                    "policy_status": "pass",
                    "booking_requirements": [],
                    "documentation_rules": [
                        {
                            "code": "fare_evidence",
                            "summary": "Attach fare evidence before approval.",
                            "severity": "error",
                        }
                    ],
                    "approval_triggers": [
                        {
                            "code": "manager_review",
                            "summary": "Manager review is required.",
                            "blocking": True,
                            "source": "policy_rule",
                        }
                    ],
                    "auth": {
                        "endpoint": "GET /api/planner/policy-snapshot",
                        "required_permission": "view",
                        "auth_scheme": "Bearer token",
                        "supported_sso": ["okta"],
                    },
                    "versioning": {
                        "contract_version": "2026-04-11",
                        "policy_version": "d7a6d25a",
                        "planner_known_policy_version": None,
                        "compatible_with_planner_cache": True,
                        "etag": "trip:policy:d7a6d25a",
                    },
                },
            )
        ],
        captured_requests=captured_requests,
    )

    created = client.post(
        "/api/trips",
        json={
            "title": "Live policy sync",
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
    fixture = _load_fixture("standard_policy_sync.json")
    fixture["request"]["trip_id"] = trip_id

    imported = client.put(
        f"/api/workspace/{trip_id}/policy",
        json={
            "request": fixture["request"],
            "source_kind": "tpp_sync",
            "tags": ["live-http"],
            "notes": ["Fetched through the live TPP client."],
        },
    )

    assert imported.status_code == 200
    payload = imported.json()
    assert payload["policy_state"]["policy_version"] == "d7a6d25a"
    assert payload["summary"]["documentation_rules"] == ["fare_evidence"]
    assert payload["summary"]["approval_triggers"] == ["manager_review"]
    assert (
        captured_requests[0]["full_url"] == "https://tpp.example.test/api/planner/policy-snapshot"
    )
    assert captured_requests[0]["method"] == "GET"
    assert captured_requests[0]["body"]["request"] == {
        "trip_id": trip_id,
        "requested_at": "2026-02-15T12:00:00Z",
    }
    assert captured_requests[0]["body"]["trip_plan"] == {
        "trip_id": trip_id,
        "traveler_name": "Policy Owner",
        "traveler_role": "business traveler",
        "department": f"profile:{trip_id}:business",
        "destination": "Chicago",
        "destination_city": "Chicago",
        "departure_date": "2026-05-04",
        "return_date": "2026-05-06",
        "purpose": "Use runtime TPP HTTP transport.",
        "transportation_mode": "mixed",
        "expected_costs": {},
        "estimated_cost": 0,
        "status": "draft",
        "expense_breakdown": {},
        "selected_providers": {},
        "validation_results": [],
        "approval_history": [],
        "exception_requests": [],
    }


def test_workspace_policy_import_surfaces_live_tpp_unavailable_errors(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TPP_BASE_URL", "https://tpp.example.test")
    monkeypatch.setenv("TPP_ACCESS_TOKEN", "token-123")
    monkeypatch.setenv("TPP_OIDC_PROVIDER", "okta")
    monkeypatch.setenv("TPP_TRANSPORT_MAX_ATTEMPTS", "1")
    _install_fake_http(
        monkeypatch,
        [
            urllib_error.URLError("connection refused"),
        ],
    )

    created = client.post(
        "/api/trips",
        json={
            "title": "Unavailable policy sync",
            "summary": "Surface live TPP transport failures.",
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
    fixture = _load_fixture("standard_policy_sync.json")
    fixture["request"]["trip_id"] = trip_id

    response = client.put(
        f"/api/workspace/{trip_id}/policy",
        json={"request": fixture["request"]},
    )

    assert response.status_code == 503
    assert response.json()["detail"].startswith(
        "The policy service could not complete the request."
    )


def test_route_does_not_disclose_upstream_exception_text(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = "upstream-secret-7da6e2"
    reference_id = "a" * 32
    logged: dict[str, object] = {}

    def _capture_log(*args: object, **kwargs: object) -> None:
        logged["args"] = args
        logged["exc_info"] = kwargs["exc_info"]

    monkeypatch.setattr(route_errors.logger, "error", _capture_log)

    def _raise_transport_error(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TPPTransportError(sentinel, status_code=503, reference_id=reference_id)

    monkeypatch.setattr(
        policy_routes, "import_workspace_policy_constraints", _raise_transport_error
    )
    fixture = _load_fixture("standard_policy_sync.json")

    response = client.put(
        "/api/workspace/trip-secret/policy",
        json={"request": fixture["request"], "response": fixture["response"]},
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert sentinel not in response.text
    match = re.search(r"Reference ID: ([0-9a-f]{32}).", detail)
    assert match is not None
    assert str(logged["exc_info"]) == sentinel
    logged_args = logged["args"]
    assert isinstance(logged_args, tuple)
    assert match.group(1) == reference_id
    assert reference_id in logged_args


def test_workspace_policy_import_uses_stored_policy_fallback_on_live_timeout(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TPP_BASE_URL", "https://tpp.example.test")
    monkeypatch.setenv("TPP_ACCESS_TOKEN", "token-123")
    monkeypatch.setenv("TPP_OIDC_PROVIDER", "okta")
    monkeypatch.setenv("TPP_TRANSPORT_MAX_ATTEMPTS", "1")

    created = client.post(
        "/api/trips",
        json={
            "title": "Fallback policy sync",
            "summary": "Render stored policy posture if live TPP times out.",
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
    fixture = _load_fixture("standard_policy_sync.json")
    fixture["request"]["trip_id"] = trip_id

    seeded = client.put(
        f"/api/workspace/{trip_id}/policy",
        json={
            "request": fixture["request"],
            "response": fixture["response"],
            "source_kind": "tpp_sync",
            "tags": ["stored-policy"],
            "notes": ["Seed stored policy posture before live retry."],
        },
    )
    assert seeded.status_code == 200

    _install_fake_http(monkeypatch, [TimeoutError("read timed out")])

    fallback = client.put(
        f"/api/workspace/{trip_id}/policy",
        json={
            "request": fixture["request"],
            "source_kind": "tpp_sync",
            "tags": ["live-retry"],
            "notes": ["Retry live TPP transport."],
        },
    )

    assert fallback.status_code == 200
    payload = fallback.json()
    assert payload["policy_state"]["policy_id"] == "policy-standard-2026-02"
    assert payload["summary"]["status"] == "stored_policy_fallback"
    assert payload["summary"]["transport_error"]["error_code"] == "timeout"
    assert payload["summary"]["transport_error"]["status_code"] == 504
    assert payload["summary"]["transport_error"]["retryable"] is True
    assert "timed out" in payload["summary"]["transport_error"]["message"]
    assert payload["summary"]["transport_error"]["source"] == "workspace_policy_sync"
    assert "stored-policy posture" in payload["summary"]["fallback_reason"]


def test_workspace_policy_import_uses_stored_policy_fallback_on_breaker_open(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TPP_BASE_URL", "https://tpp.example.test")
    monkeypatch.setenv("TPP_ACCESS_TOKEN", "token-123")
    monkeypatch.setenv("TPP_OIDC_PROVIDER", "okta")
    monkeypatch.setenv("TPP_TRANSPORT_MAX_ATTEMPTS", "1")
    monkeypatch.setenv("TPP_TRANSPORT_BREAKER_FAILURE_THRESHOLD", "1")
    monkeypatch.setenv("TPP_TRANSPORT_BREAKER_RESET_SECONDS", "60")

    created = client.post(
        "/api/trips",
        json={
            "title": "Breaker fallback policy sync",
            "summary": "Render stored policy posture if live TPP breaker is open.",
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
    fixture = _load_fixture("standard_policy_sync.json")
    fixture["request"]["trip_id"] = trip_id

    seeded = client.put(
        f"/api/workspace/{trip_id}/policy",
        json={
            "request": fixture["request"],
            "response": fixture["response"],
            "source_kind": "tpp_sync",
            "tags": ["stored-policy"],
            "notes": ["Seed stored policy posture before live retry."],
        },
    )
    assert seeded.status_code == 200

    _install_fake_http(monkeypatch, [urllib_error.URLError(ConnectionRefusedError("down"))])
    failed = client.put(
        f"/api/workspace/{trip_id}/policy",
        json={
            "request": fixture["request"],
            "source_kind": "tpp_sync",
            "tags": ["live-retry"],
            "notes": ["Open the breaker with a live TPP transport failure."],
        },
    )
    assert failed.status_code == 503

    fallback = client.put(
        f"/api/workspace/{trip_id}/policy",
        json={
            "request": fixture["request"],
            "source_kind": "tpp_sync",
            "tags": ["live-retry"],
            "notes": ["Retry after the breaker opens."],
        },
    )

    assert fallback.status_code == 200
    payload = fallback.json()
    assert payload["policy_state"]["policy_id"] == "policy-standard-2026-02"
    assert payload["summary"]["status"] == "stored_policy_fallback"
    assert payload["summary"]["transport_error"]["error_code"] == "breaker_open"
    assert payload["summary"]["transport_error"]["status_code"] == 503
    assert payload["summary"]["transport_error"]["retryable"] is True
    assert "circuit breaker is open" in payload["summary"]["transport_error"]["message"]
    assert payload["summary"]["transport_error"]["source"] == "workspace_policy_sync"
    assert "stored-policy posture" in payload["summary"]["fallback_reason"]
