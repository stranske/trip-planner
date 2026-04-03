"""In-trip monitoring and replanning scaffolds built on shared orchestration contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any

from trip_planner.contracts._validators import (
    require_non_empty,
    require_optional_non_empty,
    require_string_mapping,
    require_strings,
)
from trip_planner.state import (
    ActivityLogEvent,
    PendingDecision as SessionPendingDecision,
    PlanningSessionState,
)

from .models import (
    DecisionOption,
    NextStepSummary,
    PendingDecision,
    PlannerAction,
    PlannerOutput,
    PlannerTurn,
    WorkflowStateSnapshot,
    WorkflowTransition,
)

TRIGGER_KINDS: tuple[str, ...] = (
    "closure",
    "delay",
    "fatigue_shift",
    "budget_drift",
    "preference_change",
    "weather",
)
TRIGGER_SEVERITIES: tuple[str, ...] = (
    "informational",
    "advisory",
    "disruptive",
    "critical",
)
CHANGE_SCOPES: tuple[str, ...] = (
    "local_stop",
    "day_segment",
    "full_day",
    "trip_wide",
)
REPLANNING_KINDS: tuple[str, ...] = (
    "ignore",
    "rerank",
    "scenario_revision",
    "emergency_fallback",
)
REVISION_OUTPUT_KINDS: tuple[str, ...] = (
    "status_note",
    "reranked_options",
    "scenario_revision",
    "emergency_fallback",
)


def _require_string_list(values: list[str], field_name: str) -> None:
    if isinstance(values, str) or not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list of strings")
    require_strings(values, field_name)


def _require_unique_strings(values: list[str], field_name: str) -> None:
    _require_string_list(values, field_name)
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} cannot contain duplicates")


def _payload_list(payload: dict[str, Any], field_name: str, default: list[Any]) -> list[Any]:
    value = payload.get(field_name, default)
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    return list(value)


def _payload_mapping(
    payload: dict[str, Any], field_name: str, default: dict[str, Any]
) -> dict[str, Any]:
    value = payload.get(field_name, default)
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a mapping")
    return dict(value)


def _compact_refs(*values: str | None) -> list[str]:
    refs = [value for value in values if value]
    return list(dict.fromkeys(refs))


@dataclass(slots=True)
class InTripAdjustmentContext:
    """Typed inputs required to route one in-trip change event."""

    session_state: PlanningSessionState
    scenario_search_id: str
    generated_at: str
    ranked_result_set_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.session_state, PlanningSessionState):
            raise ValueError("session_state must be a PlanningSessionState")
        require_non_empty(self.scenario_search_id, "scenario_search_id")
        require_non_empty(self.generated_at, "generated_at")
        require_optional_non_empty(self.ranked_result_set_id, "ranked_result_set_id")
        if self.session_state.current_saved_scenario_id is None:
            raise ValueError(
                "session_state.current_saved_scenario_id is required for in-trip routing"
            )


@dataclass(slots=True)
class InTripTriggerEvent:
    """Structured in-trip event that may or may not require replanning."""

    trigger_event_id: str
    trip_id: str
    session_state_id: str
    trigger_kind: str
    severity: str
    change_scope: str
    observed_at: str
    summary: str
    actor: str = "user"
    source: str = "traveler"
    trigger_codes: list[str] = field(default_factory=list)
    affected_option_ids: list[str] = field(default_factory=list)
    affected_checkpoint_id: str | None = None
    affected_saved_scenario_id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.trigger_event_id, "trigger_event_id")
        require_non_empty(self.trip_id, "trip_id")
        require_non_empty(self.session_state_id, "session_state_id")
        require_non_empty(self.observed_at, "observed_at")
        require_non_empty(self.summary, "summary")
        require_non_empty(self.actor, "actor")
        require_non_empty(self.source, "source")
        if self.trigger_kind not in TRIGGER_KINDS:
            raise ValueError(f"trigger_kind must be one of {TRIGGER_KINDS}")
        if self.severity not in TRIGGER_SEVERITIES:
            raise ValueError(f"severity must be one of {TRIGGER_SEVERITIES}")
        if self.change_scope not in CHANGE_SCOPES:
            raise ValueError(f"change_scope must be one of {CHANGE_SCOPES}")
        _require_unique_strings(self.trigger_codes, "trigger_codes")
        _require_unique_strings(self.affected_option_ids, "affected_option_ids")
        require_optional_non_empty(self.affected_checkpoint_id, "affected_checkpoint_id")
        require_optional_non_empty(
            self.affected_saved_scenario_id,
            "affected_saved_scenario_id",
        )
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a mapping")
        require_string_mapping(self.metadata, "metadata")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "InTripTriggerEvent":
        return cls(
            trigger_event_id=payload["trigger_event_id"],
            trip_id=payload["trip_id"],
            session_state_id=payload["session_state_id"],
            trigger_kind=payload["trigger_kind"],
            severity=payload["severity"],
            change_scope=payload["change_scope"],
            observed_at=payload["observed_at"],
            summary=payload["summary"],
            actor=payload.get("actor", "user"),
            source=payload.get("source", "traveler"),
            trigger_codes=_payload_list(payload, "trigger_codes", []),
            affected_option_ids=_payload_list(payload, "affected_option_ids", []),
            affected_checkpoint_id=payload.get("affected_checkpoint_id"),
            affected_saved_scenario_id=payload.get("affected_saved_scenario_id"),
            metadata=_payload_mapping(payload, "metadata", {}),
        )


@dataclass(slots=True)
class ReplanningRequest:
    """Structured request for the next in-trip routing step."""

    request_id: str
    trip_id: str
    session_state_id: str
    requested_at: str
    replanning_kind: str
    summary: str
    trigger_event_id: str
    based_on_saved_scenario_id: str
    scenario_search_id: str
    ranked_result_set_id: str | None = None
    checkpoint_id: str | None = None
    affected_option_ids: list[str] = field(default_factory=list)
    warning_codes: list[str] = field(default_factory=list)
    requires_user_confirmation: bool = False
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.request_id, "request_id")
        require_non_empty(self.trip_id, "trip_id")
        require_non_empty(self.session_state_id, "session_state_id")
        require_non_empty(self.requested_at, "requested_at")
        require_non_empty(self.summary, "summary")
        require_non_empty(self.trigger_event_id, "trigger_event_id")
        require_non_empty(self.based_on_saved_scenario_id, "based_on_saved_scenario_id")
        require_non_empty(self.scenario_search_id, "scenario_search_id")
        require_optional_non_empty(self.ranked_result_set_id, "ranked_result_set_id")
        require_optional_non_empty(self.checkpoint_id, "checkpoint_id")
        if self.replanning_kind not in REPLANNING_KINDS:
            raise ValueError(f"replanning_kind must be one of {REPLANNING_KINDS}")
        _require_unique_strings(self.affected_option_ids, "affected_option_ids")
        _require_unique_strings(self.warning_codes, "warning_codes")
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ReplanningRequest":
        return cls(
            request_id=payload["request_id"],
            trip_id=payload["trip_id"],
            session_state_id=payload["session_state_id"],
            requested_at=payload["requested_at"],
            replanning_kind=payload["replanning_kind"],
            summary=payload["summary"],
            trigger_event_id=payload["trigger_event_id"],
            based_on_saved_scenario_id=payload["based_on_saved_scenario_id"],
            scenario_search_id=payload["scenario_search_id"],
            ranked_result_set_id=payload.get("ranked_result_set_id"),
            checkpoint_id=payload.get("checkpoint_id"),
            affected_option_ids=_payload_list(payload, "affected_option_ids", []),
            warning_codes=_payload_list(payload, "warning_codes", []),
            requires_user_confirmation=payload.get(
                "requires_user_confirmation",
                False,
            ),
            notes=_payload_list(payload, "notes", []),
        )


@dataclass(slots=True)
class InTripRevisionOutput:
    """Structured output describing the resulting in-trip revision lane."""

    revision_output_id: str
    trip_id: str
    output_kind: str
    generated_at: str
    summary: str
    recommended_action_id: str
    ref_ids: list[str] = field(default_factory=list)
    warning_codes: list[str] = field(default_factory=list)
    payload: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.revision_output_id, "revision_output_id")
        require_non_empty(self.trip_id, "trip_id")
        require_non_empty(self.generated_at, "generated_at")
        require_non_empty(self.summary, "summary")
        require_non_empty(self.recommended_action_id, "recommended_action_id")
        if self.output_kind not in REVISION_OUTPUT_KINDS:
            raise ValueError(f"output_kind must be one of {REVISION_OUTPUT_KINDS}")
        _require_unique_strings(self.ref_ids, "ref_ids")
        _require_unique_strings(self.warning_codes, "warning_codes")
        if not isinstance(self.payload, dict):
            raise ValueError("payload must be a mapping")
        require_string_mapping(self.payload, "payload")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "InTripRevisionOutput":
        return cls(
            revision_output_id=payload["revision_output_id"],
            trip_id=payload["trip_id"],
            output_kind=payload["output_kind"],
            generated_at=payload["generated_at"],
            summary=payload["summary"],
            recommended_action_id=payload["recommended_action_id"],
            ref_ids=_payload_list(payload, "ref_ids", []),
            warning_codes=_payload_list(payload, "warning_codes", []),
            payload=_payload_mapping(payload, "payload", {}),
        )


@dataclass(slots=True)
class InTripAdjustmentResult:
    """Planner-turn scaffold plus the state updates implied by one in-trip event."""

    planner_turn: PlannerTurn
    updated_session_state: PlanningSessionState
    activity_event: ActivityLogEvent
    replanning_request: ReplanningRequest
    revision_output: InTripRevisionOutput

    def __post_init__(self) -> None:
        if not isinstance(self.planner_turn, PlannerTurn):
            raise ValueError("planner_turn must be a PlannerTurn")
        if not isinstance(self.updated_session_state, PlanningSessionState):
            raise ValueError("updated_session_state must be a PlanningSessionState")
        if not isinstance(self.activity_event, ActivityLogEvent):
            raise ValueError("activity_event must be an ActivityLogEvent")
        if not isinstance(self.replanning_request, ReplanningRequest):
            raise ValueError("replanning_request must be a ReplanningRequest")
        if not isinstance(self.revision_output, InTripRevisionOutput):
            raise ValueError("revision_output must be an InTripRevisionOutput")


def build_in_trip_adjustment_result(
    context: InTripAdjustmentContext,
    event: InTripTriggerEvent,
) -> InTripAdjustmentResult:
    """Build a first-pass in-trip adjustment turn and its implied state deltas."""

    if event.trip_id != context.session_state.trip_id:
        raise ValueError("event.trip_id must match session_state.trip_id")
    if event.session_state_id != context.session_state.session_state_id:
        raise ValueError("event.session_state_id must match session_state.session_state_id")

    replanning_kind = _classify_replanning_kind(event)
    pending_decisions = _pending_decisions(context, event, replanning_kind)
    updated_session_state = replace(
        context.session_state,
        updated_at=context.generated_at,
        pending_decisions=pending_decisions,
        notes=list(context.session_state.notes)
        + [f"in-trip-trigger:{event.trigger_kind}:{replanning_kind}"],
        tags=list(
            dict.fromkeys(
                list(context.session_state.tags) + ["in-trip", event.trigger_kind, replanning_kind]
            )
        ),
    )
    replanning_request = _build_replanning_request(
        context,
        event,
        replanning_kind,
        pending_decisions,
    )
    activity_event = _build_activity_event(context, event, replanning_request)
    revision_output = _build_revision_output(context, event, replanning_request)
    planner_turn = _build_planner_turn(
        context,
        event,
        replanning_request,
        revision_output,
        pending_decisions,
    )

    return InTripAdjustmentResult(
        planner_turn=planner_turn,
        updated_session_state=updated_session_state,
        activity_event=activity_event,
        replanning_request=replanning_request,
        revision_output=revision_output,
    )


def _classify_replanning_kind(event: InTripTriggerEvent) -> str:
    if event.severity == "informational":
        return "ignore"
    if event.trigger_kind == "delay" and (
        event.severity == "critical" or event.change_scope in {"full_day", "trip_wide"}
    ):
        return "emergency_fallback"
    if event.trigger_kind in {"closure", "weather"}:
        return "scenario_revision"
    if event.trigger_kind in {"budget_drift", "preference_change", "fatigue_shift"}:
        return "rerank"
    return "ignore"


def _pending_decisions(
    context: InTripAdjustmentContext,
    event: InTripTriggerEvent,
    replanning_kind: str,
) -> list[SessionPendingDecision]:
    if replanning_kind in {"ignore", "rerank"}:
        return list(context.session_state.pending_decisions)

    existing = list(context.session_state.pending_decisions)
    decision = SessionPendingDecision(
        decision_id=f"{event.trigger_event_id}:decision",
        prompt=_decision_prompt(event, replanning_kind),
        created_at=context.generated_at,
        title="Approve in-trip adjustment",
        choices=[
            "Use the proposed adjustment",
            "Keep the current plan for now",
        ],
        blocking=True,
        related_saved_scenario_id=context.session_state.current_saved_scenario_id,
        notes=[
            "In-trip adjustment stays downstream from saved scenarios, ranking, and checkpoint history."
        ],
        related_option_set_id=event.metadata.get("option_set_id"),
    )
    return existing + [decision]


def _workflow_pending_decisions(
    session_pending_decisions: list[SessionPendingDecision],
) -> list[PendingDecision]:
    workflow_decisions: list[PendingDecision] = []
    for decision in session_pending_decisions:
        workflow_decisions.append(
            PendingDecision(
                decision_id=decision.decision_id,
                prompt=decision.prompt,
                requested_at=decision.created_at,
                choices=[
                    DecisionOption(
                        choice_id=f"{decision.decision_id}:choice:{index}",
                        label=choice,
                        recommended=index == 0,
                    )
                    for index, choice in enumerate(decision.choices)
                ],
                blocking=decision.blocking,
                selected_choice_id=(
                    None
                    if decision.selected_choice is None
                    else (
                        f"{decision.decision_id}:choice:"
                        f"{decision.choices.index(decision.selected_choice)}"
                    )
                ),
                due_by=decision.due_by,
                notes=list(decision.notes),
                related_option_ids=_compact_refs(decision.related_option_set_id),
            )
        )
    return workflow_decisions


def _decision_prompt(event: InTripTriggerEvent, replanning_kind: str) -> str:
    if replanning_kind == "emergency_fallback":
        return (
            "The active trip can no longer continue cleanly. Should the planner "
            "switch to the emergency fallback now?"
        )
    return (
        f"The planner detected a {event.trigger_kind.replace('_', ' ')} event. "
        "Should it replace the current in-trip path with a revised scenario?"
    )


def _build_replanning_request(
    context: InTripAdjustmentContext,
    event: InTripTriggerEvent,
    replanning_kind: str,
    pending_decisions: list[SessionPendingDecision],
) -> ReplanningRequest:
    introduced_blocking_decision = len(pending_decisions) > len(
        context.session_state.pending_decisions
    )
    return ReplanningRequest(
        request_id=f"{event.trigger_event_id}:request",
        trip_id=context.session_state.trip_id,
        session_state_id=context.session_state.session_state_id,
        requested_at=context.generated_at,
        replanning_kind=replanning_kind,
        summary=_request_summary(replanning_kind),
        trigger_event_id=event.trigger_event_id,
        based_on_saved_scenario_id=context.session_state.current_saved_scenario_id or "",
        scenario_search_id=context.scenario_search_id,
        ranked_result_set_id=context.ranked_result_set_id,
        checkpoint_id=(event.affected_checkpoint_id or context.session_state.current_checkpoint_id),
        affected_option_ids=list(event.affected_option_ids),
        warning_codes=list(event.trigger_codes),
        requires_user_confirmation=introduced_blocking_decision,
        notes=[
            "Keep in-trip routing attached to saved-scenario, checkpoint, and ranking references."
        ],
    )


def _request_summary(replanning_kind: str) -> str:
    if replanning_kind == "ignore":
        return "Track the in-trip event without changing the current saved scenario."
    if replanning_kind == "rerank":
        return "Refresh ranked alternatives before mutating the saved scenario."
    if replanning_kind == "scenario_revision":
        return "Build a scenario revision that preserves existing trip context."
    return "Escalate to an emergency fallback without treating the change as a new trip."


def _build_activity_event(
    context: InTripAdjustmentContext,
    event: InTripTriggerEvent,
    replanning_request: ReplanningRequest,
) -> ActivityLogEvent:
    event_kind = (
        "budget_updated" if event.trigger_kind == "budget_drift" else "in_trip_change_requested"
    )
    return ActivityLogEvent(
        activity_event_id=f"{event.trigger_event_id}:activity",
        trip_id=context.session_state.trip_id,
        session_state_id=context.session_state.session_state_id,
        occurred_at=context.generated_at,
        event_kind=event_kind,
        summary=event.summary,
        actor=event.actor,
        related_option_set_id=event.metadata.get("option_set_id"),
        saved_scenario_id=context.session_state.current_saved_scenario_id,
        budget_plan_id=(
            context.session_state.active_budget_plan_id
            if event.trigger_kind == "budget_drift"
            else None
        ),
        checkpoint_id=(
            replanning_request.checkpoint_id
            if replanning_request.replanning_kind != "ignore"
            else None
        ),
        metadata={
            "trigger_kind": event.trigger_kind,
            "severity": event.severity,
            "change_scope": event.change_scope,
            "replanning_kind": replanning_request.replanning_kind,
        },
        tags=["in-trip", event.trigger_kind, replanning_request.replanning_kind],
    )


def _build_revision_output(
    context: InTripAdjustmentContext,
    event: InTripTriggerEvent,
    replanning_request: ReplanningRequest,
) -> InTripRevisionOutput:
    mapping = {
        "ignore": ("status_note", "action-record-trigger"),
        "rerank": ("reranked_options", "action-refresh-ranking"),
        "scenario_revision": ("scenario_revision", "action-build-revision"),
        "emergency_fallback": ("emergency_fallback", "action-build-emergency-fallback"),
    }
    output_kind, recommended_action_id = mapping[replanning_request.replanning_kind]
    return InTripRevisionOutput(
        revision_output_id=f"{event.trigger_event_id}:output",
        trip_id=context.session_state.trip_id,
        output_kind=output_kind,
        generated_at=context.generated_at,
        summary=_revision_summary(replanning_request.replanning_kind),
        recommended_action_id=recommended_action_id,
        ref_ids=_compact_refs(
            context.session_state.current_saved_scenario_id,
            replanning_request.checkpoint_id,
            context.scenario_search_id,
            context.ranked_result_set_id,
            event.metadata.get("option_set_id"),
            event.affected_saved_scenario_id,
        ),
        warning_codes=list(event.trigger_codes),
        payload={
            "trigger_kind": event.trigger_kind,
            "severity": event.severity,
            "change_scope": event.change_scope,
        },
    )


def _revision_summary(replanning_kind: str) -> str:
    if replanning_kind == "ignore":
        return "The event is informational and stays in monitoring without replanning."
    if replanning_kind == "rerank":
        return "The event should refresh ranked alternatives before any scenario swap."
    if replanning_kind == "scenario_revision":
        return "The event requires a revised in-trip scenario tied to the current saved plan."
    return "The event requires an emergency fallback path because the current route is no longer viable."


def _build_planner_turn(
    context: InTripAdjustmentContext,
    event: InTripTriggerEvent,
    replanning_request: ReplanningRequest,
    revision_output: InTripRevisionOutput,
    pending_decisions: list[SessionPendingDecision],
) -> PlannerTurn:
    replanning_kind = replanning_request.replanning_kind
    current_stage = "monitoring" if replanning_kind == "ignore" else "replanning"
    workflow_pending_decisions = _workflow_pending_decisions(pending_decisions)
    output = _planner_output(revision_output, event, replanning_kind)
    actions = _planner_actions(
        context,
        event,
        replanning_request,
        revision_output,
        pending_decisions,
    )
    open_action_ids = [
        action.action_id for action in actions if action.status in {"pending", "in_progress"}
    ]
    completed_action_ids = [
        action.action_id for action in actions if action.status in {"completed", "skipped"}
    ]
    workflow_state = WorkflowStateSnapshot(
        workflow_state_id=(
            f"workflow-state:{context.session_state.session_state_id}:in-trip-adjustment"
        ),
        trip_id=context.session_state.trip_id,
        mode=context.session_state.mode,
        workflow_kind="in_trip_adjustment",
        current_stage=current_stage,
        status="waiting_on_user" if workflow_pending_decisions else "active",
        recorded_at=context.generated_at,
        pending_decisions=workflow_pending_decisions,
        open_action_ids=open_action_ids,
        completed_action_ids=completed_action_ids,
        recent_output_ids=[output.output_id],
        notes=[
            "In-trip adjustment consumes saved-scenario and ranking references instead of starting a new trip."
        ],
        tags=["in-trip", event.trigger_kind, replanning_kind],
    )
    transition = WorkflowTransition(
        from_stage="monitoring",
        to_stage=current_stage,
        trigger="trip_disruption" if replanning_kind != "ignore" else "checkpoint_due",
        changed_at=context.generated_at,
        reason=event.summary,
        changed_by=event.actor,
        warning_codes=list(event.trigger_codes),
    )
    next_step = NextStepSummary(
        headline=_next_step_headline(replanning_kind),
        recommended_action_id=revision_output.recommended_action_id,
        blocking_decision_ids=[decision.decision_id for decision in workflow_pending_decisions],
        expected_output_ids=[output.output_id],
        notes=[
            "Preserve checkpoint lineage and keep the revision downstream from ranking and saved scenarios."
        ],
    )
    return PlannerTurn(
        turn_id=f"{event.trigger_event_id}:turn",
        trip_id=context.session_state.trip_id,
        mode=context.session_state.mode,
        workflow_kind="in_trip_adjustment",
        turn_kind="adjustment_pass",
        started_at=context.generated_at,
        workflow_state=workflow_state,
        transition=transition,
        next_step=next_step,
        actions=actions,
        outputs=[output],
        notes=[
            "The scaffold classifies in-trip triggers before deciding whether to monitor, rerank, revise, or fall back."
        ],
    )


def _planner_actions(
    context: InTripAdjustmentContext,
    event: InTripTriggerEvent,
    replanning_request: ReplanningRequest,
    revision_output: InTripRevisionOutput,
    pending_decisions: list[SessionPendingDecision],
) -> list[PlannerAction]:
    collect = PlannerAction(
        action_id="action-record-trigger",
        action_kind="collect_context",
        title="Capture the in-trip trigger against the current session state",
        stage="monitoring",
        status="completed",
        actor="planner",
        payload={
            "trigger_kind": event.trigger_kind,
            "severity": event.severity,
            "source": event.source,
        },
    )
    if replanning_request.replanning_kind == "ignore":
        return [
            collect,
            PlannerAction(
                action_id="action-monitor-only",
                action_kind="record_warning",
                title="Leave the trip in monitoring because the change is informational",
                stage="monitoring",
                status="completed",
                actor="planner",
                depends_on_action_ids=[collect.action_id],
                payload={
                    "warning_codes": ",".join(event.trigger_codes) or "informational",
                },
            ),
        ]

    if replanning_request.replanning_kind == "rerank":
        return [
            collect,
            PlannerAction(
                action_id="action-refresh-ranking",
                action_kind="rank_options",
                title="Refresh ranked alternatives against the active in-trip constraints",
                stage="replanning",
                status="in_progress",
                actor="planner",
                depends_on_action_ids=[collect.action_id],
                payload={
                    "scenario_search_id": context.scenario_search_id,
                    "ranked_result_set_id": context.ranked_result_set_id or "",
                },
            ),
        ]

    build_action_id = revision_output.recommended_action_id
    actions = [
        collect,
        PlannerAction(
            action_id=build_action_id,
            action_kind="replan_itinerary",
            title=(
                "Build an emergency fallback path from the current saved scenario"
                if replanning_request.replanning_kind == "emergency_fallback"
                else "Build a revised in-trip scenario from the current saved plan"
            ),
            stage="replanning",
            status="in_progress",
            actor="planner",
            depends_on_action_ids=[collect.action_id],
            payload={
                "based_on_saved_scenario_id": (
                    context.session_state.current_saved_scenario_id or ""
                ),
                "checkpoint_id": replanning_request.checkpoint_id or "",
                "scenario_search_id": context.scenario_search_id,
            },
        ),
    ]
    if pending_decisions:
        actions.append(
            PlannerAction(
                action_id="action-request-adjustment-decision",
                action_kind="request_decision",
                title="Ask whether to adopt the proposed in-trip adjustment",
                stage="decision_checkpoint",
                status="pending",
                actor="planner",
                depends_on_action_ids=[build_action_id],
                payload={
                    "decision_id": pending_decisions[-1].decision_id,
                },
            )
        )
    return actions


def _planner_output(
    revision_output: InTripRevisionOutput,
    event: InTripTriggerEvent,
    replanning_kind: str,
) -> PlannerOutput:
    output_kind_map = {
        "status_note": ("status_update", "planner_chat"),
        "reranked_options": ("ranked_scenarios", "side_panel"),
        "scenario_revision": ("option_set", "side_panel"),
        "emergency_fallback": ("warning", "notification"),
    }
    output_kind, surface = output_kind_map[revision_output.output_kind]
    title_map = {
        "ignore": "In-trip event recorded without replanning",
        "rerank": "In-trip reranking request assembled",
        "scenario_revision": "In-trip scenario revision prepared",
        "emergency_fallback": "Emergency fallback required",
    }
    return PlannerOutput(
        output_id=revision_output.revision_output_id,
        output_kind=output_kind,
        title=title_map[replanning_kind],
        emitted_at=revision_output.generated_at,
        surface=surface,
        summary=revision_output.summary,
        ref_ids=list(revision_output.ref_ids),
        warnings=list(revision_output.warning_codes),
        payload={
            "trigger_kind": event.trigger_kind,
            "recommended_action_id": revision_output.recommended_action_id,
        },
    )


def _next_step_headline(replanning_kind: str) -> str:
    if replanning_kind == "ignore":
        return "Keep monitoring and preserve the current in-trip plan."
    if replanning_kind == "rerank":
        return "Refresh the ranked alternatives before replacing the saved scenario."
    if replanning_kind == "scenario_revision":
        return "Complete the revised scenario and confirm it before replacing the current path."
    return "Prepare the emergency fallback and confirm it before abandoning the active route."
