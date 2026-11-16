"""Business-planning workflow scaffolds built on shared orchestration contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from trip_planner.business import (
    BusinessPlanningObjectives,
    BusinessTravelProfile,
    PolicyConstraintSet,
    TripPlanProposal,
)
from trip_planner.contracts._validators import (
    require_non_empty,
    require_string_mapping,
)
from trip_planner.state import PersistedTripRecord

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

BUSINESS_PATHS: tuple[str, ...] = ("compliant_first", "exception_nearest")
BUSINESS_WORKFLOW_PHASES: tuple[str, ...] = (
    "profile_confirmation",
    "policy_input_assembly",
    "comparable_collection",
    "ranked_option_review",
    "proposal_preparation",
    "fallback_or_exception_preparation",
)


@dataclass(slots=True)
class BusinessWorkflowContext:
    """Typed inputs required to build one business planner turn."""

    trip_record: PersistedTripRecord
    business_profile: BusinessTravelProfile
    objectives: BusinessPlanningObjectives
    generated_at: str
    constraint_set: PolicyConstraintSet | None = None
    proposal: TripPlanProposal | None = None
    comparable_inventory: dict[str, int] = field(default_factory=dict)
    collected_policy_inputs: dict[str, str] = field(default_factory=dict)
    selected_path: str = "compliant_first"

    def __post_init__(self) -> None:
        if not isinstance(self.trip_record, PersistedTripRecord):
            raise ValueError("trip_record must be a PersistedTripRecord")
        if self.trip_record.trip.mode != "business":
            raise ValueError("trip_record must represent a business trip")
        if not isinstance(self.business_profile, BusinessTravelProfile):
            raise ValueError("business_profile must be a BusinessTravelProfile")
        if not isinstance(self.objectives, BusinessPlanningObjectives):
            raise ValueError("objectives must be a BusinessPlanningObjectives")
        _validate_generated_at(self.generated_at)
        if self.objectives.trip_id != self.trip_record.trip.trip_id:
            raise ValueError("objectives.trip_id must match trip_record.trip.trip_id")
        if self.constraint_set is not None and not isinstance(
            self.constraint_set, PolicyConstraintSet
        ):
            raise ValueError("constraint_set must be a PolicyConstraintSet when provided")
        if self.proposal is not None:
            if not isinstance(self.proposal, TripPlanProposal):
                raise ValueError("proposal must be a TripPlanProposal when provided")
            if self.proposal.trip_id != self.trip_record.trip.trip_id:
                raise ValueError("proposal.trip_id must match trip_record.trip.trip_id")
            if self.constraint_set is not None:
                if self.proposal.constraint_set_id != self.constraint_set.policy_id:
                    raise ValueError(
                        "proposal.constraint_set_id must match constraint_set.policy_id"
                    )
        if self.selected_path not in BUSINESS_PATHS:
            raise ValueError(f"selected_path must be one of {BUSINESS_PATHS}")
        if (
            self.selected_path == "exception_nearest"
            and not self.objectives.policy_nearest_fallback.active
            and self.proposal is None
        ):
            raise ValueError(
                "selected_path exception_nearest requires an active fallback or proposal"
            )
        require_string_mapping(self.collected_policy_inputs, "collected_policy_inputs")
        for key, value in self.collected_policy_inputs.items():
            require_non_empty(key, "collected_policy_inputs key")
            require_non_empty(str(value), f"collected_policy_inputs[{key}]")
        if not isinstance(self.comparable_inventory, dict):
            raise ValueError("comparable_inventory must be a mapping")
        for key, count in self.comparable_inventory.items():
            require_non_empty(key, "comparable_inventory key")
            if isinstance(count, bool) or not isinstance(count, int):
                raise ValueError(f"comparable_inventory[{key}] must be an int")
            if count < 0:
                raise ValueError(f"comparable_inventory[{key}] must be non-negative")


def build_business_planner_turn(context: BusinessWorkflowContext) -> PlannerTurn:
    """Build a first-pass business orchestration turn from persisted state."""

    trip_id = context.trip_record.trip.trip_id
    missing_policy_inputs = _missing_policy_inputs(context)
    comparable_gaps = _comparable_gaps(context)
    pending_decisions = _build_pending_decisions(
        context,
        missing_policy_inputs,
        comparable_gaps,
    )
    current_stage = _current_stage(context, missing_policy_inputs, comparable_gaps)
    workflow_status = _workflow_status(context, pending_decisions)
    phase_statuses = _phase_statuses(
        context,
        missing_policy_inputs,
        comparable_gaps,
    )
    actions = _build_actions(
        context,
        phase_statuses,
        missing_policy_inputs,
        comparable_gaps,
        pending_decisions,
    )
    outputs = _build_outputs(
        context,
        phase_statuses,
        missing_policy_inputs,
        comparable_gaps,
        pending_decisions,
    )
    open_action_ids = [
        action.action_id for action in actions if action.status in {"pending", "in_progress"}
    ]
    completed_action_ids = [
        action.action_id for action in actions if action.status in {"completed", "skipped"}
    ]
    recent_output_ids = [output.output_id for output in outputs]

    workflow_state = WorkflowStateSnapshot(
        workflow_state_id=f"workflow-state:{trip_id}:business",
        trip_id=trip_id,
        mode="business",
        workflow_kind="business_planning",
        current_stage=current_stage,
        status=workflow_status,
        recorded_at=context.generated_at,
        pending_decisions=pending_decisions,
        open_action_ids=open_action_ids,
        completed_action_ids=completed_action_ids,
        recent_output_ids=recent_output_ids,
        notes=_workflow_notes(
            context,
            phase_statuses,
            missing_policy_inputs,
            comparable_gaps,
        ),
        tags=_workflow_tags(context, comparable_gaps, pending_decisions),
    )
    next_step = _build_next_step(
        context,
        missing_policy_inputs,
        comparable_gaps,
        pending_decisions,
        outputs,
    )
    transition = _build_transition(
        context,
        current_stage,
        missing_policy_inputs,
        comparable_gaps,
    )

    return PlannerTurn(
        turn_id=f"planner-turn:{trip_id}:business:{context.generated_at}",
        trip_id=trip_id,
        mode="business",
        workflow_kind="business_planning",
        turn_kind="decision_checkpoint" if pending_decisions else "planning_pass",
        started_at=context.generated_at,
        workflow_state=workflow_state,
        transition=transition,
        next_step=next_step,
        actions=actions,
        outputs=outputs,
        notes=_turn_notes(context, phase_statuses),
    )


def _validate_generated_at(value: str) -> None:
    require_non_empty(value, "generated_at")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("generated_at must be an ISO-8601 timestamp") from exc


def _slug(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")


def _policy_input_decision_id(field_name: str) -> str:
    return f"decision:policy-input:{_slug(field_name)}"


def _comparable_decision_id(category: str) -> str:
    return f"decision:comparables:{_slug(category)}"


def _missing_comparable_warning_code(category: str) -> str:
    return f"missing-comparable:{category}"


def _missing_policy_inputs(context: BusinessWorkflowContext) -> list[str]:
    required_fields = context.objectives.justification_readiness.required_fields
    return [
        field_name
        for field_name in required_fields
        if field_name not in context.collected_policy_inputs
    ]


def _comparable_gaps(context: BusinessWorkflowContext) -> dict[str, int]:
    gaps: dict[str, int] = {}
    for (
        category,
        required_count,
    ) in context.objectives.comparable_requirements.required_categories.items():
        available = context.comparable_inventory.get(category, 0)
        shortfall = required_count - available
        if shortfall > 0:
            gaps[category] = shortfall
    return gaps


def _needs_exception_path(context: BusinessWorkflowContext) -> bool:
    return context.selected_path == "exception_nearest" or (
        context.proposal is not None and context.proposal.requested_exception is not None
    )


def _phase_statuses(
    context: BusinessWorkflowContext,
    missing_policy_inputs: list[str],
    comparable_gaps: dict[str, int],
) -> dict[str, str]:
    proposal_ready = not missing_policy_inputs and not comparable_gaps
    fallback_status = "pending"
    if _needs_exception_path(context):
        fallback_status = "completed" if context.proposal is not None else "in_progress"
    elif context.objectives.policy_nearest_fallback.active:
        fallback_status = "ready"

    return {
        "profile_confirmation": "completed",
        "policy_input_assembly": ("completed" if not missing_policy_inputs else "in_progress"),
        "comparable_collection": "completed" if not comparable_gaps else "in_progress",
        "ranked_option_review": (
            "completed"
            if context.trip_record.artifact_refs.ranked_result_set_id is not None
            else "pending"
        ),
        "proposal_preparation": (
            "completed"
            if context.proposal is not None
            else ("ready" if proposal_ready else "pending")
        ),
        "fallback_or_exception_preparation": fallback_status,
    }


def _current_stage(
    context: BusinessWorkflowContext,
    missing_policy_inputs: list[str],
    comparable_gaps: dict[str, int],
) -> str:
    if missing_policy_inputs:
        return "objective_derivation"
    if comparable_gaps:
        return "candidate_generation"
    if _needs_exception_path(context):
        return "policy_alignment"
    return "booking_prep"


def _workflow_status(
    context: BusinessWorkflowContext,
    pending_decisions: list[PendingDecision],
) -> str:
    if pending_decisions:
        return "waiting_on_user"
    if (
        _needs_exception_path(context)
        and context.proposal is None
        and not context.objectives.policy_nearest_fallback.active
    ):
        return "blocked"
    return "active"


def _workflow_tags(
    context: BusinessWorkflowContext,
    comparable_gaps: dict[str, int],
    pending_decisions: list[PendingDecision],
) -> list[str]:
    tags = [
        "business",
        "orchestration",
        context.selected_path,
        context.business_profile.trip_purpose.purpose_type,
    ]
    if comparable_gaps:
        tags.append("comparables_required")
    if pending_decisions:
        tags.append("policy_inputs_pending")
    if _needs_exception_path(context):
        tags.append("exception_path")
    return tags


def _workflow_notes(
    context: BusinessWorkflowContext,
    phase_statuses: dict[str, str],
    missing_policy_inputs: list[str],
    comparable_gaps: dict[str, int],
) -> list[str]:
    notes = [
        (
            "Business orchestration remains distinct from external policy evaluation; "
            "this scaffold prepares proposal-ready state without making final approvals."
        ),
        "phase_statuses:"
        + ",".join(f"{phase}:{status}" for phase, status in phase_statuses.items()),
        f"selected_path:{context.selected_path}",
        (
            f"policy_state_id:{context.trip_record.artifact_refs.policy_state_id or 'missing'};"
            f"saved_scenario_ids:{len(context.trip_record.artifact_refs.saved_scenario_ids)}"
        ),
    ]
    if missing_policy_inputs:
        notes.append("missing_policy_inputs:" + ",".join(missing_policy_inputs))
    if comparable_gaps:
        notes.append(
            "comparable_shortfalls:"
            + ",".join(f"{key}:{value}" for key, value in sorted(comparable_gaps.items()))
        )
    return notes


def _turn_notes(
    context: BusinessWorkflowContext,
    phase_statuses: dict[str, str],
) -> list[str]:
    active_phase = next(
        (
            phase
            for phase, status in phase_statuses.items()
            if status in {"in_progress", "ready", "pending"}
        ),
        "proposal_preparation",
    )
    return [
        (
            "This scaffold converts business profile, objective, policy, proposal, "
            "and saved-state references into an explicit planner turn."
        ),
        f"selected_path:{context.selected_path}",
        "active_phase:" + active_phase,
    ]


def _build_pending_decisions(
    context: BusinessWorkflowContext,
    missing_policy_inputs: list[str],
    comparable_gaps: dict[str, int],
) -> list[PendingDecision]:
    decisions: list[PendingDecision] = []
    related_ids = list(context.trip_record.artifact_refs.option_set_ids)
    if context.trip_record.artifact_refs.policy_state_id is not None:
        related_ids.append(context.trip_record.artifact_refs.policy_state_id)

    for field_name in missing_policy_inputs:
        decision_slug = _slug(field_name)
        decisions.append(
            PendingDecision(
                decision_id=_policy_input_decision_id(field_name),
                prompt=f"Provide the policy-ready detail for {field_name}.",
                requested_at=context.generated_at,
                choices=[
                    DecisionOption(
                        choice_id=f"choice:{decision_slug}:capture",
                        label=f"Capture {field_name}",
                        description="Collect the required policy-facing detail now.",
                        recommended=True,
                        metadata={"field": field_name, "path": context.selected_path},
                    ),
                    DecisionOption(
                        choice_id=f"choice:{decision_slug}:defer",
                        label="Defer and block proposal prep",
                        description="Leave the proposal packet incomplete until later.",
                        metadata={"field": field_name, "path": context.selected_path},
                    ),
                ],
                notes=[
                    "Required for structured policy-ready proposal preparation.",
                ],
                related_option_ids=related_ids,
            )
        )

    for category, shortfall in sorted(comparable_gaps.items()):
        decision_slug = _slug(category)
        required_total = context.objectives.comparable_requirements.required_categories[category]
        decisions.append(
            PendingDecision(
                decision_id=_comparable_decision_id(category),
                prompt=(
                    f"Collect {shortfall} more {category} comparable"
                    f"{'s' if shortfall != 1 else ''} before proposal prep?"
                ),
                requested_at=context.generated_at,
                choices=[
                    DecisionOption(
                        choice_id=f"choice:{decision_slug}:collect",
                        label=f"Collect missing {category} comparables",
                        description="Keep the packet compliant-first by filling the shortfall.",
                        recommended=True,
                        metadata={
                            "category": category,
                            "required_total": required_total,
                            "current_total": context.comparable_inventory.get(category, 0),
                        },
                    ),
                    DecisionOption(
                        choice_id=f"choice:{decision_slug}:escalate",
                        label="Carry shortfall into exception prep",
                        description="Escalate with an explicit explanation of the comparable gap.",
                        metadata={
                            "category": category,
                            "shortfall": shortfall,
                            "path": context.selected_path,
                        },
                    ),
                ],
                notes=[
                    "Comparable collection stays explicit so the policy packet can be audited.",
                ],
                related_option_ids=related_ids,
            )
        )

    return decisions


def _build_actions(
    context: BusinessWorkflowContext,
    phase_statuses: dict[str, str],
    missing_policy_inputs: list[str],
    comparable_gaps: dict[str, int],
    pending_decisions: list[PendingDecision],
) -> list[PlannerAction]:
    policy_id = context.constraint_set.policy_id if context.constraint_set else ""
    proposal_id = context.proposal.proposal_id if context.proposal else ""

    actions = [
        PlannerAction(
            action_id="action-confirm-business-profile",
            action_kind="collect_context",
            title="Confirm business profile, trip, and saved-state context",
            stage="intake",
            status="completed",
            payload={
                "business_profile_id": context.trip_record.trip.profile_refs.business_profile_id
                or "",
                "objective_id": context.trip_record.artifact_refs.objective_id or "",
                "policy_state_id": context.trip_record.artifact_refs.policy_state_id or "",
                "saved_scenario_ids": context.trip_record.artifact_refs.saved_scenario_ids,
            },
        ),
        PlannerAction(
            action_id="action-assemble-policy-inputs",
            action_kind="collect_context",
            title="Assemble structured policy inputs for the planning packet",
            stage="objective_derivation",
            status="completed" if not missing_policy_inputs else "in_progress",
            depends_on_action_ids=["action-confirm-business-profile"],
            payload={
                "required_fields": context.objectives.justification_readiness.required_fields,
                "captured_fields": sorted(context.collected_policy_inputs),
                "missing_fields": missing_policy_inputs,
                "policy_id": policy_id,
            },
        ),
        PlannerAction(
            action_id="action-collect-comparables",
            action_kind="assemble_candidates",
            title="Collect comparable options for the active business path",
            stage="candidate_generation",
            status="completed" if not comparable_gaps else "in_progress",
            depends_on_action_ids=["action-assemble-policy-inputs"],
            payload={
                "required_categories": context.objectives.comparable_requirements.required_categories,
                "available_counts": context.comparable_inventory,
                "shortfalls": comparable_gaps,
            },
        ),
        PlannerAction(
            action_id="action-review-ranked-options",
            action_kind="rank_options",
            title="Review ranked compliant-first and fallback business options",
            stage="ranking",
            status=(
                "completed"
                if context.trip_record.artifact_refs.ranked_result_set_id is not None
                else "pending"
            ),
            depends_on_action_ids=["action-collect-comparables"],
            payload={
                "ranked_result_set_id": context.trip_record.artifact_refs.ranked_result_set_id
                or "",
                "option_set_ids": context.trip_record.artifact_refs.option_set_ids,
                "selected_path": context.selected_path,
            },
        ),
        PlannerAction(
            action_id="action-prepare-policy-packet",
            action_kind="prepare_policy_summary",
            title="Prepare the policy-facing proposal packet",
            stage="policy_alignment",
            status=(
                "completed"
                if context.proposal is not None and not pending_decisions
                else ("in_progress" if not pending_decisions else "pending")
            ),
            depends_on_action_ids=["action-review-ranked-options"],
            payload={
                "proposal_id": proposal_id,
                "constraint_set_id": (
                    context.proposal.constraint_set_id
                    if context.proposal is not None
                    and context.proposal.constraint_set_id is not None
                    else policy_id
                ),
                "phase_status": phase_statuses["proposal_preparation"],
            },
        ),
        PlannerAction(
            action_id="action-request-path-decision",
            action_kind="request_decision",
            title="Confirm the remaining policy-input and comparable checkpoints",
            stage="decision_checkpoint",
            status="pending" if pending_decisions else "skipped",
            depends_on_action_ids=["action-prepare-policy-packet"],
            payload={
                "decision_ids": [decision.decision_id for decision in pending_decisions],
                "selected_path": context.selected_path,
            },
        ),
        PlannerAction(
            action_id="action-persist-business-state",
            action_kind="persist_state",
            title="Persist proposal-prep outputs back into saved-state layers",
            stage="booking_prep",
            status=(
                "pending" if context.proposal is not None and not pending_decisions else "skipped"
            ),
            depends_on_action_ids=["action-prepare-policy-packet"],
            payload={
                "policy_state_id": context.trip_record.artifact_refs.policy_state_id or "",
                "saved_scenario_ids": context.trip_record.artifact_refs.saved_scenario_ids,
                "session_state_id": context.trip_record.artifact_refs.session_state_id or "",
            },
        ),
    ]
    return actions


def _build_outputs(
    context: BusinessWorkflowContext,
    phase_statuses: dict[str, str],
    missing_policy_inputs: list[str],
    comparable_gaps: dict[str, int],
    pending_decisions: list[PendingDecision],
) -> list[PlannerOutput]:
    outputs: list[PlannerOutput] = []
    packet_ref_ids = list(context.trip_record.artifact_refs.option_set_ids)
    if context.trip_record.artifact_refs.policy_state_id is not None:
        packet_ref_ids.append(context.trip_record.artifact_refs.policy_state_id)
    packet_ref_ids.extend(context.trip_record.artifact_refs.saved_scenario_ids)
    if context.proposal is not None:
        packet_ref_ids.insert(0, context.proposal.proposal_id)

    outputs.append(
        PlannerOutput(
            output_id="output-business-status",
            output_kind="status_update",
            title="Business workflow scaffold status",
            emitted_at=context.generated_at,
            surface="side_panel",
            summary=(
                "Business planning is staging profile, policy, comparable, ranked-option, "
                "proposal, and fallback phases explicitly."
            ),
            ref_ids=packet_ref_ids,
            payload={
                "selected_path": context.selected_path,
                "phase_statuses": phase_statuses,
                "policy_state_id": context.trip_record.artifact_refs.policy_state_id or "",
                "objective_id": context.trip_record.artifact_refs.objective_id or "",
            },
        )
    )

    if context.proposal is not None or (not missing_policy_inputs and not comparable_gaps):
        outputs.insert(
            0,
            PlannerOutput(
                output_id="output-policy-packet",
                output_kind="policy_summary",
                title="Policy-ready business proposal scaffold",
                emitted_at=context.generated_at,
                surface="policy_packet",
                summary=(
                    "The scaffold carries business planning forward as a policy-ready packet "
                    "without performing the external policy evaluation."
                ),
                ref_ids=packet_ref_ids,
                warnings=[
                    _missing_comparable_warning_code(category)
                    for category in sorted(comparable_gaps)
                ],
                payload={
                    "selected_path": context.selected_path,
                    "proposal_id": (context.proposal.proposal_id if context.proposal else ""),
                    "constraint_set_id": (
                        context.proposal.constraint_set_id
                        if context.proposal is not None
                        and context.proposal.constraint_set_id is not None
                        else (
                            context.constraint_set.policy_id
                            if context.constraint_set is not None
                            else ""
                        )
                    ),
                    "required_approval_roles": (
                        context.objectives.exception_path_posture.approval_roles
                    ),
                    "missing_policy_inputs": missing_policy_inputs,
                    "comparable_shortfalls": comparable_gaps,
                    "saved_scenario_ids": context.trip_record.artifact_refs.saved_scenario_ids,
                    "policy_state_id": context.trip_record.artifact_refs.policy_state_id or "",
                    "external_policy_evaluation_required": True,
                    "requested_exception_type": (
                        context.proposal.requested_exception.exception_type
                        if context.proposal is not None
                        and context.proposal.requested_exception is not None
                        else ""
                    ),
                },
            ),
        )

    if pending_decisions:
        outputs.append(
            PlannerOutput(
                output_id="output-policy-decisions",
                output_kind="decision_request",
                title="Structured policy-input decisions required",
                emitted_at=context.generated_at,
                surface="planner_chat",
                summary=(
                    "Missing policy inputs and comparable gaps are surfaced as "
                    "structured checkpoint decisions."
                ),
                ref_ids=[decision.decision_id for decision in pending_decisions],
                payload={
                    "decision_ids": [decision.decision_id for decision in pending_decisions],
                    "selected_path": context.selected_path,
                },
            )
        )

    if comparable_gaps or _needs_exception_path(context):
        outputs.append(
            PlannerOutput(
                output_id="output-business-warning",
                output_kind="warning",
                title="Business policy path needs explicit handling",
                emitted_at=context.generated_at,
                surface="planner_chat",
                summary=(
                    "The business workflow keeps comparable shortfalls and exception routing "
                    "visible instead of collapsing them into free-form notes."
                ),
                ref_ids=packet_ref_ids,
                warnings=[
                    *(
                        _missing_comparable_warning_code(category)
                        for category in sorted(comparable_gaps)
                    ),
                    *(["exception-path-active"] if _needs_exception_path(context) else []),
                ],
                payload={
                    "comparable_shortfalls": comparable_gaps,
                    "selected_path": context.selected_path,
                    "exception_ready": _needs_exception_path(context),
                },
            )
        )

    return outputs


def _build_next_step(
    context: BusinessWorkflowContext,
    missing_policy_inputs: list[str],
    comparable_gaps: dict[str, int],
    pending_decisions: list[PendingDecision],
    outputs: list[PlannerOutput],
) -> NextStepSummary:
    output_ids = [output.output_id for output in outputs]
    if missing_policy_inputs:
        return NextStepSummary(
            headline="Capture the missing policy-ready inputs before preparing the business proposal packet.",
            recommended_action_id="action-assemble-policy-inputs",
            blocking_decision_ids=[decision.decision_id for decision in pending_decisions],
            expected_output_ids=output_ids,
        )
    if comparable_gaps:
        return NextStepSummary(
            headline="Collect the remaining comparables or explicitly escalate the shortfall into exception prep.",
            recommended_action_id="action-collect-comparables",
            blocking_decision_ids=[decision.decision_id for decision in pending_decisions],
            expected_output_ids=output_ids,
        )
    if _needs_exception_path(context):
        return NextStepSummary(
            headline="Finish the exception-nearest policy packet and keep the fallback path explicit for later review.",
            recommended_action_id="action-prepare-policy-packet",
            blocking_decision_ids=[decision.decision_id for decision in pending_decisions],
            expected_output_ids=output_ids,
        )
    if context.proposal is None:
        return NextStepSummary(
            headline="Prepare the compliant-first policy packet and persist its saved-state references.",
            recommended_action_id="action-prepare-policy-packet",
            expected_output_ids=output_ids,
        )
    return NextStepSummary(
        headline="Persist the policy-ready business packet back into saved-state layers.",
        recommended_action_id="action-persist-business-state",
        expected_output_ids=output_ids,
    )


def _build_transition(
    context: BusinessWorkflowContext,
    current_stage: str,
    missing_policy_inputs: list[str],
    comparable_gaps: dict[str, int],
) -> WorkflowTransition:
    if missing_policy_inputs:
        return WorkflowTransition(
            from_stage="intake",
            to_stage="objective_derivation",
            trigger="policy_constraint",
            changed_at=context.generated_at,
            reason="Business planning cannot prepare a packet until required policy inputs are captured.",
            blocker_ids=[_policy_input_decision_id(name) for name in missing_policy_inputs],
        )
    if comparable_gaps:
        return WorkflowTransition(
            from_stage="ranking",
            to_stage="candidate_generation",
            trigger="policy_constraint",
            changed_at=context.generated_at,
            reason="Comparable collection remains incomplete for the active business path.",
            blocker_ids=[_comparable_decision_id(category) for category in sorted(comparable_gaps)],
            warning_codes=[
                _missing_comparable_warning_code(category) for category in sorted(comparable_gaps)
            ],
        )
    if current_stage == "policy_alignment":
        return WorkflowTransition(
            from_stage="ranking",
            to_stage="policy_alignment",
            trigger="policy_constraint",
            changed_at=context.generated_at,
            reason="The selected business path needs explicit exception or fallback preparation.",
            warning_codes=["exception-path-active"],
        )
    return WorkflowTransition(
        from_stage="ranking",
        to_stage="booking_prep",
        trigger="planner_recommendation",
        changed_at=context.generated_at,
        reason="Ranked business options are ready to be assembled into a policy-facing proposal packet.",
    )
