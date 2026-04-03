import json
from pathlib import Path

import pytest

from trip_planner.business import PolicyEvaluationResult, TripPlanProposal
from trip_planner.integrations.tpp import (
    PolicyReoptimizationContext,
    ReoptimizationPlanningError,
    TPPReoptimizationService,
)
from trip_planner.state import ScenarioVersion


def _fixture_path(name: str) -> Path:
    fixtures_dir = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "integrations"
        / "tpp"
        / "reoptimization"
    )
    return fixtures_dir / name


def _load_fixture(name: str) -> dict:
    return json.loads(_fixture_path(name).read_text(encoding="utf-8"))


def _build_inputs(
    name: str,
) -> tuple[TripPlanProposal, PolicyEvaluationResult, PolicyReoptimizationContext]:
    payload = _load_fixture(name)
    proposal = TripPlanProposal.from_dict(payload["proposal"])
    evaluation_result = PolicyEvaluationResult.from_dict(payload["evaluation_result"])
    context = PolicyReoptimizationContext(
        source_version=ScenarioVersion.from_dict(payload["source_version"]),
        comparable_refs=payload["comparable_refs"],
        justification_refs=payload["justification_refs"],
    )
    return proposal, evaluation_result, context


def test_reoptimization_routes_fixable_failures_into_regeneration() -> None:
    proposal, evaluation_result, context = _build_inputs("fixable_failure.json")
    service = TPPReoptimizationService()

    plan = service.plan_reoptimization(proposal, evaluation_result, context)

    assert plan.reaction_kind == "regenerate_scenario"
    assert plan.target_label == "compliant_first"
    assert plan.candidate_categories == ["lodging"]
    assert plan.preserved_comparable_refs == ["comparable:lodging:policy-cap"]
    assert plan.preserved_justification_refs == ["justification:lodging:venue-proximity"]

    candidate = plan.build_candidate_version(
        version_id="saved-scenario:compliant-first-v2",
        saved_scenario_id="saved-scenario:compliant-first",
        created_at="2026-04-03T10:20:00Z",
    )
    assert candidate.label == "compliant_first"
    assert candidate.based_on_version_id == context.source_version.version_id
    assert "policy-reactive" in candidate.tags


def test_reoptimization_uses_preferred_alternative_guidance_to_narrow_candidates() -> None:
    proposal, evaluation_result, context = _build_inputs("preferred_alternative.json")
    service = TPPReoptimizationService()

    plan = service.plan_reoptimization(proposal, evaluation_result, context)

    assert plan.reaction_kind == "narrow_candidates"
    assert plan.comparison_outcome == "preferred"
    assert plan.candidate_categories == ["airfare", "lodging"]
    assert plan.preserved_comparable_refs == [
        "comparable:airfare:preferred-channel",
        "comparable:lodging:policy-cap",
    ]

    comparison = plan.build_comparison(
        comparison_id="comparison:policy-rerank",
        candidate_scenario_id="saved-scenario:compliant-first-rerank",
        compared_at="2026-04-03T10:25:00Z",
    )
    assert comparison.outcome == "preferred"
    assert comparison.focus_areas == [
        "airfare",
        "lodging",
        "policy_alignment",
        "comparables",
    ]


def test_reoptimization_generates_exception_candidate_with_preserved_context() -> None:
    proposal, evaluation_result, context = _build_inputs("exception_required.json")
    service = TPPReoptimizationService()

    plan = service.plan_reoptimization(proposal, evaluation_result, context)

    assert plan.reaction_kind == "create_exception_candidate"
    assert plan.target_label == "exception_nearest"
    assert plan.required_approval_roles == ["manager", "finance"]
    assert plan.preserved_justification_refs == [
        "justification:lodging:venue-proximity",
        "justification:ground:late-arrival-risk",
    ]
    assert "Prepare exception packet with venue-adjacent lodging rationale." in plan.notes

    candidate = plan.build_candidate_version(
        version_id="saved-scenario:exception-nearest-v2",
        saved_scenario_id="saved-scenario:exception-nearest",
        created_at="2026-04-03T10:30:00Z",
    )
    assert candidate.label == "exception_nearest"
    assert candidate.snapshot_refs.notes[-1] == (
        "candidate-categories:lodging,ground_transport"
    )


def test_reoptimization_rejects_mismatched_evaluation_result() -> None:
    proposal, evaluation_result, context = _build_inputs("fixable_failure.json")
    service = TPPReoptimizationService()
    payload = evaluation_result.to_dict()
    payload["proposal_id"] = "proposal-other"

    with pytest.raises(
        ReoptimizationPlanningError,
        match="evaluation_result.proposal_id must match proposal.proposal_id",
    ):
        service.plan_reoptimization(
            proposal,
            PolicyEvaluationResult.from_dict(payload),
            context,
        )
