from typing import Any

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


class WorkspaceProposalResponse(BaseModel):
    proposal_state: dict[str, Any] | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
