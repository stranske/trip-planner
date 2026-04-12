import json
from collections.abc import Iterator
from pathlib import Path
from urllib import error as urllib_error
import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.persistence.db import reset_database_state
from trip_planner.integrations.tpp import client as tpp_client_module


def _fixture_path(name: str) -> Path:
    return (
        Path(__file__).resolve().parents[1] / "fixtures" / "integrations" / "tpp" / "policy" / name
    )


def _load_fixture(name: str) -> dict:
    return json.loads(_fixture_path(name).read_text(encoding="utf-8"))


class _FakeHTTPResponse:
    def __init__(self, status_code: int, payload: dict[str, object]) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        del exc_type, exc, tb
        return False


def _install_fake_http(
    monkeypatch: pytest.MonkeyPatch,
    responses: list[_FakeHTTPResponse | Exception],
) -> None:
    queue = list(responses)

    def _fake_urlopen(request, timeout=0):
        del request, timeout
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
    assert payload["policy_evaluation"]["status"] == "compliant"
    assert payload["proposal"]["constraint_set_id"] == "policy-standard-2026-02"

    reloaded = client.get(f"/api/workspace/{trip_id}/policy")
    assert reloaded.status_code == 200
    reloaded_payload = reloaded.json()
    assert reloaded_payload["policy_state"]["policy_state_id"] == f"policy-state:{trip_id}"
    assert "Persisted policy storage is limited" in reloaded_payload["policy_state"]["notes"][-2]


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
    assert "business trips" in response.json()["detail"]


def test_workspace_policy_import_uses_live_tpp_transport_when_response_is_omitted(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TPP_BASE_URL", "https://tpp.example.test")
    monkeypatch.setenv("TPP_ACCESS_TOKEN", "token-123")
    monkeypatch.setenv("TPP_OIDC_PROVIDER", "okta")
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


def test_workspace_policy_import_surfaces_live_tpp_unavailable_errors(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TPP_BASE_URL", "https://tpp.example.test")
    monkeypatch.setenv("TPP_ACCESS_TOKEN", "token-123")
    monkeypatch.setenv("TPP_OIDC_PROVIDER", "okta")
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
    assert "failed" in response.json()["detail"]
