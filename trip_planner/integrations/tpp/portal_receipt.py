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


class PortalPreparationRequest(BaseModel):
    """Server-selected retry identity and complete, privately transported answers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    handoff_id: Identifier
    snapshot_version: Identifier
    answers: dict[
        Annotated[str, Field(strict=True, min_length=1, max_length=100)],
        Annotated[str, Field(strict=True, max_length=4096)],
    ] = Field(max_length=80)


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

    # Parsed transport models can contain unvalidated model_copy/model_construct
    # values. Recheck their fields before treating them as persisted evidence.
    model_config = ConfigDict(revalidate_instances="always")

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


def _validate_observation_history(receipt: TPPPortalReceipt, previous: TPPPortalReceipt) -> None:
    """Keep fixed preparation/submission evidence while accepting later decisions."""

    persisted_fields = ("prepared_at", "request_id", "execution_id", "review_id", "submitted_at")
    changed_evidence = any(
        getattr(previous, key) is not None and getattr(receipt, key) != getattr(previous, key)
        for key in persisted_fields
    )
    changed_decision = previous.decision_at is not None and (
        receipt.decision_at is None
        or receipt.decision_at < previous.decision_at
        or (receipt.decision_at == previous.decision_at and receipt.decision != previous.decision)
    )
    if receipt.observed_at < previous.observed_at or changed_evidence or changed_decision:
        raise TPPContractError("TPP portal receipt conflicts with the previous observation.")


def validate_portal_preparation(
    payload: Any,
    *,
    handoff_id: str,
    snapshot_version: str,
) -> TPPPortalReceipt:
    """Establish producer correlation from the owner's initial preparation response.

    The caller retains its server-selected retry key and version before the
    authenticated request. Only TPP knows the resulting draft ID and normalized
    answer digest; retain those from this validated response for later reads.
    A retry may already contain authoritative submission or decision evidence.
    Once the binding is saved, use receipt validation to enforce that binding
    and the previous observation on subsequent retries and reads.
    """

    receipt = _parse_portal_receipt(payload)
    if receipt.handoff_id != handoff_id or receipt.snapshot_version != snapshot_version:
        raise TPPContractError("TPP portal preparation does not match the requested snapshot.")
    return receipt


def _parse_portal_receipt(payload: Any) -> TPPPortalReceipt:
    try:
        return TPPPortalReceipt.model_validate(payload)
    except ValidationError:
        # Validation errors can include raw response data. Do not propagate that
        # data across the public/logging boundary, even on malformed responses.
        raise TPPContractError("Malformed TPP portal receipt contract.") from None


def validate_portal_receipt(
    payload: Any,
    *,
    binding: PortalReceiptBinding,
    previous: TPPPortalReceipt | None = None,
) -> TPPPortalReceipt:
    """Reject malformed or mismatched observations without exposing response contents.

    A caller must handle failed/unavailable reads separately; they never produce
    a successful observation here. Retain the last validated owner-authenticated
    receipt as ``previous`` when polling the same preparation, so stale responses
    cannot overwrite newer evidence. This function grants no read/write authority.
    """

    receipt = _parse_portal_receipt(payload)
    if any(
        getattr(receipt, key) != getattr(binding, key)
        for key in ("handoff_id", "snapshot_version", "snapshot_sha256", "draft_id")
    ):
        raise TPPContractError("TPP portal receipt does not match the prepared snapshot.")
    if previous is not None:
        # Recheck both the contract and binding: model_copy can bypass Pydantic
        # validation, and history from another handoff cannot establish freshness.
        validated_previous = validate_portal_receipt(previous.model_dump(), binding=binding)
        _validate_observation_history(receipt, validated_previous)
    return receipt
