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


class WorkspaceUserSummary(BaseModel):
    """User-facing trip summary for the product workspace surface.

    Field values must avoid raw runtime/provider/object-id language; that
    detail belongs in :class:`WorkspaceDebugState` and is rendered behind an
    explicit debug affordance.
    """

    trip_title: str = Field(description="Human-readable trip title.")
    trip_mode: Literal["leisure", "business"] = Field(
        description="Workspace product mode used to gate user-facing copy."
    )
    mode_label: str = Field(description="User-friendly mode label (e.g. 'Leisure trip').")
    status: Literal["ready", "partial", "empty"] = Field(
        description="High-level workspace status used for top-level framing."
    )
    headline: str = Field(description="Short user-facing headline for the trip.")
    decided: list[str] = Field(
        default_factory=list,
        description="User-facing 'what has been decided' bullet list.",
    )
    uncertain: list[str] = Field(
        default_factory=list,
        description="User-facing 'what is still uncertain' bullet list.",
    )


class WorkspaceNextStep(BaseModel):
    """Recommended next user action for the trip workspace."""

    title: str = Field(description="Short next-step title in user language.")
    summary: str = Field(description="Longer next-step summary in user language.")
    action_label: str | None = Field(
        default=None,
        description="Optional CTA label rendered alongside the next-step copy.",
    )
    action_target: str | None = Field(
        default=None,
        description="Optional anchor or route hint for the recommended action.",
    )
    blocked: bool = Field(
        default=False,
        description="True when the recommended action is blocked on a missing input.",
    )


class WorkspaceBusinessSummary(BaseModel):
    """Optional business-mode approval readiness expressed in user language."""

    approval_status: Literal[
        "not_applicable",
        "not_ready",
        "in_review",
        "approved",
        "needs_attention",
    ] = Field(description="Approval readiness in user-facing terms.")
    headline: str = Field(description="Short user-facing approval headline.")
    blockers: list[str] = Field(
        default_factory=list,
        description="User-facing list of open approval blockers.",
    )


class WorkspacePanelVisibility(BaseModel):
    """Mode-aware rules for normal workspace panels."""

    show_budget_panel: bool = True
    show_policy_posture: bool = False
    show_proposal_panel: bool = False
    show_approval_readiness_panel: bool = False


class WorkspacePolicyPresentation(BaseModel):
    """User-facing policy/proposal state labels for the normal workspace."""

    active_policy_state: bool = False
    posture_label: str = "Not applicable"
    approval_status_label: str = "Not applicable"
    next_step_label: str = "No policy action needed"
    summary: str = "Policy approval is not part of this workspace yet."


class WorkspaceDebugSection(BaseModel):
    """A named debug-only payload section that mirrors raw runtime state."""

    title: str = Field(description="Debug section title shown in the advanced surface.")
    payload: Any = Field(
        default_factory=dict,
        description="Raw payload attached to this debug section.",
    )


class WorkspaceDebugState(BaseModel):
    """Hidden debug surface containing raw runtime/provider/object-id payloads.

    The product workspace view should only render this state behind an
    explicit debug/advanced affordance.
    """

    sections: dict[str, WorkspaceDebugSection] = Field(
        default_factory=dict,
        description="Named raw debug sections keyed by stable section id.",
    )


class WorkspaceViewModel(BaseModel):
    """Typed product view model that translates :class:`WorkspaceResponse`.

    The view model splits the workspace payload into traveler-facing,
    business-facing, and debug-facing sections so the frontend can render a
    stable user surface without leaking raw runtime detail.
    """

    user_summary: WorkspaceUserSummary
    next_step: WorkspaceNextStep
    panel_visibility: WorkspacePanelVisibility = Field(default_factory=WorkspacePanelVisibility)
    policy_presentation: WorkspacePolicyPresentation = Field(
        default_factory=WorkspacePolicyPresentation
    )
    business_summary: WorkspaceBusinessSummary | None = None
    debug_state: WorkspaceDebugState


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
    view_model: WorkspaceViewModel | None = Field(
        default=None,
        description=(
            "Typed product workspace view model with user-facing summary, next-step,"
            " optional business-summary, and hidden debug sections."
        ),
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


class RouteOptionActionRequest(BaseModel):
    action_type: Literal["make_baseline", "keep", "reject", "reopen", "revise"]


class PlanningModeUpdateRequest(BaseModel):
    planning_mode: str = Field(min_length=1, max_length=32)
