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
    runtime_scenario_comparison: dict[str, Any] = Field(
        description="Comparison-ready runtime scenario payload derived from the current scenario search."
    )
    activity_log: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Recent persisted workspace activity entries tied to the trip/session trail.",
    )
    planner_memory: dict[str, Any] = Field(
        default_factory=dict,
        description="Persisted planner checkpoints and user-visible summarized memory.",
    )
    planner_panel_state: dict[str, Any] = Field(
        description="Workspace-scoped planner panel payload for the mounted side-panel UI.",
    )
    feasibility_summary: dict[str, Any] = Field(
        description="Structured feasibility and move-cost assessments derived from workspace inventory bundles.",
    )
    inventory_summary: dict[str, Any] = Field(
        description="Bundle summary assembled from normalized option/domain records for the workspace surface."
    )
    budget_state: dict[str, Any] = Field(
        default_factory=dict,
        description="Persisted budget plan, actual spend entries, and budget-vs-actual summary for the workspace.",
    )
    policy_state: dict[str, Any] | None = Field(
        default=None,
        description="Persisted policy constraint import and readiness summary for business-workspace flows.",
    )
    proposal_state: dict[str, Any] | None = Field(
        default=None,
        description="Persisted proposal submission and evaluation lifecycle state for business-workspace flows.",
    )


class ScenarioComparisonSurfaceResponse(BaseModel):
    trip_id: str
    title: str
    summary: str
    comparison_axes: list[dict[str, Any]] = Field(default_factory=list)
    lead_scenario_id: str | None = None
    scenarios: list[dict[str, Any]] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)


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
