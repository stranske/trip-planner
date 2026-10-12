from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceProposalSubmissionRequest(BaseModel):
    proposal: dict[str, Any] = Field(
        description="Serialized TripPlanProposal payload to persist for the workspace."
    )
    request: dict[str, Any] = Field(
        description="Serialized TPPRequestEnvelope payload used to submit the proposal."
    )
    response: dict[str, Any] | None = Field(
        default=None,
        description="Optional serialized TPPResponseEnvelope payload, accepted only when the explicit test fixture switch is enabled.",
    )
    proposal_version: str = Field(min_length=1, max_length=96)
    scenario_id: str | None = Field(default=None, max_length=96)


class WorkspaceProposalSubmitRequest(BaseModel):
    """All the traveller supplies: which scenario, if they have chosen one."""

    scenario_id: str | None = Field(default=None, max_length=96)


class WorkspaceProposalEvaluationRequest(BaseModel):
    request: dict[str, Any] = Field(
        description="Serialized TPPRequestEnvelope payload used to ingest evaluation state."
    )
    response: dict[str, Any] | None = Field(
        default=None,
        description="Optional serialized TPPResponseEnvelope payload, accepted only when the explicit test fixture switch is enabled.",
    )
    proposal_version: str = Field(min_length=1, max_length=96)
    scenario_id: str | None = Field(default=None, max_length=96)


class WorkspaceProposalSelectedAlternative(BaseModel):
    category: str | None = Field(default=None, min_length=1, max_length=64)
    summary: str | None = Field(default=None, min_length=1, max_length=280)
    rationale: str | None = Field(default=None, min_length=1, max_length=280)
    comparable_ref: str | None = Field(default=None, min_length=1, max_length=96)


class WorkspaceProposalExceptionRequest(BaseModel):
    exception_type: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=1, max_length=280)
    requested_approval_roles: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class WorkspaceProposalFollowUpRequest(BaseModel):
    status: Literal[
        "awaiting_evaluation",
        "reoptimization_required",
        "reoptimized",
        "exception_required",
        "exception_requested",
        "approval_pending",
        "resolved",
    ]
    summary: str = Field(min_length=1, max_length=280)
    title: str | None = Field(default=None, min_length=1, max_length=120)
    notes: list[str] = Field(default_factory=list)
    selected_alternative: WorkspaceProposalSelectedAlternative | None = None
    requested_exception: WorkspaceProposalExceptionRequest | None = None


class WorkspaceProposalReoptimizeRequest(BaseModel):
    comparable_refs: dict[str, list[str]] = Field(default_factory=dict)
    justification_refs: dict[str, list[str]] = Field(default_factory=dict)


class WorkspaceProposalResponse(BaseModel):
    proposal_state: dict[str, Any] | None = None
    summary: dict[str, Any] = Field(default_factory=dict)


class WorkspaceProposalHandoffRequest(BaseModel):
    """A JSON-only same-origin request; all handoff facts are resolved server-side."""

    model_config = ConfigDict(extra="forbid")


class WorkspaceProposalHandoffMetadata(BaseModel):
    """Public preparation metadata; bound source facts stay in server storage."""

    model_config = ConfigDict(extra="ignore")

    schema_version: Literal["tpp-portal-handoff/v1"]
    source_snapshot_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    prepared_at: str
    status: Literal["prepared"]
    manager_submission_status: Literal["unknown"]
    manager_decision: None = None


class WorkspaceProposalHandoffResponse(BaseModel):
    action_url: str
    method: Literal["POST"] = "POST"
    # Only server-owned prefill facts may leave in the native form. In particular,
    # internal snapshots and traveler-completed portal fields are not this contract.
    fields: dict[
        Literal[
            "traveler_name",
            "business_purpose",
            "city_state",
            "depart_date",
            "return_date",
            "notes",
            "departure_city_airport",
            "flight_pref_outbound.roundtrip_cost",
            "selected_fare",
            "flight_cost",
            "lowest_cost_roundtrip",
            "lowest_fare",
            "cabin_class",
            "flight_duration_hours",
            "fare_evidence_attached",
        ],
        str,
    ] = Field(min_length=1)
    handoff: WorkspaceProposalHandoffMetadata


class WorkspaceProposalReceiptHandoffMetadata(BaseModel):
    """Metadata from a validated owner-authenticated producer observation."""

    schema_version: Literal["tpp-portal-handoff/v1"]
    source_snapshot_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    prepared_at: str
    status: Literal["prepared"]
    receipt_status: Literal["current"]
    receipt_observed_at: str
    manager_submission_status: Literal[
        "unknown", "submitted", "pending_review", "decision_recorded"
    ]
    manager_decision: Literal["approved", "rejected", "changes_requested"] | None
    manager_decision_at: str | None
    last_manager_submission_status: str
    last_manager_decision: Literal["approved", "rejected", "changes_requested"] | None


class WorkspaceProposalReceiptHandoffResponse(BaseModel):
    """Short-lived native form for the producer's saved, owner-bound review."""

    action_url: str
    method: Literal["POST"] = "POST"
    fields: dict[Literal["handoff_token"], str] = Field(min_length=1, max_length=1)
    handoff: WorkspaceProposalReceiptHandoffMetadata
