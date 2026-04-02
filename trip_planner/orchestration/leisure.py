"""Leisure-planning workflow scaffolds built on shared orchestration contracts."""

from __future__ import annotations

from dataclasses import dataclass

from trip_planner.itinerary import ScenarioSearchResult
from trip_planner.state import PlanningSessionState, PersistedTripRecord

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


@dataclass(slots=True)
class LeisureWorkflowContext:
    """Typed inputs required to build one leisure planner turn."""

    trip_record: PersistedTripRecord
    session_state: PlanningSessionState
    scenario_search: ScenarioSearchResult
    generated_at: str

    def __post_init__(self) -> None:
        if self.trip_record.trip.mode != "leisure":
            raise ValueError("trip_record must represent a leisure trip")
        if self.session_state.mode != "leisure":
            raise ValueError("session_state must represent a leisure session")
        if self.scenario_search.trip_id != self.trip_record.trip.trip_id:
            raise ValueError("scenario_search.trip_id must match trip_record.trip.trip_id")
        if self.session_state.trip_id != self.trip_record.trip.trip_id:
            raise ValueError("session_state.trip_id must match trip_record.trip.trip_id")
        if self.scenario_search.purpose != "final_selection":
            raise ValueError("scenario_search.purpose must be final_selection")
        if not self.scenario_search.scenarios:
            raise ValueError("scenario_search.scenarios must not be empty")
        current_saved = self.session_state.current_saved_scenario_id
        known_saved = set(self.trip_record.artifact_refs.saved_scenario_ids)
        if current_saved is not None and known_saved and current_saved not in known_saved:
            raise ValueError(
                "session_state.current_saved_scenario_id must be present in trip_record artifact_refs"
            )
        scenario_search_id = self.trip_record.artifact_refs.scenario_search_id
        if scenario_search_id is not None and scenario_search_id != self.scenario_search.search_id:
            raise ValueError(
                "trip_record artifact_refs.scenario_search_id must match scenario_search.search_id"
            )


def build_leisure_planner_turn(context: LeisureWorkflowContext) -> PlannerTurn:
    """Build a first-pass leisure orchestration turn from persisted state."""

    trip_id = context.trip_record.trip.trip_id
    session = context.session_state
    variant = _resolve_variant(session)
    decisions = _map_pending_decisions(session)
    actions = _build_actions(context, variant, decisions)
    outputs = _build_outputs(context, variant, decisions)
    open_action_ids = [
        action.action_id
        for action in actions
        if action.status in {"pending", "in_progress"}
    ]
    completed_action_ids = [
        action.action_id
        for action in actions
        if action.status in {"completed", "skipped"}
    ]
    recent_output_ids = [output.output_id for output in outputs]

    workflow_state = WorkflowStateSnapshot(
        workflow_state_id=f"workflow-state:{session.session_state_id}:leisure",
        trip_id=trip_id,
        mode="leisure",
        workflow_kind="leisure_planning",
        current_stage=_current_stage(variant),
        status=_workflow_status(variant),
        recorded_at=context.generated_at,
        pending_decisions=decisions,
        open_action_ids=open_action_ids,
        completed_action_ids=completed_action_ids,
        recent_output_ids=recent_output_ids,
        notes=_workflow_notes(context, variant),
        tags=_workflow_tags(session, variant),
    )
    next_step = _build_next_step(variant, decisions, outputs)
    transition = _build_transition(context, variant)

    return PlannerTurn(
        turn_id=f"planner-turn:{trip_id}:{variant}:{context.generated_at}",
        trip_id=trip_id,
        mode="leisure",
        workflow_kind="leisure_planning",
        turn_kind=_turn_kind(variant),
        started_at=context.generated_at,
        workflow_state=workflow_state,
        transition=transition,
        next_step=next_step,
        actions=actions,
        outputs=outputs,
        notes=_turn_notes(context, variant),
    )


def _resolve_variant(session: PlanningSessionState) -> str:
    if session.pending_decisions:
        return "collaborative_iterative"
    if any(item.rejected_option_ids for item in session.recent_option_presentations):
        return "revised_after_feedback"
    return "delegated_planning"


def _current_stage(variant: str) -> str:
    if variant in {"delegated_planning", "collaborative_iterative"}:
        return "decision_checkpoint"
    return "ranking"


def _workflow_status(variant: str) -> str:
    if variant == "collaborative_iterative":
        return "waiting_on_user"
    return "active"


