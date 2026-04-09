from typing import Any, Literal

from pydantic import BaseModel, Field


class PolicySyncImportRequest(BaseModel):
    request: dict[str, Any] = Field(
        description="Serialized TPPRequestEnvelope payload used to fetch policy constraints."
    )
    response: dict[str, Any] = Field(
        description="Serialized TPPResponseEnvelope payload returned by the policy sync source."
    )
    source_kind: Literal["tpp_sync", "manual_import"] = "tpp_sync"
    tags: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class WorkspacePolicyResponse(BaseModel):
    policy_state: dict[str, Any] | None = None
    proposal: dict[str, Any] | None = None
    policy_evaluation: dict[str, Any] | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
