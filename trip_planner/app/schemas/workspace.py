from typing import Any, Literal

from pydantic import BaseModel, Field


class WorkspaceResponse(BaseModel):
    trip_record: dict[str, Any] = Field(
        description="Persisted trip record payload for the workspace."
    )
    session: dict[str, Any] = Field(
        description="Current planning session payload for the workspace."
    )
    saved_scenarios: list[dict[str, Any]] = Field(
        description="Persisted saved-scenario records associated with the trip."
    )
    scenario_comparison: dict[str, Any] | None = Field(
        default=None,
        description="Latest scenario comparison metadata when available.",
    )
    scenario_search: dict[str, Any] = Field(
        description="ScenarioSearchResult payload whose route_sequence drives the timeline UI.",
    )
    activity_log: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Recent persisted workspace activity entries tied to the trip/session trail.",
    )
    planner_panel_state: dict[str, Any] = Field(
        description="Workspace-scoped planner panel payload for the mounted side-panel UI.",
    )
    inventory_summary: dict[str, Any] = Field(
        description="Bundle summary assembled from normalized option/domain records for the workspace surface."
    )


class PlannerDecisionAnswerRequest(BaseModel):
    choice: str = Field(min_length=1, max_length=160)


class PlannerOptionFeedbackRequest(BaseModel):
    action_type: Literal[
        "accept",
        "reject",
        "revise",
        "save_as_fallback",
        "do_more_before_asking_again",
    ]
    decision_id: str | None = Field(default=None, max_length=96)
