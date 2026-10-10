"""Validate owner-authenticated TPP observations before interpreting receipt state.

This is a response contract, not authentication. Callers must obtain the receipt
through the owner's trusted server-side transport and retain the binding from
preparation. Browser input and shared service identity cannot authorize a read.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

from trip_planner.integrations.tpp.client import TPPContractError

Identifier = Annotated[str, Field(strict=True, pattern=r"^[A-Za-z0-9_.:-]{1,80}$")]
SnapshotDigest = Annotated[str, Field(strict=True, pattern=r"^[0-9a-f]{64}$")]


class PortalReceiptBinding(BaseModel):
    """Server-retained correlation for an immutable prepared producer draft.

    The producer hashes its normalized complete answers. That digest is distinct
    from trip-planner's source_snapshot_hash and must never be substituted for it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    handoff_id: Identifier
    snapshot_version: Identifier
    snapshot_sha256: SnapshotDigest
    draft_id: Identifier


class TPPPortalReceipt(PortalReceiptBinding):
    """The portal-receipt/v1 metadata emitted by the accepted TPP producer."""

    contract_version: Literal["portal-receipt/v1"]
    state: Literal["prepared", "submitted", "pending_review", "decision_recorded"]
    prepared_at: AwareDatetime
    observed_at: AwareDatetime
    request_id: Identifier | None
    execution_id: Identifier | None
    review_id: Identifier | None
    submitted_at: AwareDatetime | None
    decision: Literal["approved", "rejected", "changes_requested"] | None
    decision_at: AwareDatetime | None

    @model_validator(mode="after")
    def require_persisted_evidence(self) -> Self:
        if self.prepared_at > self.observed_at:
            raise ValueError("Preparation cannot follow the receipt observation.")
        evidence = (
            self.request_id,
            self.execution_id,
            self.review_id,
            self.submitted_at,
            self.decision,
            self.decision_at,
        )
        if self.state == "prepared":
            if any(value is not None for value in evidence):
                raise ValueError("A prepared receipt cannot claim submission or decision evidence.")
            return self

        if self.request_id is None or self.execution_id is None:
            raise ValueError("Submission requires recorded request and execution identifiers.")
        if self.state == "submitted":
            if any(value is not None for value in evidence[2:]):
                raise ValueError("A submitted receipt cannot claim manager-review evidence.")
            return self

        if self.review_id is None or self.submitted_at is None:
            raise ValueError("Manager-review state requires a recorded review and submission time.")
        if not self.prepared_at <= self.submitted_at <= self.observed_at:
            raise ValueError("Submission time must fall within the observed receipt lifetime.")
        if self.state == "pending_review":
            if self.decision is not None or self.decision_at is not None:
                raise ValueError("Pending review cannot claim a recorded decision.")
        elif self.decision is None or self.decision_at is None:
            raise ValueError("A recorded decision requires its actual value and timestamp.")
        elif not self.submitted_at <= self.decision_at <= self.observed_at:
            raise ValueError("Decision time must follow submission and precede observation.")
        return self


def validate_portal_receipt(payload: Any, *, binding: PortalReceiptBinding) -> TPPPortalReceipt:
    """Reject malformed or mismatched observations without exposing response contents.

    A caller must handle failed/unavailable reads separately; they never produce
    a successful observation here. This function grants no read/write authority.
    """

    try:
        receipt = TPPPortalReceipt.model_validate(payload)
    except ValidationError:
        # Validation errors can include raw response data. Do not propagate that
        # data across the public/logging boundary, even on malformed responses.
        raise TPPContractError("Malformed TPP portal receipt contract.") from None
    if any(
        getattr(receipt, key) != getattr(binding, key)
        for key in ("handoff_id", "snapshot_version", "snapshot_sha256", "draft_id")
    ):
        raise TPPContractError("TPP portal receipt does not match the prepared snapshot.")
    return receipt