def _turn_kind(variant: str) -> str:
    if variant == "collaborative_iterative":
        return "decision_checkpoint"
    return "planning_pass"


def _workflow_tags(session: PlanningSessionState, variant: str) -> list[str]:
    tags = ["leisure", "orchestration", variant]
    tags.extend(session.tags)
    return list(dict.fromkeys(tags))


def _workflow_notes(context: LeisureWorkflowContext, variant: str) -> list[str]:
    interaction = context.session_state.interaction_state
    notes = [
        (
            "Leisure orchestration stays downstream from preference resolution, "
            "candidate generation, and scenario ranking."
        ),
        (
            f"interaction_style:{interaction.interaction_style};"
            f"initiative_level:{interaction.initiative_level};"
            f"checkpoint_frequency:{interaction.checkpoint_frequency}"
        ),
        (
            f"scenario_search:{context.scenario_search.search_id};"
            f"scenario_count:{len(context.scenario_search.scenarios)}"
        ),
    ]
    if variant == "revised_after_feedback":
        notes.append("Feedback-triggered revision keeps the workflow stateful and explicit.")
    return notes


def _turn_notes(context: LeisureWorkflowContext, variant: str) -> list[str]:
    latest_presentation = _latest_presentation(context.session_state)
    notes = [
        (
            "This leisure scaffold converts persisted trip/session/scenario artifacts "
            "into an explicit planner turn."
        ),
        f"variant:{variant}",
    ]
    if latest_presentation is not None:
        notes.append(f"latest_presentation:{latest_presentation.presentation_id}")
    return notes


def _map_pending_decisions(session: PlanningSessionState) -> list[PendingDecision]:
    decisions: list[PendingDecision] = []
    for session_decision in session.pending_decisions:
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


def _build_actions(
    context: LeisureWorkflowContext,
    variant: str,
    decisions: list[PendingDecision],
) -> list[PlannerAction]:
    trip_id = context.trip_record.trip.trip_id
    scenario_search = context.scenario_search
    session = context.session_state
    latest_presentation = _latest_presentation(session)
    feedback_option_ids = _feedback_option_ids(session)

    actions = [
        PlannerAction(
            action_id="action-collect-context",
            action_kind="collect_context",
            title="Load persisted leisure session context",
            stage="intake",
            status="completed",
            payload={
                "trip_id": trip_id,
                "session_state_id": session.session_state_id,
                "activity_log_id": session.activity_log_id or "",
            },
        ),
        PlannerAction(
            action_id="action-refresh-preferences",
            action_kind="refresh_preferences",
            title="Refresh leisure interaction and preference posture",
            stage="objective_derivation",
            status="completed",
            payload={
                "interaction_style": session.interaction_state.interaction_style,
                "initiative_level": session.interaction_state.initiative_level,
                "ask_before_major_change": str(
                    session.interaction_state.ask_before_major_change
                ).lower(),
            },
        ),
        PlannerAction(
            action_id="action-derive-objectives",
            action_kind="derive_objectives",
            title="Confirm downstream objectives before scenario review",
            stage="objective_derivation",
            status="completed",
            payload={
                "objective_id": context.trip_record.artifact_refs.objective_id or "",
                "scenario_search_id": scenario_search.search_id,
            },
        ),
        PlannerAction(
            action_id="action-assemble-candidates",
            action_kind="assemble_candidates",
            title="Carry forward ranked leisure scenario candidates",
            stage="candidate_generation",
            status="completed",
            payload={
                "scenario_count": str(len(scenario_search.scenarios)),
                "source_result_set_id": scenario_search.source_result_set_id,
            },
        ),
    ]

    rank_status = "completed"
    rank_notes = [
        "Ranking remains the upstream source of scenario order for the leisure scaffold."
    ]
    if variant == "revised_after_feedback":
        rank_status = "in_progress"
        rank_notes.append(
            "Rejected surfaced options force an explicit reranking pass instead of implicit chat-state mutation."
        )
    actions.append(
        PlannerAction(
            action_id="action-rank-options",
            action_kind="rank_options",
            title="Rank leisure scenarios for the next planner turn",
            stage="ranking",
            status=rank_status,
            notes=rank_notes,
            payload={
                "search_id": scenario_search.search_id,
                "top_scenario_id": scenario_search.scenarios[0].scenario_id,
                "source_refs": ",".join(scenario_search.source_refs),
            },
        )
    )

    if variant == "delegated_planning":
        actions.append(
            PlannerAction(
                action_id="action-persist-state",
                action_kind="persist_state",
                title="Persist a save-ready baseline scenario checkpoint",
                stage="decision_checkpoint",
                status="in_progress",
                depends_on_action_ids=["action-rank-options"],
                notes=[
                    "Delegated planning can auto-advance to a save-ready checkpoint without forcing an immediate user stop."
                ],
                payload={
                    "current_saved_scenario_id": session.current_saved_scenario_id or "",
                    "scenario_search_id": scenario_search.search_id,
                },
            )
        )
    elif variant == "collaborative_iterative":
        decision_ids = [decision.decision_id for decision in decisions]
        actions.extend(
            [
                PlannerAction(
                    action_id="action-request-decision",
                    action_kind="request_decision",
                    title="Request a collaborative checkpoint before scenario save",
                    stage="decision_checkpoint",
                    status="in_progress",
                    depends_on_action_ids=["action-rank-options"],
                    payload={
                        "decision_ids": ",".join(decision_ids),
                        "latest_option_set_id": (
                            latest_presentation.option_set_id
                            if latest_presentation is not None
                            else ""
                        ),
                    },
                ),
                PlannerAction(
                    action_id="action-persist-state",
                    action_kind="persist_state",
                    title="Persist the chosen collaborative scenario after approval",
                    stage="decision_checkpoint",
                    status="pending",
                    depends_on_action_ids=["action-request-decision"],
                    payload={
                        "decision_ids": ",".join(decision_ids),
                        "current_saved_scenario_id": session.current_saved_scenario_id
                        or "",
                    },
                ),
            ]
        )
    else:
        actions.append(
            PlannerAction(
                action_id="action-record-warning",
                action_kind="record_warning",
                title="Record revision-driving leisure feedback",
                stage="ranking",
                status="completed",
                depends_on_action_ids=["action-collect-context"],
                payload={
                    "rejected_option_ids": ",".join(feedback_option_ids),
                    "presentation_id": (
                        latest_presentation.presentation_id
                        if latest_presentation is not None
                        else ""
                    ),
                },
            )
        )

    return actions


