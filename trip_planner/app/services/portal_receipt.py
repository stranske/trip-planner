"""Refresh a workspace's retained, owner-bound producer receipt."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError
from sqlalchemy import update
from sqlalchemy.orm import Session

from trip_planner.app.services.auth import AuthenticatedUser
from trip_planner.app.services.proposal import (
    WorkspaceProposalHandoffNotReadyError,
    _get_latest_proposal_state,
    _get_owned_trip_record,
    _portal_handoff_snapshot,
    get_workspace_proposal_payload,
)
from trip_planner.app.services.trip_prices import read_trip_prices_for_owner
from trip_planner.integrations.tpp.client import TPPTransportError
from trip_planner.integrations.tpp.portal_handoff import (
    portal_action_url,
    snapshot_hash,
)
from trip_planner.integrations.tpp.portal_receipt import (
    PortalReceiptBinding,
    validate_portal_receipt,
)
from trip_planner.integrations.tpp.portal_receipt_client import (
    OwnerPortalReceiptClient,
    PortalReceiptReadError,
)
from trip_planner.persistence.models.proposal import PersistedProposalState


def refresh_workspace_portal_receipt(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    client: OwnerPortalReceiptClient | None,
    submit: bool = False,
) -> dict[str, Any]:
    """Observe only the exact preparation retained for this traveler and trip.

    The preparation integration must retain producer_binding and producer_owner
    from its authenticated creation response. Browser-supplied IDs cannot create
    that authority. Until those exist, this route cannot claim receipt evidence.
    """

    trip = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    record = _get_latest_proposal_state(db_session, trip_id=trip_id, user_id=user.user_id)
    if record is None or not record.portal_handoff:
        raise WorkspaceProposalHandoffNotReadyError("Prepare an owner-bound portal handoff first.")
    stored = dict(record.portal_handoff)
    retained_revision = record.updated_at
    observation_status = "unavailable"
    receipt = None
    current_snapshot = _portal_handoff_snapshot(
        record=record,
        trip_record=trip,
        user=user,
        trip_prices=read_trip_prices_for_owner(db_session, user_id=user.user_id, trip_id=trip_id),
    )
    if snapshot_hash(current_snapshot) != stored.get("source_snapshot_hash"):
        observation_status = "stale"
    elif client is not None and stored.get("producer_binding") and stored.get("producer_owner"):
        try:
            binding = PortalReceiptBinding.model_validate(stored["producer_binding"])
            identity = client.resolve_owner(user.user_id)
            origin = stored.get("producer_origin")
            if identity.owner_binding() != stored["producer_owner"] or (
                origin is not None and origin != portal_action_url().removesuffix("/portal/handoff")
            ):
                observation_status = "unauthorized"
            else:
                previous = (
                    validate_portal_receipt(stored["receipt"], binding=binding)
                    if stored.get("receipt") is not None
                    else None
                )
                if submit and (previous is None or previous.state == "prepared"):
                    client.submit_request(identity=identity, binding=binding)
                receipt = validate_portal_receipt(
                    client.read_receipt(identity=identity, binding=binding),
                    binding=binding,
                    previous=previous,
                )
                observation_status = "current"
        except PortalReceiptReadError as failure:
            observation_status = failure.observation_status
        except (TPPTransportError, ValidationError):
            observation_status = "unavailable"

    updated = {**stored, "receipt_status": observation_status}
    if receipt is not None:
        submission = "unknown" if receipt.state == "prepared" else receipt.state
        updated.update(
            receipt=receipt.model_dump(mode="json"),
            receipt_observed_at=receipt.observed_at.isoformat(),
            manager_submission_status=submission,
            manager_decision=receipt.decision,
            manager_decision_at=receipt.decision_at.isoformat() if receipt.decision_at else None,
            last_manager_submission_status=submission,
            last_manager_decision=receipt.decision,
        )
    else:
        # Preserve the last validated observation privately and label its public
        # values as historical. Failed/stale reads do not establish today's state.
        updated.update(manager_submission_status="unknown", manager_decision=None)
    # A slow upstream read must not overwrite a newer preparation or observation.
    # updated_at is changed by every write to this proposal record; comparing it
    # also works on the supported JSON (rather than JSONB) database columns.
    db_session.execute(
        update(PersistedProposalState)
        .where(PersistedProposalState.proposal_state_id == record.proposal_state_id)
        .where(PersistedProposalState.updated_at == retained_revision)
        .values(portal_handoff=updated)
        .execution_options(synchronize_session=False)
    )
    db_session.commit()
    db_session.expire_all()
    return get_workspace_proposal_payload(db_session, user=user, trip_id=trip_id)
