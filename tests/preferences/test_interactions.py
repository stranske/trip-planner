from copy import deepcopy

from tests.preferences.fixture_corpus import load_fixture_corpus
from trip_planner.preferences import EvidenceSummary, resolve_leisure_profile


def _resolution_seed(fixture_profile):
    seed = deepcopy(fixture_profile)
    for dimension in seed.tradeoff_dimensions.values():
        dimension.confidence = 0.2
        dimension.salience = 0.2
        dimension.stability = 0.2
    seed.interaction_rules = []
    seed.tension_flags = []
    seed.evidence_summary = EvidenceSummary()
    return seed


def _resolved_fixture(fixture_id: str):
    fixture = next(item for item in load_fixture_corpus() if item.id == fixture_id)
    return resolve_leisure_profile(_resolution_seed(fixture.profile), fixture.evidence)


def test_movement_and_scenic_transit_interaction_activates() -> None:
    result = _resolved_fixture("scenic-rail-nomad")

    assert any(
        rule.id == "movement-x-scenic-transit"
        for rule in result.profile.interaction_rules
    )
    assert any(
        activation.rule_id == "movement-x-scenic-transit"
        for activation in result.explanation.activated_interactions
    )
    assert result.profile.hybrid_factors["route_modes"].anchor_strength >= 0.62


def test_breadth_and_recovery_interaction_produces_tension() -> None:
    result = _resolved_fixture("breadth-under-recovery-pressure")

    assert any(
        rule.id == "breadth-x-recovery" for rule in result.profile.interaction_rules
    )
    assert any(
        flag.id == "breadth-recovery-conflict" for flag in result.profile.tension_flags
    )


def test_structure_and_discovery_interaction_respects_fixed_anchors() -> None:
    result = _resolved_fixture("elastic-discovery-with-fixed-anchors")

    assert any(
        rule.id == "structure-x-discovery" for rule in result.profile.interaction_rules
    )
    assert any(
        flag.id == "elasticity-anchor-conflict" for flag in result.profile.tension_flags
    )


def test_budget_and_quality_floor_interaction_produces_guardrail_bias() -> None:
    result = _resolved_fixture("quality-floors-under-budget-pressure")

    assert any(
        rule.id == "budget-x-quality-floors"
        for rule in result.profile.interaction_rules
    )
    assert any(
        flag.id == "quality-floor-budget-conflict"
        for flag in result.profile.tension_flags
    )
    assert (
        result.profile.tradeoff_dimensions["self_reliance_vs_convenience"].value >= 0.45
    )


def test_social_and_recovery_interaction_boosts_rest_hybrid_factor() -> None:
    result = _resolved_fixture("social-recovery-balancer")

    assert any(
        rule.id == "social-energy-x-recovery"
        for rule in result.profile.interaction_rules
    )
    assert any(
        flag.id == "social-energy-recovery-conflict"
        for flag in result.profile.tension_flags
    )
    assert result.profile.hybrid_factors["rest"].salience >= 0.84
