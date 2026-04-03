import json
from copy import deepcopy
from pathlib import Path

import pytest

from trip_planner.business import (
    BusinessTravelProfile,
    PolicyConstraintSet,
    TripPlanProposal,
    derive_business_planning_objectives,
)
from trip_planner.orchestration import (
    BUSINESS_PATHS,
    BusinessWorkflowContext,
    build_business_planner_turn,
)
from trip_planner.state import PersistedTripRecord


def _fixture_root() -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _deep_merge(base: dict, overrides: dict) -> dict:
    merged = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _load_scenario(name: str) -> dict:
    return _load_json(_fixture_root() / "orchestration" / "business" / name)


def _build_context(name: str) -> BusinessWorkflowContext:
    scenario = _load_scenario(name)
    trip_payload = _load_json(
        _fixture_root() / "state" / "trips" / scenario["trip_fixture"]
    )
    if "trip_overrides" in scenario:
        trip_payload = _deep_merge(trip_payload, scenario["trip_overrides"])
    trip_record = PersistedTripRecord.from_dict(trip_payload)

    profile_payload = _load_json(
        _fixture_root() / "business" / scenario["profile_fixture"]
    )
    profile = BusinessTravelProfile.from_dict(profile_payload)

    policy_payload = _load_json(
        _fixture_root() / "business" / scenario["policy_fixture"]
    )
    constraint_set = PolicyConstraintSet(**policy_payload["constraint_set"])
    objectives = derive_business_planning_objectives(
        profile,
        trip_id=trip_record.trip.trip_id,
        constraint_set=constraint_set,
    )

    proposal = None
    proposal_fixture = scenario.get("proposal_policy_fixture")
    if proposal_fixture is not None:
        proposal_payload = _load_json(_fixture_root() / "business" / proposal_fixture)
        proposal_dict = deepcopy(proposal_payload["proposal"])
        proposal_dict["trip_id"] = trip_record.trip.trip_id
        proposal_dict["constraint_set_id"] = constraint_set.policy_id
        proposal = TripPlanProposal.from_dict(proposal_dict)

    return BusinessWorkflowContext(
        trip_record=trip_record,
        business_profile=profile,
        objectives=objectives,
        generated_at=scenario["generated_at"],
        constraint_set=constraint_set,
        proposal=proposal,
        comparable_inventory=scenario["comparable_inventory"],
        collected_policy_inputs=scenario["collected_policy_inputs"],
        selected_path=scenario["selected_path"],
    )


def test_business_paths_export_expected_values() -> None:
    assert BUSINESS_PATHS == ("compliant_first", "exception_nearest")


def test_compliant_business_flow_transitions_to_policy_ready_booking_prep() -> None:
    turn = build_business_planner_turn(_build_context("compliant_flow.json"))

    assert turn.turn_kind == "planning_pass"
    assert turn.workflow_state.current_stage == "booking_prep"
    assert turn.workflow_state.status == "active"
    assert turn.next_step.recommended_action_id == "action-persist-business-state"
    assert turn.outputs[0].output_kind == "policy_summary"
    assert turn.outputs[0].payload["policy_state_id"] == "policy-state:conference-001"
    assert turn.outputs[0].payload["saved_scenario_ids"] == [
        "saved-scenario:conference-compliant"
    ]
    assert turn.actions[4].status == "completed"
    assert turn.actions[6].status == "pending"


def test_missing_comparable_flow_surfaces_structured_pending_decisions() -> None:
    turn = build_business_planner_turn(_build_context("missing_comparables_flow.json"))

    assert turn.turn_kind == "decision_checkpoint"
    assert turn.workflow_state.current_stage == "objective_derivation"
    assert turn.workflow_state.status == "waiting_on_user"
    assert turn.next_step.recommended_action_id == "action-assemble-policy-inputs"
    assert len(turn.workflow_state.pending_decisions) == 5
    assert turn.outputs[1].output_kind == "decision_request"
    assert turn.outputs[2].output_kind == "warning"
    input_fields = {
        decision.choices[0].metadata["field"]
        for decision in turn.workflow_state.pending_decisions
        if decision.decision_id.startswith("decision:policy-input:")
    }
    assert input_fields == {"need for in-person presence", "exception rationale"}
    comparable_decision = next(
        decision
        for decision in turn.workflow_state.pending_decisions
        if decision.decision_id == "decision:comparables:ground-transport"
    )
    assert comparable_decision.choices[0].metadata["required_total"] == 1
    assert comparable_decision.choices[1].metadata["shortfall"] == 1
    assert turn.actions[5].title == (
        "Confirm the remaining policy-input and comparable checkpoints"
    )


