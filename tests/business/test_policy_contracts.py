import json
from pathlib import Path

from trip_planner.business import (
    JustificationRecord,
    PolicyConstraintSet,
    PolicyEvaluationResult,
    TripPlanProposal,
)


def _scenario_path(name: str) -> Path:
    return Path("tests/fixtures/business") / name


def _load_scenario(name: str) -> dict:
    return json.loads(_scenario_path(name).read_text(encoding="utf-8"))


def test_policy_round_trip_compliant_case() -> None:
    scenario = _load_scenario("policy_round_trip_compliant.json")

    constraint_set = PolicyConstraintSet(**scenario["constraint_set"])
    proposal = TripPlanProposal.from_dict(scenario["proposal"])
    evaluation = PolicyEvaluationResult.from_dict(scenario["evaluation_result"])

    assert constraint_set.policy_id == proposal.constraint_set_id
    assert evaluation.status == "compliant"
    assert proposal.booking_channel_summaries[0].approved is True
    assert proposal.to_dict()["selected_options"][0]["vendor"] == "United"


def test_policy_round_trip_non_compliant_case() -> None:
    scenario = _load_scenario("policy_round_trip_non_compliant.json")

    proposal = TripPlanProposal.from_dict(scenario["proposal"])
    evaluation = PolicyEvaluationResult.from_dict(scenario["evaluation_result"])

    assert proposal.booking_channel_summaries[0].approved is False
    assert evaluation.status == "non_compliant"
    assert len(evaluation.failure_reasons) == 2
    assert evaluation.preferred_alternatives[0].category == "lodging"


def test_policy_round_trip_exception_case() -> None:
    scenario = _load_scenario("policy_round_trip_exception.json")

    proposal = TripPlanProposal.from_dict(scenario["proposal"])
    evaluation = PolicyEvaluationResult.from_dict(scenario["evaluation_result"])

    assert proposal.requested_exception is not None
    assert proposal.requested_exception.exception_type == "fatigue_management"
    assert evaluation.status == "exception_required"
    assert "approval packet" in evaluation.exception_guidance[0]


def test_policy_constraint_set_rejects_missing_policy_id() -> None:
    try:
        PolicyConstraintSet(policy_id="", organization_id="org", policy_version="2026.1")
    except ValueError as exc:
        assert "policy_id" in str(exc)
    else:
        raise AssertionError("PolicyConstraintSet should reject missing policy ids")


def test_trip_plan_proposal_rejects_non_business_mode() -> None:
    scenario = _load_scenario("policy_round_trip_compliant.json")
    scenario["proposal"]["mode"] = "leisure"

    try:
        TripPlanProposal.from_dict(scenario["proposal"])
    except ValueError as exc:
        assert "mode" in str(exc)
    else:
        raise AssertionError("TripPlanProposal should reject non-business modes")


def test_trip_plan_proposal_requires_selected_options_list() -> None:
    scenario = _load_scenario("policy_round_trip_compliant.json")
    del scenario["proposal"]["selected_options"]

    try:
        TripPlanProposal.from_dict(scenario["proposal"])
    except KeyError as exc:
        assert exc.args == ("selected_options",)
    else:
        raise AssertionError("TripPlanProposal should require selected_options")


def test_trip_plan_proposal_rejects_empty_selected_options() -> None:
    scenario = _load_scenario("policy_round_trip_compliant.json")
    scenario["proposal"]["selected_options"] = []

    try:
        TripPlanProposal.from_dict(scenario["proposal"])
    except ValueError as exc:
        assert "selected_options" in str(exc)
    else:
        raise AssertionError("TripPlanProposal should reject empty selected_options")


def test_trip_plan_proposal_rejects_non_list_approval_notes() -> None:
    scenario = _load_scenario("policy_round_trip_compliant.json")
    scenario["proposal"]["approval_notes"] = "manager approval pending"

    try:
        TripPlanProposal.from_dict(scenario["proposal"])
    except ValueError as exc:
        assert "approval_notes" in str(exc)
    else:
        raise AssertionError("TripPlanProposal should reject non-list approval_notes")


def test_policy_evaluation_result_rejects_invalid_status() -> None:
    try:
        PolicyEvaluationResult(
            evaluation_id="eval-x",
            proposal_id="proposal-x",
            status="maybe",
        )
    except ValueError as exc:
        assert "status" in str(exc)
    else:
        raise AssertionError("PolicyEvaluationResult should reject unsupported statuses")


def test_policy_evaluation_result_rejects_non_list_exception_guidance() -> None:
    scenario = _load_scenario("policy_round_trip_exception.json")
    scenario["evaluation_result"]["exception_guidance"] = "submit fatigue rationale"

    try:
        PolicyEvaluationResult.from_dict(scenario["evaluation_result"])
    except ValueError as exc:
        assert "exception_guidance" in str(exc)
    else:
        raise AssertionError("PolicyEvaluationResult should reject non-list exception_guidance")


def test_policy_evaluation_result_rejects_non_list_notes() -> None:
    scenario = _load_scenario("policy_round_trip_non_compliant.json")
    scenario["evaluation_result"]["notes"] = {"summary": "use preferred booking channel"}

    try:
        PolicyEvaluationResult.from_dict(scenario["evaluation_result"])
    except ValueError as exc:
        assert "notes" in str(exc)
    else:
        raise AssertionError("PolicyEvaluationResult should reject non-list notes")


def test_business_package_exports_justification_record() -> None:
    record = JustificationRecord(
        category="lodging",
        summary="Preferred a walkable hotel to reduce fatigue before meetings.",
        evidence=["10-minute walk to client office"],
    )

    assert record.category == "lodging"