def _build_outputs(
    context: LeisureWorkflowContext,
    variant: str,
    decisions: list[PendingDecision],
) -> list[PlannerOutput]:
    scenario_search = context.scenario_search
    session = context.session_state
    outputs: list[PlannerOutput] = []

    if variant != "revised_after_feedback":
        outputs.append(
            PlannerOutput(
                output_id="output-ranked-scenarios",
                output_kind="ranked_scenarios",
                title="Ranked leisure scenarios ready for orchestration",
                emitted_at=context.generated_at,
                surface="side_panel",
                summary=(
                    f"{len(scenario_search.scenarios)} ranked leisure scenarios remain "
                    "downstream from preference learning and route ranking."
                ),
                ref_ids=[
                    scenario_search.search_id,
                    scenario_search.source_result_set_id,
                ],
                payload={
                    "search_id": scenario_search.search_id,
                    "scenario_ids": [
                        scenario.scenario_id for scenario in scenario_search.scenarios
                    ],
                    "recommended_scenario_id": scenario_search.scenarios[0].scenario_id,
                    "saved_scenario_id": session.current_saved_scenario_id or "",
                },
            )
        )

    if variant == "delegated_planning":
        outputs.append(
            PlannerOutput(
                output_id="output-delegated-status",
                output_kind="status_update",
                title="Delegated leisure flow is ready to save a baseline",
                emitted_at=context.generated_at,
                surface="planner_chat",
                summary=(
                    "Planner-first leisure mode can advance from ranked scenarios to "
                    "a save-ready checkpoint without inventing extra chat state."
                ),
                ref_ids=["action-persist-state", scenario_search.search_id],
                payload={
                    "auto_advance_research_passes": session.interaction_state.auto_advance_research_passes,
                    "checkpoint_frequency": session.interaction_state.checkpoint_frequency,
                },
            )
        )
    elif variant == "collaborative_iterative":
        outputs.append(
            PlannerOutput(
                output_id="output-decision-request",
                output_kind="decision_request",
                title="Collaborative checkpoint requested before scenario save",
                emitted_at=context.generated_at,
                surface="planner_chat",
                summary="The planner pauses at a structured checkpoint so the traveler can steer the next save/revise step.",
                ref_ids=[decision.decision_id for decision in decisions],
                payload={
                    "decision_ids": [decision.decision_id for decision in decisions],
                    "blocking_decision_ids": [
                        decision.decision_id
                        for decision in decisions
                        if decision.blocking
                    ],
                },
            )
        )
    else:
        outputs.extend(
            [
                PlannerOutput(
                    output_id="output-feedback-warning",
                    output_kind="warning",
                    title="Feedback-triggered reranking remains unresolved",
                    emitted_at=context.generated_at,
                    surface="planner_chat",
                    summary=(
                        "Rejected surfaced options triggered a new ranking pass instead "
                        "of silently mutating the prior scenario choice."
                    ),
                    warnings=["feedback_rejected_option_set"],
                    payload={
                        "rejected_option_ids": _feedback_option_ids(session),
                        "presentation_id": (
                            _latest_presentation(session).presentation_id
                            if _latest_presentation(session) is not None
                            else ""
                        ),
                    },
                ),
                PlannerOutput(
                    output_id="output-revision-status",
                    output_kind="status_update",
                    title="Leisure workflow is recomputing ranked scenarios",
                    emitted_at=context.generated_at,
                    surface="timeline",
                    summary=(
                        "Preference feedback, saved state, and scenario history stay "
                        "separate while the workflow recomputes the next ranked pass."
                    ),
                    ref_ids=["action-rank-options", scenario_search.search_id],
                    payload={
                        "search_id": scenario_search.search_id,
                        "current_saved_scenario_id": session.current_saved_scenario_id
                        or "",
                    },
                ),
            ]
        )

    return outputs


