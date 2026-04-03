"""Option-presentation feedback loop scaffolds for leisure planning."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from trip_planner.contracts._validators import (
    require_non_empty,
    require_optional_non_empty,
)
from trip_planner.preferences import (
    AutonomyFeedback,
    PlanningAutonomyProfile,
    RevealedPreferenceSignal,
    RevealedPreferenceUpdate,
    build_revealed_preference_update,
    schema as preference_schema,
)
from trip_planner.preferences.autonomy import AUTONOMY_FEEDBACK_KINDS
from trip_planner.preferences.models import LeisurePreferenceProfile
from trip_planner.state import (
    ActivityLogEvent,
    OptionPresentationRecord,
    PendingDecision as SessionPendingDecision,
    PlanningInteractionState,
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

FEEDBACK_KINDS: tuple[str, ...] = (
    "accept_option",
    "reject_option",
    "request_alternatives",
    "save_as_fallback",
)
COMPARISON_DEPTHS: tuple[str, ...] = (
    "quick_preference_check",
    "inventory_narrowing",
)


def _require_axis_mapping(values: dict[str, float], field_name: str) -> None:
    if not isinstance(values, dict):
        raise ValueError(f"{field_name} must be a mapping")
    for key, value in values.items():
        if not isinstance(key, str) or not key:
            raise ValueError(f"{field_name} keys must be non-empty strings")
        if not isinstance(value, int | float):
            raise ValueError(f"{field_name}[{key}] must be numeric")
        if not -1.0 <= float(value) <= 1.0:
            raise ValueError(f"{field_name}[{key}] must be between -1.0 and 1.0")


@dataclass(slots=True)
class FeedbackLoopContext:
    """Typed inputs required to route one feedback event through orchestration."""

    preference_profile: LeisurePreferenceProfile
    session_state: PlanningSessionState
    autonomy_profile: PlanningAutonomyProfile
    generated_at: str
    trip_stage: str = "inventory_selection"

    def __post_init__(self) -> None:
        if not isinstance(self.preference_profile, LeisurePreferenceProfile):
            raise ValueError("preference_profile must be a LeisurePreferenceProfile")
        if not isinstance(self.session_state, PlanningSessionState):
            raise ValueError("session_state must be a PlanningSessionState")
        if not isinstance(self.autonomy_profile, PlanningAutonomyProfile):
            raise ValueError("autonomy_profile must be a PlanningAutonomyProfile")
        if self.session_state.mode != "leisure":
            raise ValueError("session_state must represent a leisure session")
        if self.trip_stage not in preference_schema.PLANNING_STAGES:
            raise ValueError(
                f"trip_stage must be one of {preference_schema.PLANNING_STAGES}"
            )
        require_non_empty(self.generated_at, "generated_at")


@dataclass(slots=True)
class OptionFeedbackEvent:
    """Structured feedback captured from one option-presentation touchpoint."""

    feedback_event_id: str
    presentation_id: str
    feedback_kind: str
    option_id: str
    summary: str
    comparison_depth: str = "quick_preference_check"
    signal_strength: float = 0.75
    dimension_biases: dict[str, float] = field(default_factory=dict)
    hybrid_biases: dict[str, float] = field(default_factory=dict)
    autonomy_feedback_kinds: list[str] = field(default_factory=list)
    fallback_saved_scenario_id: str | None = None
    fallback_title: str | None = None

    def __post_init__(self) -> None:
        require_non_empty(self.feedback_event_id, "feedback_event_id")
        require_non_empty(self.presentation_id, "presentation_id")
        require_non_empty(self.option_id, "option_id")
        require_non_empty(self.summary, "summary")
        if self.feedback_kind not in FEEDBACK_KINDS:
            raise ValueError(f"feedback_kind must be one of {FEEDBACK_KINDS}")
        if self.comparison_depth not in COMPARISON_DEPTHS:
            raise ValueError(f"comparison_depth must be one of {COMPARISON_DEPTHS}")
        if not 0.0 <= self.signal_strength <= 1.0:
            raise ValueError("signal_strength must be between 0.0 and 1.0")
        _require_axis_mapping(self.dimension_biases, "dimension_biases")
        _require_axis_mapping(self.hybrid_biases, "hybrid_biases")
        for kind in self.autonomy_feedback_kinds:
            if kind not in AUTONOMY_FEEDBACK_KINDS:
                raise ValueError(
                    "autonomy_feedback_kinds must contain supported autonomy feedback"
                )
        require_optional_non_empty(
            self.fallback_saved_scenario_id,
            "fallback_saved_scenario_id",
        )
        require_optional_non_empty(self.fallback_title, "fallback_title")
        if self.feedback_kind == "save_as_fallback":
            if self.fallback_saved_scenario_id is None:
                raise ValueError("save_as_fallback requires fallback_saved_scenario_id")
            if self.fallback_title is None:
                raise ValueError("save_as_fallback requires fallback_title")


@dataclass(slots=True)
class ScenarioCaptureRequest:
    """Structured scenario-persistence request emitted by the feedback loop."""

    saved_scenario_id: str
    trip_id: str
    title: str
    label: str
    requested_at: str
    option_id: str
    option_set_id: str
    based_on_saved_scenario_id: str | None = None
    summary: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.saved_scenario_id, "saved_scenario_id")
        require_non_empty(self.trip_id, "trip_id")
        require_non_empty(self.title, "title")
        require_non_empty(self.label, "label")
        require_non_empty(self.requested_at, "requested_at")
        require_non_empty(self.option_id, "option_id")
        require_non_empty(self.option_set_id, "option_set_id")
        require_optional_non_empty(
            self.based_on_saved_scenario_id,
            "based_on_saved_scenario_id",
        )
        if self.label != "fallback":
            raise ValueError("ScenarioCaptureRequest currently supports fallback saves")


@dataclass(slots=True)
class FeedbackLoopResult:
    """Planner-turn scaffold plus the state updates implied by one feedback event."""

    planner_turn: PlannerTurn
    updated_session_state: PlanningSessionState
    activity_event: ActivityLogEvent
    updated_autonomy_profile: PlanningAutonomyProfile
    revealed_preference_updates: list[RevealedPreferenceUpdate] = field(
        default_factory=list
    )
    scenario_capture_request: ScenarioCaptureRequest | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.planner_turn, PlannerTurn):
            raise ValueError("planner_turn must be a PlannerTurn")
        if not isinstance(self.updated_session_state, PlanningSessionState):
            raise ValueError("updated_session_state must be a PlanningSessionState")
        if not isinstance(self.activity_event, ActivityLogEvent):
            raise ValueError("activity_event must be an ActivityLogEvent")
        if not isinstance(self.updated_autonomy_profile, PlanningAutonomyProfile):
            raise ValueError(
                "updated_autonomy_profile must be a PlanningAutonomyProfile"
            )
        if any(
            not isinstance(item, RevealedPreferenceUpdate)
            for item in self.revealed_preference_updates
        ):
            raise ValueError(
                "revealed_preference_updates must contain RevealedPreferenceUpdate instances"
            )


def build_feedback_loop_result(
    context: FeedbackLoopContext,
    event: OptionFeedbackEvent,
) -> FeedbackLoopResult:
    """Build a first-pass feedback routing turn and its implied state deltas."""

    presentation = _select_presentation(context.session_state, event.presentation_id)
    if event.option_id not in presentation.surfaced_option_ids:
        raise ValueError("event.option_id must be one of surfaced_option_ids")

    updated_presentation = _apply_feedback_to_presentation(presentation, event)
    updated_session_state = replace(
        context.session_state,
        updated_at=context.generated_at,
        recent_option_presentations=[
            (
                updated_presentation
                if item.presentation_id == presentation.presentation_id
                else item
            )
            for item in context.session_state.recent_option_presentations
        ],
    )

    revealed_update = build_revealed_preference_update(
        context.preference_profile,
        _build_revealed_signal(context, updated_presentation, event),
    )
    updated_autonomy = _apply_autonomy_feedback(context, event)
    updated_session_state = replace(
        updated_session_state,
        interaction_state=_interaction_state_from_behavior(
            updated_session_state.interaction_state,
            updated_autonomy,
            context.trip_stage,
            event.autonomy_feedback_kinds,
        ),
    )
    updated_session_state = replace(
        updated_session_state,
        pending_decisions=_updated_pending_decisions(updated_session_state, event),
        notes=_session_notes(updated_session_state, event),
    )

    scenario_capture_request = _build_scenario_capture_request(
        updated_session_state,
        updated_presentation,
        event,
        context.generated_at,
    )
    activity_event = _build_activity_event(
        updated_session_state,
        updated_presentation,
        event,
        scenario_capture_request,
        context.generated_at,
    )
    planner_turn = _build_planner_turn(
        updated_session_state,
        updated_presentation,
        event,
        updated_autonomy,
        activity_event,
        scenario_capture_request,
        context.generated_at,
        context.trip_stage,
    )

    return FeedbackLoopResult(
        planner_turn=planner_turn,
        updated_session_state=updated_session_state,
        activity_event=activity_event,
        updated_autonomy_profile=updated_autonomy,
        revealed_preference_updates=[revealed_update],
        scenario_capture_request=scenario_capture_request,
    )


def _select_presentation(
    session_state: PlanningSessionState, presentation_id: str
) -> OptionPresentationRecord:
    for presentation in session_state.recent_option_presentations:
        if presentation.presentation_id == presentation_id:
            return presentation
    raise ValueError("presentation_id must match a recent_option_presentations entry")


def _apply_feedback_to_presentation(
    presentation: OptionPresentationRecord,
    event: OptionFeedbackEvent,
) -> OptionPresentationRecord:
    rejected_option_ids = list(presentation.rejected_option_ids)
    selected_option_id = presentation.selected_option_id
    notes = list(presentation.notes)

    if event.feedback_kind in {"reject_option", "request_alternatives"}:
        if event.option_id not in rejected_option_ids:
            rejected_option_ids.append(event.option_id)
        if selected_option_id == event.option_id:
            selected_option_id = None
    elif event.feedback_kind == "accept_option":
        selected_option_id = event.option_id
        rejected_option_ids = [
            option_id
            for option_id in rejected_option_ids
            if option_id != event.option_id
        ]
    elif event.feedback_kind == "save_as_fallback":
        pass

    notes.append(f"feedback:{event.feedback_kind}:{event.summary}")

    return replace(
        presentation,
        selected_option_id=selected_option_id,
        rejected_option_ids=rejected_option_ids,
        notes=notes,
        summary=event.summary,
    )


def _build_revealed_signal(
    context: FeedbackLoopContext,
    presentation: OptionPresentationRecord,
    event: OptionFeedbackEvent,
) -> RevealedPreferenceSignal:
    reaction_type = {
        "accept_option": "selected",
        "reject_option": "rejected",
        "request_alternatives": "requested_less_like_this",
        "save_as_fallback": "saved_for_later",
    }[event.feedback_kind]
    return RevealedPreferenceSignal(
        signal_id=f"{event.feedback_event_id}:revealed",
        trip_stage=context.trip_stage,
        reaction_type=reaction_type,
        option_set_id=presentation.option_set_id,
        option_id=event.option_id,
        option_kind="destination_bundle",
        signal_strength=event.signal_strength,
        dimension_biases=event.dimension_biases,
        hybrid_biases=event.hybrid_biases,
        summary=event.summary,
    )


def _apply_autonomy_feedback(
    context: FeedbackLoopContext,
    event: OptionFeedbackEvent,
) -> PlanningAutonomyProfile:
    updated = context.autonomy_profile
    for feedback_kind in event.autonomy_feedback_kinds:
        updated = updated.apply_feedback(
            AutonomyFeedback(
                feedback_kind=feedback_kind,
                trip_stage=context.trip_stage,
                note=event.summary,
            )
        )
    return updated


def _interaction_state_from_behavior(
    previous: PlanningInteractionState,
    autonomy_profile: PlanningAutonomyProfile,
    trip_stage: str,
    autonomy_feedback_kinds: list[str],
) -> PlanningInteractionState:
    behavior = autonomy_profile.behavior_for_stage(trip_stage)
    preference = autonomy_profile.preference_for_stage(trip_stage)
    notes = list(previous.notes)
    if autonomy_feedback_kinds:
        notes.append("feedback-loop updated planner autonomy pacing.")
    return replace(
        previous,
        initiative_level=_initiative_level_from_preference(
            preference.system_initiative
        ),
        checkpoint_frequency=(
            "phase" if behavior.ask_before_next_major_change else "manual"
        ),
        option_preview_timing="early" if behavior.surface_options_early else "balanced",
        auto_advance_research_passes=behavior.target_research_passes,
        ask_before_major_change=behavior.ask_before_next_major_change,
        notes=notes,
    )


def _initiative_level_from_preference(system_initiative: float) -> str:
    if system_initiative >= 0.85:
        return "planner_first"
    if system_initiative >= 0.65:
        return "planner_led"
    if system_initiative <= 0.25:
        return "user_led"
    return "balanced"


def _updated_pending_decisions(
    session_state: PlanningSessionState,
    event: OptionFeedbackEvent,
) -> list[SessionPendingDecision]:
    if event.feedback_kind in {"reject_option", "request_alternatives"}:
        return []
    return list(session_state.pending_decisions)


def _session_notes(
    session_state: PlanningSessionState,
    event: OptionFeedbackEvent,
) -> list[str]:
    notes = list(session_state.notes)
    notes.append(
        f"feedback-loop:{event.feedback_kind}:{event.comparison_depth}:{event.option_id}"
    )
    return notes


def _build_scenario_capture_request(
    session_state: PlanningSessionState,
    presentation: OptionPresentationRecord,
    event: OptionFeedbackEvent,
    generated_at: str,
) -> ScenarioCaptureRequest | None:
    if event.feedback_kind != "save_as_fallback":
        return None
    return ScenarioCaptureRequest(
        saved_scenario_id=event.fallback_saved_scenario_id or "",
        trip_id=session_state.trip_id,
        title=event.fallback_title or "",
        label="fallback",
        requested_at=generated_at,
        option_id=event.option_id,
        option_set_id=presentation.option_set_id,
        based_on_saved_scenario_id=session_state.current_saved_scenario_id,
        summary=event.summary,
    )


def _build_activity_event(
    session_state: PlanningSessionState,
    presentation: OptionPresentationRecord,
    event: OptionFeedbackEvent,
    scenario_capture_request: ScenarioCaptureRequest | None,
    generated_at: str,
) -> ActivityLogEvent:
    event_kind = {
        "accept_option": "decision_recorded",
        "reject_option": "option_rejected",
        "request_alternatives": "rerank_requested",
        "save_as_fallback": "scenario_saved",
    }[event.feedback_kind]
    return ActivityLogEvent(
        activity_event_id=f"{event.feedback_event_id}:activity",
        trip_id=session_state.trip_id,
        session_state_id=session_state.session_state_id,
        occurred_at=generated_at,
        event_kind=event_kind,
        summary=event.summary,
        actor="user",
        related_option_set_id=presentation.option_set_id,
        saved_scenario_id=(
            scenario_capture_request.saved_scenario_id
            if scenario_capture_request is not None
            else None
        ),
        metadata={
            "feedback_kind": event.feedback_kind,
            "comparison_depth": event.comparison_depth,
            "option_id": event.option_id,
        },
        tags=["feedback-loop", event.feedback_kind],
    )


def _build_planner_turn(
    session_state: PlanningSessionState,
    presentation: OptionPresentationRecord,
    event: OptionFeedbackEvent,
    autonomy_profile: PlanningAutonomyProfile,
    activity_event: ActivityLogEvent,
    scenario_capture_request: ScenarioCaptureRequest | None,
    generated_at: str,
    trip_stage: str,
) -> PlannerTurn:
    rerank = event.feedback_kind in {"reject_option", "request_alternatives"}
    current_stage = "ranking" if rerank else "decision_checkpoint"
    status = "active" if not session_state.pending_decisions else "waiting_on_user"
    action_ids = {
        "collect": "action-collect-feedback-context",
        "update": "action-refresh-revealed-preferences",
        "rank": "action-rank-options",
        "save": "action-persist-fallback",
        "decision": "action-request-decision",
    }
    actions = [
        PlannerAction(
            action_id=action_ids["collect"],
            action_kind="collect_context",
            title="Capture the latest option-presentation feedback",
            stage=current_stage,
            status="completed",
            payload={
                "presentation_id": presentation.presentation_id,
                "option_set_id": presentation.option_set_id,
                "comparison_depth": event.comparison_depth,
            },
        ),
        PlannerAction(
            action_id=action_ids["update"],
            action_kind="refresh_preferences",
            title="Route revealed-preference and autonomy feedback into planning state",
            stage="objective_derivation",
            status="completed",
            depends_on_action_ids=[action_ids["collect"]],
            payload={
                "feedback_kind": event.feedback_kind,
                "autonomy_feedback_kinds": list(event.autonomy_feedback_kinds),
                "target_research_passes": autonomy_profile.behavior_for_stage(
                    trip_stage
                ).target_research_passes,
            },
        ),
    ]
    outputs: list[PlannerOutput] = []

    if rerank:
        actions.append(
            PlannerAction(
                action_id=action_ids["rank"],
                action_kind="rank_options",
                title="Refresh the ranked option set after explicit traveler feedback",
                stage="ranking",
                status="in_progress",
                depends_on_action_ids=[action_ids["update"]],
                payload={
                    "requested_alternatives": event.feedback_kind
                    == "request_alternatives",
                    "rejected_option_ids": list(presentation.rejected_option_ids),
                    "comparison_depth": event.comparison_depth,
                },
            )
        )
        outputs.extend(
            [
                PlannerOutput(
                    output_id="output-feedback-warning",
                    output_kind="warning",
                    title="Feedback loop requested a rerank",
                    emitted_at=generated_at,
                    surface="planner_chat",
                    summary=event.summary,
                    warnings=["feedback_rerank_requested"],
                    payload={
                        "activity_event_id": activity_event.activity_event_id,
                        "presentation_id": presentation.presentation_id,
                    },
                ),
                PlannerOutput(
                    output_id="output-feedback-status",
                    output_kind="status_update",
                    title="Ranking refresh is queued with explicit feedback context",
                    emitted_at=generated_at,
                    surface="side_panel",
                    summary=_comparison_summary(event.comparison_depth),
                    payload={
                        "comparison_depth": event.comparison_depth,
                        "feedback_kind": event.feedback_kind,
                    },
                ),
            ]
        )
        recommended_action_id = action_ids["rank"]
    else:
        if scenario_capture_request is not None:
            actions.append(
                PlannerAction(
                    action_id=action_ids["save"],
                    action_kind="persist_state",
                    title="Persist the selected option as an explicit fallback scenario",
                    stage="decision_checkpoint",
                    status="in_progress",
                    depends_on_action_ids=[action_ids["update"]],
                    payload={
                        "saved_scenario_id": scenario_capture_request.saved_scenario_id,
                        "label": scenario_capture_request.label,
                        "based_on_saved_scenario_id": (
                            scenario_capture_request.based_on_saved_scenario_id or ""
                        ),
                    },
                )
            )
            recommended_action_id = action_ids["save"]
        else:
            actions.append(
                PlannerAction(
                    action_id=action_ids["decision"],
                    action_kind="request_decision",
                    title="Carry the accepted option forward into the next checkpoint",
                    stage="decision_checkpoint",
                    status="in_progress",
                    depends_on_action_ids=[action_ids["update"]],
                    payload={
                        "selected_option_id": presentation.selected_option_id or "",
                        "pending_decision_ids": [
                            decision.decision_id
                            for decision in session_state.pending_decisions
                        ],
                    },
                )
            )
            recommended_action_id = action_ids["decision"]
        outputs.append(
            PlannerOutput(
                output_id="output-feedback-status",
                output_kind="status_update",
                title="Feedback was captured as structured workflow state",
                emitted_at=generated_at,
                surface="planner_chat",
                summary=event.summary,
                payload={
                    "selected_option_id": presentation.selected_option_id or "",
                    "comparison_depth": event.comparison_depth,
                },
            )
        )
        if scenario_capture_request is not None:
            outputs.append(
                PlannerOutput(
                    output_id="output-fallback-capture",
                    output_kind="decision_request",
                    title="Fallback capture request is ready for persistence",
                    emitted_at=generated_at,
                    surface="side_panel",
                    summary=(
                        f"{scenario_capture_request.title} stays explicit without"
                        " replacing the baseline scenario."
                    ),
                    ref_ids=[scenario_capture_request.saved_scenario_id],
                    payload={
                        "saved_scenario_id": scenario_capture_request.saved_scenario_id,
                        "label": scenario_capture_request.label,
                    },
                )
            )

    workflow_state = WorkflowStateSnapshot(
        workflow_state_id=f"workflow-state:{session_state.session_state_id}:feedback-loop",
        trip_id=session_state.trip_id,
        mode="leisure",
        workflow_kind="leisure_planning",
        current_stage=current_stage,
        status=status,
        recorded_at=generated_at,
        pending_decisions=_map_pending_decisions(session_state.pending_decisions),
        open_action_ids=[
            action.action_id
            for action in actions
            if action.status in {"pending", "in_progress"}
        ],
        completed_action_ids=[
            action.action_id
            for action in actions
            if action.status in {"completed", "skipped"}
        ],
        recent_output_ids=[output.output_id for output in outputs],
        notes=[
            "Feedback loop routes concrete option reactions through explicit workflow state.",
            f"comparison_depth:{event.comparison_depth}",
        ],
        tags=["leisure", "feedback-loop", event.feedback_kind],
    )
    next_step = NextStepSummary(
        headline=_next_step_headline(event),
        recommended_action_id=recommended_action_id,
        expected_output_ids=[output.output_id for output in outputs],
        notes=[
            _comparison_summary(event.comparison_depth),
            f"activity_event:{activity_event.activity_event_id}",
        ],
    )
    transition = WorkflowTransition(
        from_stage="decision_checkpoint" if rerank else "ranking",
        to_stage=current_stage,
        trigger="decision_response",
        changed_at=generated_at,
        reason=event.summary,
        changed_by="planner",
        warning_codes=["feedback_rerank_requested"] if rerank else [],
    )

    return PlannerTurn(
        turn_id=f"planner-turn:{session_state.trip_id}:feedback-loop:{generated_at}",
        trip_id=session_state.trip_id,
        mode="leisure",
        workflow_kind="leisure_planning",
        turn_kind="planning_pass" if rerank else "decision_checkpoint",
        started_at=generated_at,
        workflow_state=workflow_state,
        transition=transition,
        next_step=next_step,
        actions=actions,
        outputs=outputs,
        notes=[
            "Planner feedback remains explicit workflow logic instead of loose chat state.",
            f"presentation:{presentation.presentation_id}",
        ],
    )


def _map_pending_decisions(
    session_decisions: list[SessionPendingDecision],
) -> list[PendingDecision]:
    decisions: list[PendingDecision] = []
    for session_decision in session_decisions:
        choices = [
            DecisionOption(
                choice_id=f"{session_decision.decision_id}:choice:{index + 1}",
                label=choice,
                recommended=index == 0,
            )
            for index, choice in enumerate(session_decision.choices)
        ]
        selected_choice_id = None
        if session_decision.selected_choice is not None:
            for choice in choices:
                if choice.label == session_decision.selected_choice:
                    selected_choice_id = choice.choice_id
                    break
        related_option_ids = []
        if session_decision.related_option_set_id is not None:
            related_option_ids.append(session_decision.related_option_set_id)
        if session_decision.related_saved_scenario_id is not None:
            related_option_ids.append(session_decision.related_saved_scenario_id)
        decisions.append(
            PendingDecision(
                decision_id=session_decision.decision_id,
                prompt=session_decision.prompt,
                requested_at=session_decision.created_at,
                choices=choices,
                blocking=session_decision.blocking,
                selected_choice_id=selected_choice_id,
                due_by=session_decision.due_by,
                notes=list(session_decision.notes),
                related_option_ids=related_option_ids,
            )
        )
    return decisions


def _comparison_summary(comparison_depth: str) -> str:
    if comparison_depth == "quick_preference_check":
        return "Quick preference-learning comparisons should feed the next surfaced options."
    return "Inventory-narrowing comparisons should refresh the ranked candidate set."


def _next_step_headline(event: OptionFeedbackEvent) -> str:
    if event.feedback_kind == "request_alternatives":
        return "Refresh the option set with explicit alternatives."
    if event.feedback_kind == "reject_option":
        return "Rerank the current option set after a concrete rejection."
    if event.feedback_kind == "save_as_fallback":
        return "Persist the selected option as a durable fallback scenario."
    return "Carry the accepted option into the next structured checkpoint."