def test_comparable_only_gap_uses_structured_decision_ids_in_transition_and_warnings() -> (
    None
):
    context = _build_context("missing_comparables_flow.json")
    context.collected_policy_inputs["need for in-person presence"] = (
        "Lead negotiator must be physically present for renewal terms."
    )
    context.collected_policy_inputs["exception rationale"] = (
        "Ground transport shortfall is the only remaining exception candidate."
    )

    turn = build_business_planner_turn(context)

    assert turn.workflow_state.current_stage == "candidate_generation"
    assert turn.transition.blocker_ids == [
        "decision:comparables:airfare",
        "decision:comparables:ground-transport",
        "decision:comparables:lodging",
    ]
    assert turn.transition.warning_codes == [
        "missing-comparable:airfare",
        "missing-comparable:ground_transport",
        "missing-comparable:lodging",
    ]
    warning_output = next(
        output for output in turn.outputs if output.output_kind == "warning"
    )
    assert warning_output.warnings == [
        "missing-comparable:airfare",
        "missing-comparable:ground_transport",
        "missing-comparable:lodging",
    ]


def test_exception_path_without_proposal_stays_active_when_fallback_is_available() -> (
    None
):
    context = _build_context("exception_prep_flow.json")

    turn = build_business_planner_turn(
        BusinessWorkflowContext(
            trip_record=context.trip_record,
            business_profile=context.business_profile,
            objectives=context.objectives,
            generated_at=context.generated_at,
            constraint_set=context.constraint_set,
            proposal=None,
            comparable_inventory=context.comparable_inventory,
            collected_policy_inputs=context.collected_policy_inputs,
            selected_path=context.selected_path,
        )
    )

    assert turn.workflow_state.current_stage == "policy_alignment"
    assert turn.workflow_state.status == "active"
    assert turn.next_step.recommended_action_id == "action-prepare-policy-packet"


def test_exception_prep_flow_keeps_exception_nearest_path_explicit() -> None:
    turn = build_business_planner_turn(_build_context("exception_prep_flow.json"))

    assert turn.workflow_state.current_stage == "policy_alignment"
    assert turn.workflow_state.status == "active"
    assert turn.next_step.recommended_action_id == "action-prepare-policy-packet"
    assert turn.outputs[0].payload["requested_exception_type"] == "fatigue_management"
    assert turn.outputs[0].payload["required_approval_roles"] == ["finance", "manager"]
    assert turn.outputs[-1].warnings == ["exception-path-active"]
    assert "exception_nearest" in turn.workflow_state.tags


def test_business_builder_rejects_mismatched_proposal_trip() -> None:
    context = _build_context("compliant_flow.json")
    proposal_payload = deepcopy(context.proposal.to_dict()) if context.proposal else {}
    proposal_payload["trip_id"] = "trip-business-other"

    with pytest.raises(ValueError, match="proposal.trip_id"):
        BusinessWorkflowContext(
            trip_record=context.trip_record,
            business_profile=context.business_profile,
            objectives=context.objectives,
            generated_at=context.generated_at,
            constraint_set=context.constraint_set,
            proposal=TripPlanProposal.from_dict(proposal_payload),
            comparable_inventory=context.comparable_inventory,
            collected_policy_inputs=context.collected_policy_inputs,
            selected_path=context.selected_path,
        )


def test_business_builder_rejects_unknown_generated_at() -> None:
    context = _build_context("compliant_flow.json")

    with pytest.raises(ValueError, match="generated_at"):
        BusinessWorkflowContext(
            trip_record=context.trip_record,
            business_profile=context.business_profile,
            objectives=context.objectives,
            generated_at="not-a-timestamp",
            constraint_set=context.constraint_set,
            proposal=context.proposal,
            comparable_inventory=context.comparable_inventory,
            collected_policy_inputs=context.collected_policy_inputs,
            selected_path=context.selected_path,
        )