def _build_next_step(
    variant: str,
    decisions: list[PendingDecision],
    outputs: list[PlannerOutput],
) -> NextStepSummary:
    if variant == "delegated_planning":
        return NextStepSummary(
            headline="Persist the current save-ready leisure baseline.",
            recommended_action_id="action-persist-state",
            expected_output_ids=[output.output_id for output in outputs],
            notes=[
                "Delegated leisure planning can continue to checkpoint persistence without an immediate user stop."
            ],
        )
    if variant == "collaborative_iterative":
        return NextStepSummary(
            headline="Resolve the active traveler checkpoint before saving the scenario.",
            recommended_action_id="action-request-decision",
            blocking_decision_ids=[decision.decision_id for decision in decisions],
            expected_output_ids=[output.output_id for output in outputs],
            notes=[
                "Collaborative mode surfaces a structured choice set before advancing the session."
            ],
        )
    return NextStepSummary(
        headline="Re-rank leisure scenarios after the latest traveler feedback.",
        recommended_action_id="action-rank-options",
        expected_output_ids=[output.output_id for output in outputs],
        notes=[
            "Revision remains explicit: feedback changes ranking inputs instead of mutating the saved scenario in place."
        ],
    )


def _build_transition(
    context: LeisureWorkflowContext,
    variant: str,
) -> WorkflowTransition:
    if variant == "delegated_planning":
        return WorkflowTransition(
            from_stage="ranking",
            to_stage="decision_checkpoint",
            trigger="planner_recommendation",
            changed_at=context.generated_at,
            reason="Ranked leisure scenarios are ready for a delegated save-ready checkpoint.",
            changed_by="planner",
        )
    if variant == "collaborative_iterative":
        return WorkflowTransition(
            from_stage="ranking",
            to_stage="decision_checkpoint",
            trigger="checkpoint_due",
            changed_at=context.generated_at,
            reason="Checkpoint-heavy collaboration pauses the leisure flow for a structured traveler decision.",
            changed_by="planner",
        )
    return WorkflowTransition(
        from_stage="decision_checkpoint",
        to_stage="ranking",
        trigger="decision_response",
        changed_at=context.generated_at,
        reason="Traveler feedback rejected surfaced options, so the planner is recomputing ranked leisure scenarios.",
        changed_by="planner",
        warning_codes=["feedback_rejected_option_set"],
    )


def _latest_presentation(session: PlanningSessionState):
    if not session.recent_option_presentations:
        return None
    return max(session.recent_option_presentations, key=lambda item: item.shown_at)


def _feedback_option_ids(session: PlanningSessionState) -> list[str]:
    option_ids: list[str] = []
    for presentation in session.recent_option_presentations:
        option_ids.extend(presentation.rejected_option_ids)
    return list(dict.fromkeys(option_ids))
