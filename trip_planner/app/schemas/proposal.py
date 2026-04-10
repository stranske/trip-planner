from typing import Any, Literal

from pydantic import BaseModel, Field


class WorkspaceProposalSubmissionRequest(BaseModel):
    proposal: dict[str, Any] = Field(
        description="Serialized TripPlanProposal payload to persist for the workspace."
    )
    request: dict[str, Any] = Field(
        description="Serialized TPPRequestEnvelope payload used to submit the proposal."
    )
    response: dict[str, Any] = Field(
        description="Serialized TPPResponseEnvelope payload returned by proposal submission."
    )
    proposal_version: str = Field(min_length=1, max_length=96)
    scenario_id: str | None = Field(default=None, max_length=96)


class WorkspaceProposalEvaluationRequest(BaseModel):
    request: dict[str, Any] = Field(
        description="Serialized TPPRequestEnvelope payload used to ingest evaluation state."
    )
    response: dict[str, Any] = Field(
        description="Serialized TPPResponseEnvelope payload returned by evaluation ingestion."
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


class WorkspaceProposalResponse(BaseModel):
    proposal_state: dict[str, Any] | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
