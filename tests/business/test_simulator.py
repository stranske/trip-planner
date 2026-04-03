import json
from pathlib import Path

from trip_planner.business import (
    BusinessTravelProfile,
    PolicyEvaluationSimulator,
    TripPlanProposal,
)

_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "business"


def _fixture_path(name: str) -> Path:
    return _FIXTURES_DIR / name


def _load_fixture(name: str) -> dict:
    return json.loads(_fixture_path(name).read_text(encoding="utf-8"))


def test_simulator_loads_case_catalog() -> None:
    simulator = PolicyEvaluationSimulator.from_json_file(
        _fixture_path("policy_simulator_cases.json")
    )

    assert simulator.case_ids() == ["clean-approval", "exception-approval"]


def test_simulator_evaluates_clean_case_with_runtime_proposal_id() -> None:
    simulator = PolicyEvaluationSimulator.from_json_file(
        _fixture_path("policy_simulator_cases.json")
    )
    payload = _load_fixture("approval_ready_clean.json")
    proposal = TripPlanProposal.from_dict(payload["proposal"])

    evaluation = simulator.evaluate(proposal, case_id="clean-approval")

    assert evaluation.proposal_id == proposal.proposal_id
    assert evaluation.status == "compliant"
    assert evaluation.approval_requirements[0].role == "manager"


def test_simulator_round_trip_builds_exception_ready_package() -> None:
    simulator = PolicyEvaluationSimulator.from_json_file(
        _fixture_path("policy_simulator_cases.json")
    )
    payload = _load_fixture("approval_ready_exception.json")
    profile = BusinessTravelProfile.from_dict(payload["profile"])
    proposal = TripPlanProposal.from_dict(payload["proposal"])

    run = simulator.simulate_round_trip(
        case_id="exception-approval",
        profile=profile,
        proposal=proposal,
    )

    assert run.case_id == "exception-approval"
    assert run.evaluation_result.status == "exception_required"
    assert run.approval_package.package_status == "exception_ready"
    assert run.approval_package.readiness_checks[-1].key == "exception_packet"


def test_simulator_rejects_case_shape_mismatch() -> None:
    simulator = PolicyEvaluationSimulator.from_json_file(
        _fixture_path("policy_simulator_cases.json")
    )
    payload = _load_fixture("approval_ready_clean.json")
    proposal_payload = dict(payload["proposal"])
    proposal_payload["selected_options"] = proposal_payload["selected_options"][:1]
    proposal = TripPlanProposal.from_dict(proposal_payload)

    try:
        simulator.evaluate(proposal, case_id="clean-approval")
    except ValueError as exc:
        assert "selected option categories" in str(exc)
    else:
        raise AssertionError("shape mismatch should fail simulator evaluation")


def test_simulator_rejects_unknown_case_id() -> None:
    simulator = PolicyEvaluationSimulator.from_json_file(
        _fixture_path("policy_simulator_cases.json")
    )
    payload = _load_fixture("approval_ready_clean.json")
    proposal = TripPlanProposal.from_dict(payload["proposal"])

    try:
        simulator.evaluate(proposal, case_id="missing-case")
    except ValueError as exc:
        assert "Unknown case_id" in str(exc)
        assert "clean-approval" in str(exc)
    else:
        raise AssertionError("unknown case ids should fail with a clear error")
