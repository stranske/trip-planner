from typing import Any

from pydantic import BaseModel, Field


class PlannerToolCallRequest(BaseModel):
    tool_name: str = Field(min_length=1, max_length=80)
    arguments: dict[str, Any] = Field(default_factory=dict)


class PlannerTurnRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    tool_calls: list[PlannerToolCallRequest] = Field(default_factory=list)


class PlannerToolCallResponse(BaseModel):
    tool_name: str
    status: str
    summary: str
    mutates_state: bool
    refs: list[str] = Field(default_factory=list)
    output: dict[str, Any] = Field(default_factory=dict)


class PlannerMessageResponse(BaseModel):
    message_id: str
    role: str
    content: str
    created_at: str
    refs: list[str] = Field(default_factory=list)
    tool_calls: list[PlannerToolCallResponse] = Field(default_factory=list)


class PlannerCheckpointResponse(BaseModel):
    checkpoint_id: str
    checkpoint_kind: str
    turn_index: int
    message_count: int
    summary: str
    source_message_ids: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class PlannerMemoryArtifactResponse(BaseModel):
    memory_artifact_id: str
    checkpoint_id: str | None = None
    artifact_kind: str
    title: str
    summary: str
    detail: str
    source_message_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class PlannerMemoryResponse(BaseModel):
    current_checkpoint_id: str | None = None
    checkpoints: list[PlannerCheckpointResponse] = Field(default_factory=list)
    artifacts: list[PlannerMemoryArtifactResponse] = Field(default_factory=list)


class PlannerSessionResponse(BaseModel):
    trip_id: str
    session_state_id: str
    conversation_id: str
    resumed_at: str | None = None
    runtime: dict[str, Any] = Field(default_factory=dict)
    session: dict[str, Any]
    planner_panel_state: dict[str, Any]
    planner_memory: PlannerMemoryResponse
    available_tools: list[dict[str, Any]] = Field(default_factory=list)
    activity_log: list[dict[str, Any]] = Field(default_factory=list)
    messages: list[PlannerMessageResponse] = Field(default_factory=list)
