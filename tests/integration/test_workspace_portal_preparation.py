"""Consumer preparation persistence; producer answer validation is not mocked acceptance."""

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from uuid import uuid4

import pytest
from fastapi import HTTPException, Response
from fastapi.testclient import TestClient

from tests.integration.test_workspace_portal_receipt import ReceiptClient, decide
from trip_planner.app.main import create_app
from trip_planner.app.routes.proposal import prepare_workspace_proposal_portal_handoff
from trip_planner.app.schemas.proposal import WorkspaceProposalHandoffRequest
from trip_planner.app.services.auth import require_authenticated_user
from trip_planner.app.services.portal_receipt import refresh_workspace_portal_receipt
from trip_planner.app.services.proposal import (
    _bind_portal_handoff_evaluation_snapshot,
    _bind_portal_handoff_snapshot,
    get_workspace_proposal_payload,
)
from trip_planner.app.services.trips import update_trip
from trip_planner.integrations.tpp.portal_receipt import PortalBrowserSession
from trip_planner.integrations.tpp.portal_receipt_client import PortalPreparationError
from trip_planner.persistence.db import get_db_session, get_session_factory
from trip_planner.persistence.models.proposal import PersistedProposalState
from trip_planner.persistence.models.trip import PersistedTrip
from trip_planner.persistence.models.trip_price import PersistedTripPrice


class PreparationClient(ReceiptClient):
    """Exercise consumer correlation independently of the producer's required-answer gate."""

    def __init__(self):
        super().__init__()
        self.preparations = []
        self.browser_bindings = []
        self.capability = uuid4().hex
        self.browser_failure = None

    def prepare_handoff(self, *, identity, handoff_id, snapshot_version, answers):
        self.preparations.append((handoff_id, snapshot_version, deepcopy(answers)))
        if self.failure:
            raise self.failure
        self.payload = {
            "handoff_id": handoff_id,
            "snapshot_version": snapshot_version,
            "snapshot_sha256": sha256(str(answers).encode()).hexdigest(),
            "draft_id": "draft-1",
            "contract_version": "portal-receipt/v1",
            "state": "prepared",
            "prepared_at": "2026-10-10T12:00:00Z",
            "observed_at": "2026-10-10T12:30:00Z",
            "request_id": None,
            "execution_id": None,
            "review_id": None,
            "submitted_at": None,
            "decision": None,
            "decision_at": None,
        }
        return deepcopy(self.payload)

    def create_browser_session(self, *, identity, binding):
        self.browser_bindings.append(binding)
        if self.browser_failure:
            raise self.browser_failure
        return PortalBrowserSession(draft_id=binding.draft_id, handoff_token=self.capability)


def prepare(saved_portal_handoff, client):
    session, user, trip_id, _ = saved_portal_handoff
    response = Response()
    result = prepare_workspace_proposal_portal_handoff(
        trip_id=trip_id,
        _payload=WorkspaceProposalHandoffRequest(),
        response=response,
        user=user,
        db_session=session,
        client=client,
    ).model_dump()
    assert response.headers["cache-control"] == "no-store"
    return result


def test_production_route_uses_configured_owner_client_and_saved_facts(saved_portal_handoff):
    session, user, trip_id, original = saved_portal_handoff
    client = PreparationClient()
    app = create_app(portal_receipt_client=client)
    app.dependency_overrides[require_authenticated_user] = lambda: user
    app.dependency_overrides[get_db_session] = lambda: session
    with TestClient(app) as browser:
        prepared = browser.post(f"/api/workspace/{trip_id}/proposal/handoff", json={})
    assert prepared.status_code == 200
    assert prepared.headers["cache-control"] == "no-store"
    result = prepared.json()
    assert result["action_url"] == "https://tpp.example/portal/handoff/receipt"
    assert result["fields"] == {"handoff_token": client.capability}
    assert result["method"] == "POST"
    assert client.users == [user.user_id]
    assert client.preparations[0][2] == original["fields"]
    # Missing traveler answers are not invented; the real producer rejects them.
    assert "destination_zip" not in client.preparations[0][2]
    assert "booking_date" not in client.preparations[0][2]
    assert result["handoff"]["manager_submission_status"] == "unknown"
    assert result["handoff"]["manager_decision"] is None
    record = session.get(PersistedProposalState, f"proposal-state:{trip_id}")
    assert record.portal_handoff["producer_owner"] == client.identity.owner_binding()
    assert record.portal_handoff["producer_binding"] == client.browser_bindings[0].model_dump()
    assert record.portal_handoff["browser_review"]["draft_id"] == "draft-1"
    assert client.capability not in str(record.portal_handoff)
    assert client.identity.authorization not in str(record.portal_handoff)
    public = get_workspace_proposal_payload(session, user=user, trip_id=trip_id)
    assert public["proposal_state"]["portal_handoff"] == result["handoff"]
    assert (
        not {"producer_owner", "producer_binding", "browser_review", "receipt", "source_snapshot"}
        & result["handoff"].keys()
    )


