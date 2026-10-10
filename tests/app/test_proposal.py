import json
from collections.abc import Iterator
from pathlib import Path
from typing import Literal, cast

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.integrations.tpp import client as tpp_client_module
from trip_planner.persistence.db import get_session_factory, reset_database_state
from trip_planner.persistence.models.proposal import PersistedProposalState
from trip_planner.persistence.models.trip import PersistedTrip
from trip_planner.persistence.models.trip_price import PersistedTripPrice


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
    monkeypatch.setenv("TRIP_PLANNER_ALLOW_FIXTURE_TPP_RESPONSES", "true")
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


def test_workspace_proposal_submission_and_evaluation_persist(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TPP_PORTAL_BASE_URL", "https://tpp.example")
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
    priced = client.put(
        f"/api/workspace/{trip_id}/prices",
        json={
            "component": "transport",
            "amount": 620.0,
            "currency": "USD",
            "note": "United.com quote",
        },
    )
    assert priced.status_code == 200

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

    handoff = client.post(f"/api/workspace/{trip_id}/proposal/handoff", json={})
    assert handoff.status_code == 200
    assert handoff.json()["action_url"] == "https://tpp.example/portal/handoff"
    assert handoff.json()["method"] == "POST"
    assert handoff.json()["fields"]["traveler_name"] == "Proposal Owner"
    assert "destination_zip" not in handoff.json()["fields"]
    assert handoff.json()["handoff"]["status"] == "prepared"
    assert handoff.json()["handoff"]["manager_submission_status"] == "unknown"

    updated_price = client.put(
        f"/api/workspace/{trip_id}/prices",
        json={
            "component": "transport",
            "amount": 625.0,
            "currency": "USD",
            "note": "United.com updated quote",
        },
    )
    assert updated_price.status_code == 200
    stale = client.post(f"/api/workspace/{trip_id}/proposal/handoff", json={})
    assert stale.status_code == 409
    assert "Run the policy check again" in stale.json()["detail"]

    refreshed_evaluation = client.put(
        f"/api/workspace/{trip_id}/proposal/evaluation",
        json={
            "request": evaluation_fixture["request"],
            "response": evaluation_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )
    assert refreshed_evaluation.status_code == 200
    still_stale = client.post(f"/api/workspace/{trip_id}/proposal/handoff", json={})
    assert still_stale.status_code == 409
    assert "Run the policy check again" in still_stale.json()["detail"]

    reloaded = client.get(f"/api/workspace/{trip_id}/proposal")
    assert reloaded.status_code == 200
    reloaded_payload = reloaded.json()
    assert reloaded_payload["proposal_state"]["proposal"]["proposal_id"] == f"proposal:{trip_id}"
    assert (
        reloaded_payload["proposal_state"]["evaluation"]["evaluation_result"]["evaluation_id"]
        == "eval-approved-001"
    )
    assert reloaded_payload["proposal_state"]["portal_handoff"]["status"] == "eligible"
    assert "source_snapshot" not in reloaded_payload["proposal_state"]["portal_handoff"]


@pytest.fixture
def checked_handoff(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> tuple[str, dict, dict]:
    monkeypatch.setenv("TPP_PORTAL_BASE_URL", "https://tpp.example")
    created = client.post(
        "/api/trips",
        json={
            "title": "Freshness-bound handoff",
            "mode": "business",
            "trip_frame": {
                "origin": "ORD",
                "start_date": "2026-05-04",
                "end_date": "2026-05-06",
                "duration_days": 3,
                "primary_regions": ["Chicago"],
            },
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]
    assert (
        client.put(
            f"/api/workspace/{trip_id}/prices",
            json={"component": "transport", "amount": 620.0, "note": "United.com quote"},
        ).status_code
        == 200
    )

    submission_fixture = _load_fixture("proposal_submit_deferred.json")
    submission_fixture["request"]["trip_id"] = trip_id
    submission_fixture["request"]["proposal_id"] = f"proposal:{trip_id}"
    submission_fixture["request"]["payload"]["proposal_ref"] = f"proposal:{trip_id}"
    submission = {
        "proposal": _proposal_payload(trip_id),
        "request": submission_fixture["request"],
        "response": submission_fixture["response"],
        "proposal_version": "proposal-v3",
        "scenario_id": "scenario-a",
    }
    assert client.put(f"/api/workspace/{trip_id}/proposal", json=submission).status_code == 200

    evaluation_fixture = _load_fixture("results", "approved_evaluation.json")
    evaluation_fixture["request"]["trip_id"] = trip_id
    evaluation_fixture["request"]["proposal_id"] = f"proposal:{trip_id}"
    result = evaluation_fixture["response"]["result_payload"]
    result["trip_id"] = trip_id
    result["proposal_id"] = f"proposal:{trip_id}"
    result["evaluation_result"]["proposal_id"] = f"proposal:{trip_id}"
    evaluation = {
        "request": evaluation_fixture["request"],
        "response": evaluation_fixture["response"],
        "proposal_version": "proposal-v3",
        "scenario_id": "scenario-a",
    }
    assert (
        client.put(f"/api/workspace/{trip_id}/proposal/evaluation", json=evaluation).status_code
        == 200
    )
    assert client.post(f"/api/workspace/{trip_id}/proposal/handoff", json={}).status_code == 200
    return trip_id, submission, evaluation


def test_prepared_handoff_persists_only_unknown_manager_state(
    client: TestClient, checked_handoff: tuple[str, dict, dict]
) -> None:
    trip_id, _, _ = checked_handoff
    prepared = client.post(f"/api/workspace/{trip_id}/proposal/handoff", json={})
    assert prepared.status_code == 200
    assert prepared.headers["cache-control"] == "no-store"
    metadata = prepared.json()["handoff"]
    assert metadata["status"] == "prepared"
    assert metadata["prepared_at"] is not None
    assert metadata["manager_submission_status"] == "unknown"
    assert metadata["manager_decision"] is None
    assert set(metadata) == {
        "schema_version",
        "source_snapshot_hash",
        "prepared_at",
        "status",
        "manager_submission_status",
        "manager_decision",
    }

    # Read the stored row through a new session: preparation records no receipt or decision.
    with get_session_factory()() as session:
        record = session.get(PersistedProposalState, f"proposal-state:{trip_id}")
        assert record is not None
        stored = record.portal_handoff
        assert stored is not None
        assert stored["source_snapshot"]["traveler_name"] == "Proposal Owner"
        assert {key: stored[key] for key in metadata} == metadata

    for path in (f"/api/workspace/{trip_id}/proposal", f"/api/workspace/{trip_id}"):
        reloaded = client.get(path)
        assert reloaded.status_code == 200
        assert reloaded.json()["proposal_state"]["portal_handoff"] == metadata


def test_handoff_response_filters_internal_source_facts(
    client: TestClient,
    checked_handoff: tuple[str, dict, dict],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trip_planner.app.routes import proposal as proposal_routes

    trip_id, _, _ = checked_handoff
    prepared = client.post(f"/api/workspace/{trip_id}/proposal/handoff", json={})
    assert prepared.status_code == 200
    public_payload = prepared.json()
    with get_session_factory()() as session:
        record = session.get(PersistedProposalState, f"proposal-state:{trip_id}")
        assert record is not None
        internal_metadata = dict(record.portal_handoff or {})
    assert "source_snapshot" in internal_metadata

    # If a service returns persisted metadata directly, response serialization
    # still must not disclose the proposal, full verdict or source price records.
    monkeypatch.setattr(
        proposal_routes,
        "prepare_workspace_proposal_handoff",
        lambda *args, **kwargs: {**public_payload, "handoff": internal_metadata},
    )
    response = client.post(f"/api/workspace/{trip_id}/proposal/handoff", json={})

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == public_payload


@pytest.mark.parametrize(
    "payload",
    [
        {"action_url": "https://caller.example/portal/handoff"},
        {"fields": {"traveler_name": "Caller supplied traveler"}},
        {"manager_submission_status": "sent", "manager_decision": "approved"},
    ],
)
def test_handoff_rejects_caller_supplied_destination_fields_and_manager_state(
    client: TestClient, checked_handoff: tuple[str, dict, dict], payload: dict
) -> None:
    trip_id, _, _ = checked_handoff
    before = client.get(f"/api/workspace/{trip_id}/proposal").json()
    rejected = client.post(f"/api/workspace/{trip_id}/proposal/handoff", json=payload)
    assert rejected.status_code == 422
    assert client.get(f"/api/workspace/{trip_id}/proposal").json() == before


def test_handoff_ignores_query_overrides_and_uses_saved_traveler(
    client: TestClient, checked_handoff: tuple[str, dict, dict]
) -> None:
    trip_id, _, _ = checked_handoff
    prepared = client.post(
        f"/api/workspace/{trip_id}/proposal/handoff",
        params={"action_url": "https://caller.example", "traveler_name": "Caller supplied name"},
        json={},
    )
    assert prepared.status_code == 200
    payload = prepared.json()
    assert payload["action_url"] == "https://tpp.example/portal/handoff"
    assert payload["fields"]["traveler_name"] == "Proposal Owner"
    assert "source_snapshot" not in payload
    assert "source_snapshot" not in payload["handoff"]


@pytest.mark.parametrize(
    ("media_type", "body"),
    [
        ("application/x-www-form-urlencoded", "traveler_name=Caller+supplied+name"),
        ("application/x-www-form-urlencoded", "{}"),
        ("text/plain", "{}"),
    ],
)
def test_handoff_rejects_native_form_requests_to_planner(
    client: TestClient, checked_handoff: tuple[str, dict, dict], media_type: str, body: str
) -> None:
    trip_id, _, _ = checked_handoff
    before = client.get(f"/api/workspace/{trip_id}/proposal").json()
    rejected = client.post(
        f"/api/workspace/{trip_id}/proposal/handoff",
        content=body,
        headers={"Content-Type": media_type},
    )
    assert rejected.status_code == 415
    assert client.get(f"/api/workspace/{trip_id}/proposal").json() == before


@pytest.mark.parametrize("other_account", [False, True], ids=["signed-out", "another-traveler"])
def test_handoff_requires_the_saved_trip_owner(
    client: TestClient, checked_handoff: tuple[str, dict, dict], other_account: bool
) -> None:
    trip_id, _, _ = checked_handoff
    before = client.get(f"/api/workspace/{trip_id}/proposal").json()["proposal_state"][
        "portal_handoff"
    ]
    client.cookies.clear()
    if other_account:
        signup = client.post(
            "/api/auth/signup",
            json={"email": "other@example.com", "password": "password123", "display_name": "Other"},
        )
        assert signup.status_code == 201

    rejected = client.post(f"/api/workspace/{trip_id}/proposal/handoff", json={})
    assert rejected.status_code == (404 if other_account else 401)
    with get_session_factory()() as session:
        record = session.get(PersistedProposalState, f"proposal-state:{trip_id}")
        assert record is not None
        assert record.portal_handoff is not None
        assert {key: record.portal_handoff[key] for key in before} == before


@pytest.mark.parametrize(
    "origin",
    [
        "https://tpp.example:invalid",
        "https://[::1",
        "http://localhost",
        "https://@tpp.example",
        "https://:@tpp.example",
        "https://tpp.example|other.example",
        "https://tpp.example%2f.other.example",
        "https://[::1%25eth0]",
    ],
)
def test_handoff_bad_server_origin_returns_unavailable_without_changing_state(
    client: TestClient, checked_handoff: tuple[str, dict, dict], monkeypatch, origin: str
) -> None:
    trip_id, _, _ = checked_handoff
    before = client.get(f"/api/workspace/{trip_id}/proposal").json()
    monkeypatch.setenv("TRIP_PLANNER_ENV", "production")
    monkeypatch.setenv("TPP_PORTAL_BASE_URL", origin)

    rejected = client.post(f"/api/workspace/{trip_id}/proposal/handoff", json={})
    assert rejected.status_code == 503
    assert client.get(f"/api/workspace/{trip_id}/proposal").json() == before


def test_handoff_configuration_recovery_preserves_the_saved_verdict(
    client: TestClient, checked_handoff: tuple[str, dict, dict], monkeypatch: pytest.MonkeyPatch
) -> None:
    trip_id, _, _ = checked_handoff
    monkeypatch.setenv("TRIP_PLANNER_ENV", "production")
    monkeypatch.delenv("TPP_PORTAL_BASE_URL", raising=False)
    monkeypatch.delenv("TPP_BASE_URL", raising=False)
    before = client.get(f"/api/workspace/{trip_id}/proposal").json()

    unavailable = client.post(f"/api/workspace/{trip_id}/proposal/handoff", json={})
    assert unavailable.status_code == 503
    assert client.get(f"/api/workspace/{trip_id}/proposal").json() == before

    # Deployment configuration can restore the handoff without changing checked facts.
    monkeypatch.setenv("TPP_BASE_URL", "https://fallback-tpp.example")
    prepared = client.post(
        f"/api/workspace/{trip_id}/proposal/handoff",
        params={"action_url": "https://caller.example", "traveler_name": "Caller name"},
        json={},
    )
    assert prepared.status_code == 200
    assert prepared.headers["cache-control"] == "no-store"
    payload = prepared.json()
    assert payload["action_url"] == "https://fallback-tpp.example/portal/handoff"
    assert payload["method"] == "POST"
    assert payload["fields"]["traveler_name"] == "Proposal Owner"
    assert (
        payload["handoff"]["source_snapshot_hash"]
        == before["proposal_state"]["portal_handoff"]["source_snapshot_hash"]
    )
    assert payload["handoff"]["manager_submission_status"] == "unknown"
    assert payload["handoff"]["manager_decision"] is None


def test_handoff_portal_origin_is_independent_of_policy_api_configuration(
    client: TestClient, checked_handoff: tuple[str, dict, dict], monkeypatch: pytest.MonkeyPatch
) -> None:
    trip_id, _, _ = checked_handoff
    monkeypatch.setenv("TRIP_PLANNER_ENV", "production")
    monkeypatch.setenv("TPP_BASE_URL", "https://policy-api.example/api")
    monkeypatch.setenv("TPP_PORTAL_BASE_URL", "https://traveler-portal.example:8443/")

    prepared = client.post(f"/api/workspace/{trip_id}/proposal/handoff", json={})
    assert prepared.status_code == 200
    assert prepared.json()["action_url"] == "https://traveler-portal.example:8443/portal/handoff"
    assert prepared.json()["fields"]["traveler_name"] == "Proposal Owner"


def test_handoff_invalid_explicit_portal_origin_does_not_use_fallback(
    client: TestClient, checked_handoff: tuple[str, dict, dict], monkeypatch: pytest.MonkeyPatch
) -> None:
    trip_id, _, _ = checked_handoff
    monkeypatch.setenv("TRIP_PLANNER_ENV", "production")
    monkeypatch.setenv("TPP_BASE_URL", "https://fallback-tpp.example")
    monkeypatch.setenv("TPP_PORTAL_BASE_URL", "http://traveler-portal.example")
    before = client.get(f"/api/workspace/{trip_id}/proposal").json()

    unavailable = client.post(f"/api/workspace/{trip_id}/proposal/handoff", json={})
    assert unavailable.status_code == 503
    assert client.get(f"/api/workspace/{trip_id}/proposal").json() == before


def test_handoff_requires_a_saved_policy_result(
    client: TestClient, checked_handoff: tuple[str, dict, dict]
) -> None:
    trip_id, _, _ = checked_handoff
    with get_session_factory()() as session:
        record = session.get(PersistedProposalState, f"proposal-state:{trip_id}")
        assert record is not None
        record.evaluation_record = {}
        session.commit()

    rejected = client.post(f"/api/workspace/{trip_id}/proposal/handoff", json={})
    assert rejected.status_code == 409
    assert "Run the policy check again" in rejected.json()["detail"]


@pytest.mark.parametrize(
    ("model", "field", "value"),
    [
        (PersistedTrip, "origin", "LAX"),
        (PersistedTrip, "primary_regions", ["Denver"]),
        (PersistedTrip, "start_date", "2026-05-03"),
        (PersistedTrip, "duration_days", 4),
        (PersistedTrip, "traveler_count", 2),
        (PersistedTrip, "traveler_party_kind", "team"),
        (PersistedTrip, "traveler_notes", "Requires accessible transport"),
        (PersistedTripPrice, "amount", 625.0),
        (PersistedTripPrice, "note", "Revised fare source"),
        (PersistedTripPrice, "lowest_amount", 400.0),
        (PersistedTripPrice, "evidence_attested", True),
        (PersistedTripPrice, "cabin_class", "business"),
        (PersistedTripPrice, "flight_hours", 8.0),
    ],
    ids=lambda value: value.__name__ if isinstance(value, type) else str(value),
)
def test_handoff_rejects_changed_saved_facts(
    client: TestClient, checked_handoff: tuple[str, dict, dict], model, field: str, value
) -> None:
    trip_id, _, evaluation = checked_handoff
    # Exercise the hash independently of the trip edit route's verdict deletion.
    with get_session_factory()() as session:
        record_id = trip_id if model is PersistedTrip else f"trip-price:{trip_id}:transport"
        record = session.get(model, record_id)
        assert record is not None
        setattr(record, field, value)
        session.commit()

    stale = client.post(f"/api/workspace/{trip_id}/proposal/handoff", json={})
    assert stale.status_code == 409
    assert "Run the policy check again" in stale.json()["detail"]

    # Fetching the original execution's verdict must not rebind it to changed facts.
    refreshed = client.put(f"/api/workspace/{trip_id}/proposal/evaluation", json=evaluation)
    assert refreshed.status_code == 200
    assert client.post(f"/api/workspace/{trip_id}/proposal/handoff", json={}).status_code == 409


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("compliance_score", 0.5),
        ("notes", ["Additional documentation required"]),
        ("approval_requirements", [{"role": "director", "reason": "Review", "mandatory": True}]),
    ],
)
def test_handoff_hash_binds_full_policy_result(
    client: TestClient, checked_handoff: tuple[str, dict, dict], field: str, value
) -> None:
    trip_id, _, _ = checked_handoff
    with get_session_factory()() as session:
        record = session.get(PersistedProposalState, f"proposal-state:{trip_id}")
        assert record is not None
        evaluation = dict(record.evaluation_record)
        evaluation["evaluation_result"] = {**evaluation["evaluation_result"], field: value}
        record.evaluation_record = evaluation
        session.commit()

    # Status and rule codes are unchanged; the full saved result has changed.
    assert client.post(f"/api/workspace/{trip_id}/proposal/handoff", json={}).status_code == 409


def test_handoff_hash_binds_submitted_proposal(
    client: TestClient, checked_handoff: tuple[str, dict, dict]
) -> None:
    trip_id, _, _ = checked_handoff
    with get_session_factory()() as session:
        record = session.get(PersistedProposalState, f"proposal-state:{trip_id}")
        assert record is not None
        record.proposal_payload = {**record.proposal_payload, "approval_notes": ["Changed request"]}
        session.commit()

    assert client.post(f"/api/workspace/{trip_id}/proposal/handoff", json={}).status_code == 409


def test_legacy_verdict_requires_new_submission_to_bind_facts(
    client: TestClient, checked_handoff: tuple[str, dict, dict]
) -> None:
    trip_id, submission, evaluation = checked_handoff
    with get_session_factory()() as session:
        record = session.get(PersistedProposalState, f"proposal-state:{trip_id}")
        assert record is not None
        record.portal_handoff = None
        session.commit()

    refreshed = client.put(f"/api/workspace/{trip_id}/proposal/evaluation", json=evaluation)
    assert refreshed.status_code == 200
    assert refreshed.json()["proposal_state"]["portal_handoff"] is None
    assert client.post(f"/api/workspace/{trip_id}/proposal/handoff", json={}).status_code == 409

    assert client.put(f"/api/workspace/{trip_id}/proposal", json=submission).status_code == 200
    assert (
        client.put(f"/api/workspace/{trip_id}/proposal/evaluation", json=evaluation).status_code
        == 200
    )
    assert client.post(f"/api/workspace/{trip_id}/proposal/handoff", json={}).status_code == 200


def test_fresh_policy_check_restores_handoff_after_price_change(
    client: TestClient, checked_handoff: tuple[str, dict, dict]
) -> None:
    trip_id, submission, evaluation = checked_handoff
    original = client.post(f"/api/workspace/{trip_id}/proposal/handoff", json={}).json()
    updated = client.put(
        f"/api/workspace/{trip_id}/prices",
        json={"component": "transport", "amount": 625.0, "note": "Revised quote"},
    )
    assert updated.status_code == 200
    assert client.post(f"/api/workspace/{trip_id}/proposal/handoff", json={}).status_code == 409

    proposal = submission["proposal"]
    proposal["selected_options"][0]["estimated_cost"]["typical_amount"] = 625.0
    proposal["selected_options"][0]["estimated_cost"]["min_amount"] = 625.0
    proposal["selected_options"][0]["estimated_cost"]["max_amount"] = 625.0
    proposal["cost_summary"]["total_estimated_cost"] = 625.0
    proposal["cost_summary"]["category_estimates"]["transport"] = 625.0
    assert client.put(f"/api/workspace/{trip_id}/proposal", json=submission).status_code == 200
    assert client.post(f"/api/workspace/{trip_id}/proposal/handoff", json={}).status_code == 409
    assert (
        client.put(f"/api/workspace/{trip_id}/proposal/evaluation", json=evaluation).status_code
        == 200
    )
    prepared = client.post(f"/api/workspace/{trip_id}/proposal/handoff", json={})
    assert prepared.status_code == 200
    metadata = prepared.json()["handoff"]
    assert metadata["source_snapshot_hash"] != original["handoff"]["source_snapshot_hash"]
    assert metadata["manager_submission_status"] == "unknown"
    assert metadata["manager_decision"] is None
    assert "source_snapshot" not in metadata
    assert "USD 625.00" in prepared.json()["fields"]["notes"]
    reloaded = client.get(f"/api/workspace/{trip_id}/proposal").json()
    assert reloaded["proposal_state"]["portal_handoff"] == metadata
    repeated = client.post(f"/api/workspace/{trip_id}/proposal/handoff", json={}).json()
    assert repeated["handoff"]["source_snapshot_hash"] == metadata["source_snapshot_hash"]


def test_client_supplied_response_cannot_set_approval_ready(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A production request body cannot forge a compliant TPP verdict."""
    monkeypatch.setenv("TRIP_PLANNER_ENV", "production")
    created = client.post(
        "/api/trips",
        json={
            "title": "Forged verdict attempt",
            "summary": "Verify the production route ignores a caller-provided verdict.",
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
    workspace = client.get(f"/api/workspace/{trip_id}").json()
    scenario_id = workspace["route_comparison"]["scenarios"][0]["scenario_id"]
    fixture = _load_fixture("results", "approved_evaluation.json")
    fixture["request"]["trip_id"] = trip_id
    fixture["request"]["proposal_id"] = f"proposal:{trip_id}"
    fixture["response"]["result_payload"]["trip_id"] = trip_id
    fixture["response"]["result_payload"]["proposal_id"] = f"proposal:{trip_id}"
    response = client.put(
        f"/api/workspace/{trip_id}/proposal",
        json={
            "proposal": _proposal_payload(trip_id),
            "request": fixture["request"],
            "response": fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": scenario_id,
        },
    )

    assert response.status_code == 503
    reloaded = client.get(f"/api/workspace/{trip_id}/proposal")
    assert reloaded.status_code == 200
    assert reloaded.json()["proposal_state"] is None


def test_production_evaluation_ignores_caller_compliant_response(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A production evaluation cannot use a caller-supplied compliant verdict."""
    created = client.post(
        "/api/trips",
        json={
            "title": "Forged evaluation attempt",
            "summary": "Verify production evaluation ignores caller-provided approval state.",
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

    monkeypatch.setenv("TRIP_PLANNER_ENV", "production")
    evaluation_fixture = _load_fixture("results", "approved_evaluation.json")
    evaluation_fixture["request"]["trip_id"] = trip_id
    evaluation_fixture["request"]["proposal_id"] = f"proposal:{trip_id}"
    evaluation_fixture["response"]["result_payload"]["trip_id"] = trip_id
    evaluation_fixture["response"]["result_payload"]["proposal_id"] = f"proposal:{trip_id}"
    evaluated = client.put(
        f"/api/workspace/{trip_id}/proposal/evaluation",
        json={
            "request": evaluation_fixture["request"],
            "response": evaluation_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )

    assert evaluated.status_code == 503
    reloaded = client.get(f"/api/workspace/{trip_id}/proposal")
    assert reloaded.status_code == 200
    assert reloaded.json()["proposal_state"]["evaluation"] == {}
    assert reloaded.json()["proposal_state"]["summary"]["approval_ready"] is False


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


def test_non_compliant_reoptimize_surfaces_plan_in_workspace_reload(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Reoptimization plan workspace",
            "summary": "Persist reoptimization output after a non-compliant policy result.",
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
    proposal_id = f"proposal:{trip_id}"

    reoptimize_fixture = _load_fixture("reoptimization", "non_compliant_manual_review.json")
    proposal_payload = reoptimize_fixture["proposal"]
    proposal_payload["trip_id"] = trip_id
    proposal_payload["proposal_id"] = proposal_id
    proposal_payload["source_version"]["trip_id"] = trip_id

    submission_fixture = _load_fixture("proposal_submit_deferred.json")
    submission_fixture["request"]["trip_id"] = trip_id
    submission_fixture["request"]["proposal_id"] = proposal_id
    submission_fixture["request"]["payload"]["proposal_ref"] = proposal_id
    submitted = client.put(
        f"/api/workspace/{trip_id}/proposal",
        json={
            "proposal": proposal_payload,
            "request": submission_fixture["request"],
            "response": submission_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )
    assert submitted.status_code == 200

    evaluation_fixture = _load_fixture("results", "non_compliant_evaluation.json")
    evaluation_fixture["request"]["trip_id"] = trip_id
    evaluation_fixture["request"]["proposal_id"] = proposal_id
    result_payload = evaluation_fixture["response"]["result_payload"]
    result_payload["trip_id"] = trip_id
    result_payload["proposal_id"] = proposal_id
    result_payload["proposal_version"] = "proposal-v3"
    result_payload["evaluation_result"] = reoptimize_fixture["evaluation_result"]
    result_payload["evaluation_result"]["proposal_id"] = proposal_id

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

    reoptimized = client.post(
        f"/api/workspace/{trip_id}/proposal/reoptimize",
        json={
            "comparable_refs": reoptimize_fixture["comparable_refs"],
            "justification_refs": reoptimize_fixture["justification_refs"],
        },
    )
    assert reoptimized.status_code == 200
    plan = reoptimized.json()["summary"]["follow_up"]["reoptimization_plan"]
    assert plan["reaction_kind"] in (
        "rerank",
        "narrow_candidates",
        "regenerate_scenario",
        "manual_review",
        "create_exception_candidate",
    )
    assert plan["candidate_categories"]

    workspace = client.get(f"/api/workspace/{trip_id}")
    assert workspace.status_code == 200
    reloaded_plan = workspace.json()["proposal_state"]["summary"]["follow_up"][
        "reoptimization_plan"
    ]
    assert reloaded_plan["reaction_kind"] == plan["reaction_kind"]
    assert reloaded_plan["candidate_categories"]


@pytest.mark.parametrize("score", [0.68, None])
def test_workspace_proposal_evaluation_derives_exception_follow_up(
    client: TestClient, score: float | None
) -> None:
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
    evaluation_fixture["response"]["result_payload"]["evaluation_result"][
        "compliance_score"
    ] = score

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
    assert payload["evaluation"]["evaluation_result"]["compliance_score"] == score

    session = get_session_factory()()
    try:
        record = session.query(PersistedProposalState).filter_by(trip_id=trip_id).one()
        assert record.evaluation_record["evaluation_result"]["compliance_score"] == score
    finally:
        session.close()

    reloaded = client.get(f"/api/workspace/{trip_id}")
    assert reloaded.status_code == 200
    reloaded_state = reloaded.json()["proposal_state"]
    assert reloaded_state["summary"]["evaluation_result_status"] == "exception_required"
    assert reloaded_state["follow_up"]["status"] == "exception_required"


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
    assert evaluated.json()["detail"].startswith("The workspace proposal request was invalid.")


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
    assert scenario_response.json()["detail"].startswith(
        "The workspace proposal request was invalid."
    )

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
    assert response.json()["detail"].startswith("The workspace proposal request was invalid.")


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
                "destination": "Chicago",
                "origin_city": "ORD",
                "destination_city": "Chicago",
                "departure_date": "2026-05-04",
                "return_date": "2026-05-06",
                "purpose": "Use runtime TPP HTTP transport.",
                "transportation_mode": "air",
                "expected_costs": {"airfare": 620.0},
                "estimated_cost": 620.0,
                "status": "submitted",
                "expense_breakdown": {"airfare": 620.0},
                "selected_fare": 620.0,
                "flight_cost": 620.0,
                # Nothing entered on this trip's Budget tab, so none of these is sent as a value.
                # The policy id used to go out as `department` and `funding_source`.
                "lowest_fare": None,
                "fare_evidence_attached": None,
                "cabin_class": None,
                "flight_duration_hours": None,
                "expenses": None,
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
    assert response.json()["detail"].startswith("The workspace proposal request was invalid.")


def test_workspace_proposal_submission_persists_stored_policy_when_live_tpp_times_out(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TPP_BASE_URL", "https://tpp.example.test")
    monkeypatch.setenv("TPP_ACCESS_TOKEN", "token-123")
    monkeypatch.setenv("TPP_OIDC_PROVIDER", "okta")
    monkeypatch.setenv("TPP_TRANSPORT_MAX_ATTEMPTS", "1")
    _install_fake_http(monkeypatch, [TimeoutError("slow response")])

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
        raise TimeoutError("evaluation read timeout")

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


def _deferred_submission_and_poll() -> tuple[_FakeHTTPResponse, _FakeHTTPResponse]:
    """Submission and a poll that both say "deferred": TPP's status stays deferred until a
    person approves the trip, whatever the policy verdict."""

    deferred = {
        "transport_pattern": "deferred",
        "execution_status": {
            "state": "deferred",
            "terminal": False,
            "summary": "Proposal queued for evaluation.",
            "poll_after_seconds": 30,
            "external_status": "202 Accepted",
            "updated_at": "2026-09-22T23:57:05Z",
        },
        "result_payload": {
            "execution_id": "exec-live-009",
            "queue_state": "waiting_for_policy_engine",
        },
        "received_at": "2026-09-22T23:57:05Z",
        "status_endpoint": "https://tpp.example.test/api/planner/proposals/p/executions/exec-live-009",
    }
    return _FakeHTTPResponse(200, dict(deferred)), _FakeHTTPResponse(200, dict(deferred))


def _submit_deferred_trip(client: TestClient) -> str:
    created = client.post(
        "/api/trips",
        json={
            "title": "Compliant but awaiting approval",
            "summary": "A trip TPP has passed but no person has approved yet.",
            "mode": "business",
            "trip_frame": {
                "start_date": "2026-10-05",
                "end_date": "2026-10-07",
                "duration_days": 3,
                "primary_regions": ["Chicago"],
            },
        },
    )
    trip_id = created.json()["trip"]["trip_id"]
    fixture = _load_fixture("proposal_submit_deferred.json")
    fixture["request"]["trip_id"] = trip_id
    fixture["request"]["proposal_id"] = f"proposal:{trip_id}"
    fixture["request"]["payload"]["proposal_ref"] = f"proposal:{trip_id}"
    submitted = client.put(
        f"/api/workspace/{trip_id}/proposal",
        json={
            "proposal": _proposal_payload(trip_id),
            "request": fixture["request"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )
    assert submitted.status_code == 200, submitted.text
    return str(trip_id)


def test_refresh_reads_the_verdict_while_approval_is_still_pending(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The latch this closes, observed 2026-09-22 against a live TPP service.

    TPP derives the execution status from the trip's APPROVAL state, so it reports
    "deferred" until a person approves, while the policy verdict is already final at the
    result endpoint. Refresh read the verdict only after "succeeded", and approval happens in
    TPP's portal, which this workspace never reaches. A compliant trip therefore read
    "Policy review is deferred" forever.
    """

    monkeypatch.setenv("TPP_BASE_URL", "https://tpp.example.test")
    monkeypatch.setenv("TPP_ACCESS_TOKEN", "token-123")
    monkeypatch.setenv("TPP_OIDC_PROVIDER", "okta")
    submission, poll = _deferred_submission_and_poll()
    evaluation = _FakeHTTPResponse(
        200,
        {
            "trip_id": "placeholder",
            "proposal_id": "proposal:placeholder",
            "proposal_version": "proposal-v3",
            "execution_id": "exec-live-009",
            "request_id": "ignored",
            "correlation_id": {"value": "ignored", "issued_by": "tpp"},
            "outcome": "compliant",
            "result_endpoint": "GET /api/planner/executions/exec-live-009/evaluation-result",
            "status_endpoint": "https://tpp.example.test/api/planner/proposals/p/executions/exec-live-009",
            "policy_result": {"status": "pass", "issues": [], "policy_version": "policy-v1"},
            "blocking_issues": [],
            "preferred_alternatives": [],
            "exception_requirements": [],
            "reoptimization_guidance": [],
            "generated_at": "2026-09-22T23:57:06Z",
        },
    )
    captured: list[dict[str, object]] = []
    _install_fake_http(monkeypatch, [submission, poll, evaluation], captured_requests=captured)
    trip_id = _submit_deferred_trip(client)
    evaluation._payload["trip_id"] = trip_id
    evaluation._payload["proposal_id"] = f"proposal:{trip_id}"
    evaluation.text = json.dumps(evaluation._payload)

    refreshed = client.post(f"/api/workspace/{trip_id}/proposal/refresh")

    assert refreshed.status_code == 200, refreshed.text
    state = refreshed.json()["proposal_state"]
    assert state["summary"]["evaluation_result_status"] == "compliant"
    assert state["summary"]["approval_ready"] is True
    assert captured[-1]["full_url"] == (
        "https://tpp.example.test/api/planner/executions/exec-live-009/evaluation-result"
    )


def test_refresh_with_no_verdict_yet_keeps_waiting_without_recording_a_failure(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The inverse: while evaluation is genuinely still running, reading the result endpoint
    early must not turn "not yet" into a failure the traveller is asked to fix."""

    monkeypatch.setenv("TPP_BASE_URL", "https://tpp.example.test")
    monkeypatch.setenv("TPP_ACCESS_TOKEN", "token-123")
    monkeypatch.setenv("TPP_OIDC_PROVIDER", "okta")
    submission, poll = _deferred_submission_and_poll()
    not_ready = _FakeHTTPResponse(404, {"detail": "evaluation not ready"})
    _install_fake_http(monkeypatch, [submission, poll, not_ready])
    trip_id = _submit_deferred_trip(client)

    refreshed = client.post(f"/api/workspace/{trip_id}/proposal/refresh")

    assert refreshed.status_code == 200, refreshed.text
    state = refreshed.json()["proposal_state"]
    assert state["submission_status"] == "deferred"
    assert state["summary"].get("evaluation_result_status") is None
    assert state["summary"]["submission_outcome"] != "failed"


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


def test_proposal_state_persists_across_create_app_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Issue #1187 task-list item: proposal state persists across a
    ``create_app()`` restart.

    The live-tpp verification captured for PR #1190 demonstrated a
    successful lifecycle PASS, but did not prove that proposal state
    survives a trip-planner app restart against the same backing DB. This
    test closes that gap by:

    1. Creating the app instance, submitting a proposal + its evaluation,
       and asserting the lifecycle landed on disk via a workspace GET.
    2. Closing the first TestClient (drops the SQLAlchemy session factory
       reference and exits the FastAPI lifespan).
    3. Building a *fresh* ``create_app()`` instance against the **same**
       SQLite file (no ``reset_database_state``), opening a new TestClient,
       and asserting the same workspace GET returns the proposal +
       evaluation exactly as persisted by the first app instance.

    A regression where proposal state is held only in process memory (e.g.
    a non-persistent cache layer accidentally promoted to the proposal
    source-of-truth) would surface here as a 404 / empty proposal payload
    from the second app instance.
    """
    db_path = tmp_path / "restart-persistence.db"
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("TRIP_PLANNER_ALLOW_FIXTURE_TPP_RESPONSES", "true")
    reset_database_state()

    # ---- First app instance: submit + evaluate a proposal. ------------------
    app_first = create_app()
    with TestClient(app_first) as client_first:
        client_first.post(
            "/api/auth/signup",
            json={
                "email": "restart@example.com",
                "password": "password123",
                "display_name": "Restart Owner",
            },
        )
        created = client_first.post(
            "/api/trips",
            json={
                "title": "Restart-persistence proposal",
                "summary": "Proves proposal state survives create_app() restart.",
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

        submitted = client_first.put(
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
        evaluation_fixture["response"]["result_payload"]["proposal_id"] = f"proposal:{trip_id}"
        evaluation_fixture["response"]["result_payload"]["evaluation_result"][
            "proposal_id"
        ] = f"proposal:{trip_id}"

        evaluated = client_first.put(
            f"/api/workspace/{trip_id}/proposal/evaluation",
            json={
                "request": evaluation_fixture["request"],
                "response": evaluation_fixture["response"],
                "proposal_version": "proposal-v3",
                "scenario_id": "scenario-a",
            },
        )
        assert evaluated.status_code == 200

        first_app_view = client_first.get(f"/api/workspace/{trip_id}/proposal").json()
        first_evaluation_id = first_app_view["proposal_state"]["evaluation"]["evaluation_result"][
            "evaluation_id"
        ]
        first_evaluation_status = first_app_view["proposal_state"]["evaluation"][
            "evaluation_result"
        ]["status"]

    # Confirm the SQLite file actually exists on disk before we restart.
    assert db_path.exists(), "first app instance did not persist the DB file"

    # ---- Second app instance against the SAME DB (no reset). ----------------
    # If proposal state were held only in process memory or a non-persistent
    # cache, the second client below would see an empty / 404 proposal
    # payload, which is exactly the regression this test guards against.
    app_second = create_app()
    with TestClient(app_second) as client_second:
        # Sign in as the same user (the persisted account survives the
        # restart along with the proposal).
        signin = client_second.post(
            "/api/auth/login",
            json={"email": "restart@example.com", "password": "password123"},
        )
        assert signin.status_code == 200, signin.text

        reloaded = client_second.get(f"/api/workspace/{trip_id}/proposal")
        assert reloaded.status_code == 200, reloaded.text
        reloaded_payload = reloaded.json()

        # Exact-value match across the restart — proposal_id, evaluation
        # status, evaluation_id, and the persisted summary must all be
        # identical between the two app instances.
        assert (
            reloaded_payload["proposal_state"]["proposal"]["proposal_id"] == f"proposal:{trip_id}"
        )
        assert (
            reloaded_payload["proposal_state"]["evaluation"]["evaluation_result"]["evaluation_id"]
            == first_evaluation_id
        )
        assert (
            reloaded_payload["proposal_state"]["evaluation"]["evaluation_result"]["status"]
            == first_evaluation_status
        )
        assert reloaded_payload["proposal_state"]["summary"]["submission_status"] == "deferred"

    reset_database_state()
