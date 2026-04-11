from typing import Any

from pydantic import BaseModel, Field


class PlannerTurnRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class PlannerMessageResponse(BaseModel):
    message_id: str
    role: str
    content: str
    created_at: str
    refs: list[str] = Field(default_factory=list)


class PlannerSessionResponse(BaseModel):
    trip_id: str
    session_state_id: str
    conversation_id: str
    resumed_at: str | None = None
    session: dict[str, Any]
    planner_panel_state: dict[str, Any]
    activity_log: list[dict[str, Any]] = Field(default_factory=list)
    messages: list[PlannerMessageResponse] = Field(default_factory=list)