@pytest.mark.parametrize("failure_stage", ["answers", "browser"])
def test_failed_preparation_is_atomic_and_same_snapshot_retries_same_key(
    saved_portal_handoff, failure_stage
):
    session, _user, trip_id, _ = saved_portal_handoff
    client = PreparationClient()
    record = session.get(PersistedProposalState, f"proposal-state:{trip_id}")
    before = deepcopy(record.portal_handoff)
    revision = record.updated_at
    if failure_stage == "answers":
        client.failure = PortalPreparationError(422)
    else:
        client.browser_failure = PortalPreparationError(503)
    with pytest.raises(HTTPException) as failure:
        prepare(saved_portal_handoff, client)
    assert failure.value.status_code == (422 if failure_stage == "answers" else 503)
    session.expire_all()
    assert record.portal_handoff == before and record.updated_at == revision
    client.failure = client.browser_failure = None
    result = prepare(saved_portal_handoff, client)
    assert client.preparations[0] == client.preparations[1]
    assert result["handoff"]["manager_submission_status"] == "unknown"


@pytest.mark.parametrize("decision", ["approved", "rejected", "changes_requested"])
def test_authenticated_retry_preserves_actual_decision_without_creating_another_draft(
    saved_portal_handoff, decision
):
    session, user, trip_id, _ = saved_portal_handoff
    client = PreparationClient()
    first = prepare(saved_portal_handoff, client)
    decide(client, decision)
    refresh_workspace_portal_receipt(session, user=user, trip_id=trip_id, client=client)
    result = prepare(saved_portal_handoff, client)
    assert len(client.preparations) == 1
    assert client.reads == 2
    assert result["handoff"]["prepared_at"] == first["handoff"]["prepared_at"]
    assert result["handoff"]["manager_decision"] == decision
    assert result["handoff"]["manager_submission_status"] == "decision_recorded"


@pytest.mark.parametrize("change", ["owner", "origin"])
def test_bound_retry_does_not_transport_to_another_owner_or_origin(
    saved_portal_handoff, monkeypatch, change
):
    session, user, trip_id, _ = saved_portal_handoff
    client = PreparationClient()
    prepare(saved_portal_handoff, client)
    record = session.get(PersistedProposalState, f"proposal-state:{trip_id}")
    before = deepcopy(record.portal_handoff)
    if change == "owner":
        client.identity = replace(client.identity, subject="another-owner")
    else:
        monkeypatch.setenv("TPP_PORTAL_BASE_URL", "https://another.example")
    with pytest.raises(HTTPException) as rejected:
        prepare(saved_portal_handoff, client)
    assert rejected.value.status_code == 403
    assert client.reads == 0 and len(client.browser_bindings) == 1
    assert record.portal_handoff == before
    refresh_workspace_portal_receipt(session, user=user, trip_id=trip_id, client=client)
    assert client.reads == 0
    assert record.portal_handoff["receipt_status"] == "unauthorized"


