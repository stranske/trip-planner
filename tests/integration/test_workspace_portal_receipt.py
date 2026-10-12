"""Owner-bound workspace observations retain evidence without inventing freshness."""

from copy import deepcopy
from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request, Response

from trip_planner.app.main import create_app
from trip_planner.app.routes.proposal import (
    prepare_workspace_proposal_portal_handoff,
    refresh_workspace_proposal_portal_receipt,
)
from trip_planner.app.schemas.proposal import WorkspaceProposalHandoffRequest
from trip_planner.app.services.portal_receipt import refresh_workspace_portal_receipt
from trip_planner.app.services.proposal import (
    WorkspaceProposalHandoffNotReadyError,
    _bind_portal_handoff_evaluation_snapshot,
    get_workspace_proposal_payload,
    prepare_workspace_proposal_handoff,
)
from trip_planner.integrations.tpp.portal_receipt_client import (
    OwnerPortalReceiptClient,
    PortalOwnerIdentity,
    PortalReceiptReadError,
)
from trip_planner.persistence.db import get_session_factory
from trip_planner.persistence.models.proposal import PersistedProposalState
from trip_planner.persistence.models.trip import PersistedTrip
from trip_planner.persistence.models.trip_price import PersistedTripPrice


class ReceiptClient(OwnerPortalReceiptClient):
    def __init__(self):
        self.identity = PortalOwnerIdentity("oidc:tenant-a", "traveler-a", "Bearer " + uuid4().hex)
        super().__init__(lambda user_id: self.identity)
        self.payload = None
        self.failure = None
        self.reads = 0
        self.users = []

    def resolve_owner(self, user_id):
        self.users.append(user_id)
        return self.identity

    def read_receipt(self, *, identity, binding):
        self.reads += 1
        if self.failure:
            raise self.failure
        return deepcopy(self.payload)


