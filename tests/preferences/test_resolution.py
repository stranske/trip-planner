from copy import deepcopy

from tests.preferences.fixture_corpus import load_fixture_corpus
from trip_planner.preferences import EvidenceSummary, resolve_leisure_profile

EXPECTED_TENSION_IDS = {
    "social-recovery-balancer": {"social-energy-recovery-conflict"},
    "breadth-under-recovery-pressure": {"breadth-recovery-conflict"},
    "elastic-discovery-with-fixed-anchors": {"elasticity-anchor-conflict"},
    "quality-floors-under-budget-pressure": {"quality-floor-budget-conflict"},
}


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


def _same_direction(left: float, right: float) -> bool:
    if left == 0.0 or right == 0.0:
        return left == right
    return (left < 0 and right < 0) or (left > 0 and right > 0)


def test_resolution_matches_fixture_directional_outcomes() -> None:
    for fixture in load_fixture_corpus():
        result = resolve_leisure_profile(
            _resolution_seed(fixture.profile), fixture.evidence
        )

        for dimension_key in fixture.intended_interpretation.dominant_dimensions:
            expected = fixture.profile.tradeoff_dimensions[dimension_key]
            actual = result.profile.tradeoff_dimensions[dimension_key]
            assert _same_direction(actual.value, expected.value)
            assert actual.confidence > 0.2
            assert actual.salience > 0.2
            assert result.explanation.dimension_explanations[dimension_key].influences

        if fixture.id in EXPECTED_TENSION_IDS:
            actual_ids = {flag.id for flag in result.profile.tension_flags}
            assert EXPECTED_TENSION_IDS[fixture.id].issubset(actual_ids)


def test_resolution_emits_contradiction_tension_when_evidence_conflicts() -> None:
    fixture = next(
        item for item in load_fixture_corpus() if item.id == "scenic-rail-nomad"
    )
    contradictory = deepcopy(fixture.evidence[0])
    contradictory.id = "scenic-rail-nomad-ev-contradiction"
    contradictory.signal_direction = "contradiction"
    contradictory.contradictions = []
    contradictory.note = (
        "Traveler also says frequent transfers become exhausting after a week."
    )

    result = resolve_leisure_profile(
        _resolution_seed(fixture.profile),
        fixture.evidence + [contradictory],
    )

    assert any(
        flag.id == "movement_vs_friction-contradiction"
        for flag in result.profile.tension_flags
    )
    assert "movement_vs_friction-contradiction" in (
        result.explanation.dimension_explanations[
            "movement_vs_friction"
        ].tension_flag_ids
    )


def test_resolution_flags_dimensions_that_need_directional_seed() -> None:
    fixture = next(
        item for item in load_fixture_corpus() if item.id == "discovery-wanderer"
    )
    seed = _resolution_seed(fixture.profile)
    seed.tradeoff_dimensions["iconic_vs_discovery"].value = 0.0

    result = resolve_leisure_profile(seed, fixture.evidence)

    assert any(
        flag.id == "iconic_vs_discovery-needs-directional-seed"
        for flag in result.profile.tension_flags
    )
    assert any(
        "zero-direction seed value" in note
        for note in result.profile.evidence_summary.confidence_notes
    )


def test_directional_seed_artifacts_removed_after_interaction_moves_off_zero() -> None:
    fixture = next(
        item for item in load_fixture_corpus() if item.id == "discovery-wanderer"
    )
    seed = _resolution_seed(fixture.profile)
    seed.tradeoff_dimensions["movement_vs_friction"].value = 0.0
    seed.tradeoff_dimensions["breadth_vs_depth"].value = -0.6
    seed.tradeoff_dimensions["recovery_vs_intensity"].value = -0.6

    result = resolve_leisure_profile(seed, fixture.evidence)

    assert result.profile.tradeoff_dimensions["movement_vs_friction"].value != 0.0
    assert all(
        flag.id != "movement_vs_friction-needs-directional-seed"
        for flag in result.profile.tension_flags
    )
    assert (
        "movement_vs_friction-needs-directional-seed"
        not in result.explanation.dimension_explanations[
            "movement_vs_friction"
        ].tension_flag_ids
    )
    assert (
        "movement_vs_friction-needs-directional-seed"
        not in result.explanation.tension_explanations
    )
    assert all(
        "movement_vs_friction received evidence but remained at a zero-direction seed value."
        != note
        for note in result.profile.evidence_summary.confidence_notes
    )