@pytest.mark.parametrize("change", ["price", "proposal", "cleared-verdict"])
def test_slow_preparation_cannot_overwrite_a_concurrent_edit(
    saved_portal_handoff, monkeypatch, change
):
    session, user, trip_id, _ = saved_portal_handoff
    client = PreparationClient()
    record = session.get(PersistedProposalState, f"proposal-state:{trip_id}")
    before = deepcopy(record.portal_handoff)
    original_browser_session = client.create_browser_session

    def edit_during_request(**kwargs):
        with get_session_factory()() as other:
            if change == "price":
                price = other.get(PersistedTripPrice, f"trip-price:{trip_id}:transport")
                price.amount += 1
            elif change == "cleared-verdict":
                assert (
                    update_trip(
                        other,
                        user=user,
                        trip_id=trip_id,
                        changes={"summary": "Changed during authenticated preparation"},
                    )
                    is not None
                )
            else:
                proposal = other.get(PersistedProposalState, record.proposal_state_id)
                proposal.portal_handoff = {**proposal.portal_handoff, "newer_write": True}
            other.commit()
        return original_browser_session(**kwargs)

    monkeypatch.setattr(client, "create_browser_session", edit_during_request)
    with pytest.raises(HTTPException) as rejected:
        prepare(saved_portal_handoff, client)
    assert rejected.value.status_code == 409
    session.expire_all()
    if change == "cleared-verdict":
        assert session.query(PersistedProposalState).filter_by(trip_id=trip_id).count() == 0
        trip = session.get(PersistedTrip, trip_id)
        assert trip.summary == "Changed during authenticated preparation"
        assert (
            get_workspace_proposal_payload(session, user=user, trip_id=trip_id)["proposal_state"]
            is None
        )
        # A producer capability for the removed verdict must never become a
        # saved browser handoff, including when the traveler retries.
        with pytest.raises(HTTPException) as retry:
            prepare(saved_portal_handoff, client)
        assert retry.value.status_code == 409
        assert len(client.preparations) == 1
        assert len(client.browser_bindings) == 1
        return
    assert record.portal_handoff == (
        {**before, "newer_write": True} if change == "proposal" else before
    )
    assert "producer_binding" not in record.portal_handoff


@pytest.mark.parametrize("invalid", ["foreign-draft", "invalid-copy"])
def test_invalid_capability_cannot_establish_a_preparation(
    saved_portal_handoff, monkeypatch, invalid
):
    session, _user, trip_id, _ = saved_portal_handoff
    client = PreparationClient()
    record = session.get(PersistedProposalState, f"proposal-state:{trip_id}")
    before = deepcopy(record.portal_handoff)
    capability = PortalBrowserSession(draft_id="draft-1", handoff_token=client.capability)
    capability = capability.model_copy(
        update=(
            {"draft_id": "another-draft"} if invalid == "foreign-draft" else {"draft_id": "bad/id"}
        )
    )
    monkeypatch.setattr(client, "create_browser_session", lambda **kwargs: capability)
    with pytest.raises(HTTPException) as rejected:
        prepare(saved_portal_handoff, client)
    assert rejected.value.status_code == 502
    assert client.capability not in rejected.value.detail
    session.expire_all()
    assert record.portal_handoff == before


def test_producer_version_must_match_saved_policy_snapshot(saved_portal_handoff):
    session, _user, trip_id, _ = saved_portal_handoff
    client = PreparationClient()
    prepare(saved_portal_handoff, client)
    record = session.get(PersistedProposalState, f"proposal-state:{trip_id}")
    record.portal_handoff = {
        **record.portal_handoff,
        "producer_binding": {
            **record.portal_handoff["producer_binding"],
            "snapshot_version": "other",
        },
    }
    session.commit()
    with pytest.raises(HTTPException) as rejected:
        prepare(saved_portal_handoff, client)
    assert rejected.value.status_code == 409
    assert client.reads == 0 and len(client.browser_bindings) == 1


@pytest.mark.parametrize("rebinding", ["submission", "evaluation"])
def test_new_policy_snapshot_retains_private_producer_history(saved_portal_handoff, rebinding):
    session, user, trip_id, _ = saved_portal_handoff
    client = PreparationClient()
    prepare(saved_portal_handoff, client)
    decide(client, "changes_requested")
    refresh_workspace_portal_receipt(session, user=user, trip_id=trip_id, client=client)
    record = session.get(PersistedProposalState, f"proposal-state:{trip_id}")
    before = deepcopy(record.portal_handoff)
    if rebinding == "submission":
        _bind_portal_handoff_snapshot(
            record=record,
            trip_record=session.get(PersistedTrip, trip_id),
            user=user,
            trip_prices=session.query(PersistedTripPrice).all(),
            status="awaiting_evaluation",
        )
    else:
        result = deepcopy(record.evaluation_record)
        result["evaluation_result"]["evaluation_id"] = "fresh-policy-check"
        record.evaluation_record = result
        _bind_portal_handoff_evaluation_snapshot(
            record=record, current_snapshot=deepcopy(before["source_snapshot"])
        )
    session.commit()
    assert record.portal_handoff["producer_history"] == [before]
    assert "producer_binding" not in record.portal_handoff
    assert record.portal_handoff["manager_decision"] is None
    public = get_workspace_proposal_payload(session, user=user, trip_id=trip_id)
    assert "producer_history" not in public["proposal_state"]["portal_handoff"]
