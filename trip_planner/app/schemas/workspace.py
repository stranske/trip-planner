from typing import Any, Literal

from pydantic import BaseModel, Field


class InventoryRuntimeIssue(BaseModel):
    issue_id: str | None = None
    stage: str | None = None
    severity: str | None = None
    code: str | None = None
    message: str | None = None
    reason: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    affected_record_ids: list[str] = Field(default_factory=list)


class InventoryRuntimeState(BaseModel):
    status: str = Field(description="Runtime readiness status for inventory assembly.")
    title: str = Field(description="Short runtime readiness heading.")
    summary: str = Field(description="Human-readable runtime readiness summary.")
    issues: list[InventoryRuntimeIssue] = Field(
        default_factory=list,
        description="Adapter and runtime issues describing missing inputs or blocked inventory reads.",
    )


class InventorySummary(BaseModel):
    bundle_count: int = Field(description="Number of assembled inventory bundles.")
    bundles: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Inventory bundle previews derived from persisted runtime context.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Inventory assembly notes for current workspace readiness.",
    )
    runtime_state: InventoryRuntimeState = Field(
        description="Runtime state details including AdapterIssue-derived issue entries."
    )
    source_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Source and provenance metadata for the runtime inventory assembly path.",
    )


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
    ranking: dict[str, Any] = Field(
        description="Top-level scenario-ranking payload derived from the current scenario search."
    )
    route_comparison: dict[str, Any] = Field(
        description=(
            "Canonical comparison-ready route payload derived from the current scenario search."
        )
    )
    runtime_scenario_comparison: dict[str, Any] = Field(
        description=(
            "Compatibility alias for route_comparison retained for existing workspace clients."
        )
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
    runtime_state: dict[str, Any] = Field(
        description="Top-level runtime readiness summary for the workspace surface.",
    )
    feasibility_summary: dict[str, Any] = Field(
        description="Structured feasibility and move-cost assessments derived from workspace inventory bundles.",
    )
    inventory_summary: InventorySummary = Field(
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


class PlanningModeUpdateRequest(BaseModel):
    planning_mode: str = Field(min_length=1, max_length=32)
