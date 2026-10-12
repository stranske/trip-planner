"""Atomically retain authenticated producer preparation before browser navigation."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from pydantic import ValidationError
from sqlalchemy import update
from sqlalchemy.orm import Session

from trip_planner.app.schemas.proposal import WorkspaceProposalReceiptHandoffResponse
from trip_planner.app.services.auth import AuthenticatedUser
from trip_planner.app.services.proposal import (
    WorkspaceProposalHandoffStaleError,
    _get_owned_trip_record,
    _portal_handoff_snapshot,
    _public_portal_handoff,
)
from trip_planner.app.services.trip_prices import read_trip_prices_for_owner
from trip_planner.integrations.tpp.client import TPPContractError
from trip_planner.integrations.tpp.portal_handoff import (
    portal_action_url,
    snapshot_hash,
)
from trip_planner.integrations.tpp.portal_receipt import (
    PortalBrowserSession,
    PortalReceiptBinding,
    validate_portal_preparation,
    validate_portal_receipt,
)
from trip_planner.integrations.tpp.portal_receipt_client import (
    OwnerPortalReceiptClient,
    PortalPreparationError,
)
from trip_planner.persistence.models.proposal import PersistedProposalState
from trip_planner.persistence.models.trip import PersistedTrip


def prepare_owner_portal_handoff(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    record: PersistedProposalState,
    trip_record: PersistedTrip,
    snapshot: dict[str, Any],
    fields: dict[str, str],
    client: OwnerPortalReceiptClient,
) -> dict[str, Any]:
    """Use saved facts only; producer validation must reject incomplete answers.

    The retry key derives from the server-owned trip and policy-bound snapshot,
    so a lost response can replay the same producer draft without a second write.
    A browser capability grants viewing only, never submission or approval.
    """
    stored = dict(record.portal_handoff or {})
    revision, record_id, trip_id = record.updated_at, record.proposal_state_id, record.trip_id
    source_hash = snapshot_hash(snapshot)
    identity = client.resolve_owner(user.user_id)
    owner = identity.owner_binding()
    origin = portal_action_url().removesuffix("/portal/handoff")
    if stored.get("producer_binding"):
        if stored.get("producer_owner") != owner or stored.get("producer_origin") != origin:
            raise PortalPreparationError(403)
        binding = PortalReceiptBinding.model_validate(stored["producer_binding"])
        if binding.snapshot_version != source_hash:
            raise WorkspaceProposalHandoffStaleError("The producer snapshot version changed.")
        previous = (
            validate_portal_receipt(stored["receipt"], binding=binding)
            if stored.get("receipt") is not None
            else None
        )
        receipt = validate_portal_receipt(
            client.read_receipt(identity=identity, binding=binding),
            binding=binding,
            previous=previous,
        )
    else:
        handoff_id = "planner:" + sha256(f"{trip_id}:{source_hash}".encode()).hexdigest()
        receipt = validate_portal_preparation(
            client.prepare_handoff(
                identity=identity,
                handoff_id=handoff_id,
                snapshot_version=source_hash,
                answers=fields,
            ),
            handoff_id=handoff_id,
            snapshot_version=source_hash,
        )
        binding = PortalReceiptBinding.model_validate(
            receipt.model_dump(include=set(PortalReceiptBinding.model_fields))
        )
    # Validate even injected client results; model_copy can bypass validation.
    try:
        browser = PortalBrowserSession.model_validate(
            client.create_browser_session(identity=identity, binding=binding)
        )
    except ValidationError:
        raise TPPContractError("Malformed TPP browser review capability.") from None
    if browser.draft_id != binding.draft_id:
        raise TPPContractError("TPP browser review does not match the prepared draft.")
    submission = "unknown" if receipt.state == "prepared" else receipt.state
    handoff = {
        **stored,
        "status": "prepared",
        "prepared_at": receipt.prepared_at.isoformat(),
        "producer_owner": owner,
        "producer_origin": origin,
        "producer_binding": binding.model_dump(),
        "receipt": receipt.model_dump(mode="json"),
        "receipt_status": "current",
        "receipt_observed_at": receipt.observed_at.isoformat(),
        "manager_submission_status": submission,
        "manager_decision": receipt.decision,
        "manager_decision_at": receipt.decision_at.isoformat() if receipt.decision_at else None,
        "last_manager_submission_status": submission,
        "last_manager_decision": receipt.decision,
        # Retain capability provenance, not the ephemeral bearer value.
        "browser_review": {
            "draft_id": browser.draft_id,
            "issued_at": datetime.now(UTC).isoformat(),
        },
    }
    result = WorkspaceProposalReceiptHandoffResponse.model_validate(
        {
            "action_url": f"{origin}/portal/handoff/receipt",
            "fields": {"handoff_token": browser.handoff_token.get_secret_value()},
            "handoff": _public_portal_handoff(handoff),
        }
    ).model_dump()
    # Network requests can overlap edits to trip facts or another preparation.
    # Reload before persisting so a capability for obsolete facts is never returned.
    db_session.expire_all()
    current_trip = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    current_snapshot = _portal_handoff_snapshot(
        record=record,
        trip_record=current_trip,
        user=user,
        trip_prices=read_trip_prices_for_owner(db_session, user_id=user.user_id, trip_id=trip_id),
    )
    if snapshot_hash(current_snapshot) != source_hash:
        raise WorkspaceProposalHandoffStaleError("Trip facts changed during portal preparation.")
    retained = db_session.execute(
        update(PersistedProposalState)
        .where(PersistedProposalState.proposal_state_id == record_id)
        .where(PersistedProposalState.updated_at == revision)
        .values(portal_handoff=handoff)
        .returning(PersistedProposalState.proposal_state_id)
        .execution_options(synchronize_session=False)
    ).scalar_one_or_none()
    if retained is None:
        db_session.rollback()
        raise WorkspaceProposalHandoffStaleError("The saved proposal changed during preparation.")
    trip_record.updated_at = datetime.now(UTC)
    db_session.commit()
    db_session.expire_all()
    return result