@pytest.fixture
def bound_workspace(saved_portal_handoff):
    session, user, trip_id, _ = saved_portal_handoff
    record = session.get(PersistedProposalState, f"proposal-state:{trip_id}")
    client = ReceiptClient()
    binding = {
        "handoff_id": "handoff-1",
        "snapshot_version": record.portal_handoff["source_snapshot_hash"],
        "snapshot_sha256": "a" * 64,
        "draft_id": "draft-1",
    }
    # Model the server-retained output of authenticated producer preparation.
    # The legacy browser preparation route does not establish this binding.
    record.portal_handoff = {
        **record.portal_handoff,
        "producer_binding": binding,
        "producer_owner": client.identity.owner_binding(),
    }
    session.commit()
    client.payload = {
        **binding,
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
    return session, user, trip_id, record, client


def refresh(bound_workspace):
    session, user, trip_id, _, client = bound_workspace
    app = create_app(portal_receipt_client=client)
    response = Response()
    result = refresh_workspace_proposal_portal_receipt(
        trip_id,
        Request({"type": "http", "app": app}),
        response,
        WorkspaceProposalHandoffRequest(),
        user,
        session,
    ).model_dump()
    assert response.headers["cache-control"] == "no-store"
    return result["proposal_state"]["portal_handoff"]


def decide(client, decision):
    client.payload.update(
        state="decision_recorded",
        request_id="request-1",
        execution_id="execution-1",
        review_id="review-1",
        submitted_at="2026-10-10T12:10:00Z",
        decision=decision,
        decision_at="2026-10-10T12:20:00Z",
    )


@pytest.mark.parametrize("state", ["prepared", "submitted", "pending_review"])
def test_observed_request_and_review_state_does_not_invent_a_decision(bound_workspace, state):
    *_, client = bound_workspace
    if state != "prepared":
        client.payload.update(state=state, request_id="request-1", execution_id="execution-1")
    if state == "pending_review":
        client.payload.update(review_id="review-1", submitted_at="2026-10-10T12:10:00Z")
    public = refresh(bound_workspace)
    assert public["receipt_status"] == "current"
    assert public["manager_submission_status"] == ("unknown" if state == "prepared" else state)
    assert public["manager_decision"] is None


@pytest.mark.parametrize("decision", ["approved", "rejected", "changes_requested"])
def test_route_records_actual_decision_and_keeps_correlation_private(bound_workspace, decision):
    session, user, trip_id, record, client = bound_workspace
    decide(client, decision)
    public = refresh(bound_workspace)
    assert public["receipt_status"] == "current"
    assert public["manager_submission_status"] == "decision_recorded"
    assert public["manager_decision"] == decision
    assert public["manager_decision_at"] == "2026-10-10T12:20:00+00:00"
    assert client.users == [user.user_id]
    assert not {"producer_owner", "producer_binding", "receipt", "source_snapshot"} & public.keys()
    session.expire_all()
    assert (
        get_workspace_proposal_payload(session, user=user, trip_id=trip_id)["proposal_state"][
            "portal_handoff"
        ]
        == public
    )
    assert record.portal_handoff["receipt"]["decision"] == decision


@pytest.mark.parametrize("status", ["unavailable", "unauthorized", "not_found", "stale"])
def test_failed_observation_retains_historical_decision(bound_workspace, status):
    _, _, _, record, client = bound_workspace
    decide(client, "changes_requested")
    refresh(bound_workspace)
    retained = deepcopy(record.portal_handoff["receipt"])
    client.failure = PortalReceiptReadError(status)
    public = refresh(bound_workspace)
    assert public["receipt_status"] == status
    assert public["manager_submission_status"] == "unknown"
    assert public["manager_decision"] is None
    assert public["last_manager_decision"] == "changes_requested"
    assert record.portal_handoff["receipt"] == retained


@pytest.mark.parametrize("field", ["handoff_id", "snapshot_version", "draft_id", "snapshot_sha256"])
def test_mismatched_receipt_cannot_claim_approval(bound_workspace, field):
    _, _, _, record, client = bound_workspace
    decide(client, "approved")
    client.payload[field] = "b" * 64
    public = refresh(bound_workspace)
    assert public["receipt_status"] == "unavailable"
    assert public["manager_decision"] is None
    assert "receipt" not in record.portal_handoff


def test_other_owner_is_rejected_before_identity_or_receipt_lookup(bound_workspace):
    session, user, trip_id, record, client = bound_workspace
    before = deepcopy(record.portal_handoff)
    with pytest.raises(HTTPException) as rejected:
        refresh_workspace_proposal_portal_receipt(
            trip_id,
            Request({"type": "http", "app": create_app(portal_receipt_client=client)}),
            Response(),
            WorkspaceProposalHandoffRequest(),
            replace(user, user_id="another-local-account"),
            session,
        )
    assert rejected.value.status_code == 404
    assert client.users == [] and client.reads == 0
    assert record.portal_handoff == before


@pytest.mark.parametrize("field", ["namespace", "subject"])
def test_changed_identity_namespace_or_subject_does_not_read_receipt(bound_workspace, field):
    *_, client = bound_workspace
    client.identity = replace(client.identity, **{field: "different-owner"})
    public = refresh(bound_workspace)
    assert public["receipt_status"] == "unauthorized"
    assert client.reads == 0


def test_changed_prices_never_reuse_a_current_decision_even_on_reload(bound_workspace):
    session, user, trip_id, record, client = bound_workspace
    decide(client, "approved")
    refresh(bound_workspace)
    price = session.get(PersistedTripPrice, f"trip-price:{trip_id}:transport")
    assert price is not None
    price.amount += 1
    session.commit()
    public = get_workspace_proposal_payload(session, user=user, trip_id=trip_id)["proposal_state"][
        "portal_handoff"
    ]
    assert public["receipt_status"] == "stale"
    assert public["manager_decision"] is None
    assert public["last_manager_decision"] == "approved"
    public = refresh(bound_workspace)
    assert public["receipt_status"] == "stale"
    assert client.reads == 1
    assert record.portal_handoff["receipt"]["decision"] == "approved"


def test_unchanged_policy_refresh_preserves_receipt_and_decision(bound_workspace):
    session, _, _, record, client = bound_workspace
    decide(client, "rejected")
    refresh(bound_workspace)
    before = deepcopy(record.portal_handoff)
    _bind_portal_handoff_evaluation_snapshot(
        record=record, current_snapshot=deepcopy(before["source_snapshot"])
    )
    session.commit()
    assert record.portal_handoff == before


def test_legacy_preparation_cannot_erase_a_recorded_owner_bound_decision(bound_workspace):
    session, user, trip_id, record, client = bound_workspace
    decide(client, "approved")
    refresh(bound_workspace)
    before = deepcopy(record.portal_handoff)
    with pytest.raises(WorkspaceProposalHandoffNotReadyError):
        prepare_workspace_proposal_handoff(session, user=user, trip_id=trip_id)
    assert record.portal_handoff == before


@pytest.mark.parametrize(
    "state",
    [
        "bound_only",
        "prepared",
        "submitted",
        "pending_review",
        "approved",
        "rejected",
        "changes_requested",
    ],
)
@pytest.mark.parametrize("observation_available", [False, True], ids=["historical", "current"])
@pytest.mark.parametrize("portal_configured", [False, True])
def test_browser_handoff_route_preserves_authenticated_producer_state(
    bound_workspace, monkeypatch, state, observation_available, portal_configured
):
    session, user, trip_id, record, client = bound_workspace
    if state in {"approved", "rejected", "changes_requested"}:
        decide(client, state)
    elif state in {"submitted", "pending_review"}:
        client.payload.update(state=state, request_id="request-1", execution_id="execution-1")
        if state == "pending_review":
            client.payload.update(review_id="review-1", submitted_at="2026-10-10T12:10:00Z")
    if state != "bound_only":
        refresh(bound_workspace)
    if not observation_available:
        client.failure = PortalReceiptReadError("unavailable")
        refresh(bound_workspace)

    # Producer correlation must block the legacy form even before a first receipt
    # is observed, and after a failed read hides the current submission/decision.
    session.expire_all()
    before = deepcopy(record.portal_handoff)
    verdict = deepcopy(record.evaluation_record)
    public_before = get_workspace_proposal_payload(session, user=user, trip_id=trip_id)
    trip = session.get(PersistedTrip, trip_id)
    assert trip is not None
    trip_updated_at, proposal_updated_at = trip.updated_at, record.updated_at
    reads_before, users_before = client.reads, list(client.users)
    if not portal_configured:
        monkeypatch.delenv("TPP_PORTAL_BASE_URL", raising=False)
        monkeypatch.delenv("TPP_BASE_URL", raising=False)

    def unexpected_form(*args, **kwargs):
        pytest.fail("An owner-bound handoff must not regenerate the legacy browser form")

    monkeypatch.setattr("trip_planner.app.services.proposal.build_portal_fields", unexpected_form)
    for _ in range(2):
        with pytest.raises(HTTPException) as rejected:
            prepare_workspace_proposal_portal_handoff(
                trip_id=trip_id,
                _payload=WorkspaceProposalHandoffRequest(),
                response=Response(),
                user=user,
                db_session=session,
            )
        assert rejected.value.status_code == 409
        assert "handoff-1" not in rejected.value.detail
        assert "draft-1" not in rejected.value.detail
        session.expire_all()
        assert record.portal_handoff == before
        assert record.evaluation_record == verdict
        assert (trip.updated_at, record.updated_at) == (trip_updated_at, proposal_updated_at)
        assert get_workspace_proposal_payload(session, user=user, trip_id=trip_id) == public_before
        assert (client.reads, client.users) == (reads_before, users_before)


def test_absent_identity_bridge_returns_unknown_without_shared_service_fallback(bound_workspace):
    session, user, trip_id, _, client = bound_workspace
    result = refresh_workspace_portal_receipt(session, user=user, trip_id=trip_id, client=None)
    assert result["proposal_state"]["portal_handoff"]["receipt_status"] == "unavailable"
    assert client.reads == 0


def test_legacy_handoff_does_not_invent_a_producer_binding(saved_portal_handoff):
    session, user, trip_id, original = saved_portal_handoff
    client = ReceiptClient()
    result = refresh_workspace_portal_receipt(session, user=user, trip_id=trip_id, client=client)
    handoff = result["proposal_state"]["portal_handoff"]
    assert handoff["source_snapshot_hash"] == original["handoff"]["source_snapshot_hash"]
    assert handoff["receipt_status"] == "unavailable"
    assert handoff["manager_decision"] is None
    assert client.users == [] and client.reads == 0


def test_a_delayed_read_cannot_overwrite_a_newer_preparation(bound_workspace, monkeypatch):
    session, _user, _trip_id, record, client = bound_workspace
    decide(client, "approved")

    def replace_preparation(**kwargs):
        with get_session_factory()() as another_session:
            newer = another_session.get(PersistedProposalState, record.proposal_state_id)
            newer.portal_handoff = {
                **newer.portal_handoff,
                "producer_binding": {
                    **newer.portal_handoff["producer_binding"],
                    "draft_id": "new-draft",
                },
            }
            another_session.commit()
        return deepcopy(client.payload)

    monkeypatch.setattr(client, "read_receipt", replace_preparation)
    public = refresh(bound_workspace)
    assert public["manager_decision"] is None
    session.expire_all()
    assert record.portal_handoff["producer_binding"]["draft_id"] == "new-draft"
    assert "receipt" not in record.portal_handoff


def test_a_trip_changed_during_the_read_is_reported_as_stale(bound_workspace, monkeypatch):
    _session, _user, trip_id, record, client = bound_workspace
    decide(client, "approved")

    def change_price(**kwargs):
        with get_session_factory()() as another_session:
            price = another_session.get(PersistedTripPrice, f"trip-price:{trip_id}:transport")
            price.amount += 1
            another_session.commit()
        return deepcopy(client.payload)

    monkeypatch.setattr(client, "read_receipt", change_price)
    public = refresh(bound_workspace)
    assert public["receipt_status"] == "stale"
    assert public["manager_decision"] is None
    assert public["last_manager_decision"] == "approved"
    assert record.portal_handoff["receipt"]["decision"] == "approved"
