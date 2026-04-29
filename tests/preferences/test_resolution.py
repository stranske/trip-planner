from copy import deepcopy

from tests.preferences.fixture_corpus import load_fixture_corpus
from trip_planner.preferences import EvidenceSummary, resolve_leisure_profile
from trip_planner.preferences.evidence import PreferenceEvidence
from trip_planner.preferences.resolution import resolve_dimension_evidence

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
        result = resolve_leisure_profile(_resolution_seed(fixture.profile), fixture.evidence)

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
    fixture = next(item for item in load_fixture_corpus() if item.id == "scenic-rail-nomad")
    contradictory = deepcopy(fixture.evidence[0])
    contradictory.id = "scenic-rail-nomad-ev-contradiction"
    contradictory.signal_direction = "contradiction"
    contradictory.contradictions = []
    contradictory.note = "Traveler also says frequent transfers become exhausting after a week."

    result = resolve_leisure_profile(
        _resolution_seed(fixture.profile),
        fixture.evidence + [contradictory],
    )

    assert any(
        flag.id == "movement_vs_friction-contradiction" for flag in result.profile.tension_flags
    )
    assert "movement_vs_friction-contradiction" in (
        result.explanation.dimension_explanations["movement_vs_friction"].tension_flag_ids
    )


def test_resolution_flags_dimensions_that_need_directional_seed() -> None:
    fixture = next(item for item in load_fixture_corpus() if item.id == "discovery-wanderer")
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


def test_resolution_explanation_reports_value_delta_from_seed() -> None:
    fixture = next(item for item in load_fixture_corpus() if item.id == "scenic-rail-nomad")
    seed = _resolution_seed(fixture.profile)
    seed.tradeoff_dimensions["movement_vs_friction"].value = 0.2

    result = resolve_leisure_profile(seed, fixture.evidence)

    detail = result.explanation.dimension_explanations["movement_vs_friction"]
    assert detail.initial_value == 0.2
    assert detail.resolved_value == result.profile.tradeoff_dimensions["movement_vs_friction"].value
    assert detail.value_delta == detail.resolved_value - detail.initial_value
    assert detail.value_delta > 0.0
    assert any(influence.source_kind == "evidence" for influence in detail.influences)
    assert "Score increased from 0.20" in detail.explanation_text
    assert "delta +" in detail.explanation_text
    assert "based on" in detail.explanation_text


def test_value_delta_is_not_clamped_for_full_axis_swings() -> None:
    # ``self_reliance_vs_convenience`` is force-raised to at least 0.35 by the
    # quality-floor guardrail in ``_apply_anchor_and_constraint_precedence``.
    # Seeding it at -1.0 and letting the public resolver run produces a natural
    # delta of 1.35, which would be silently truncated to 1.0 if value_delta
    # were ever clamped to the [-1, 1] axis range again.
    fixture = next(item for item in load_fixture_corpus() if item.id == "comfort-floor-traveler")
    seed = _resolution_seed(fixture.profile)
    seed.tradeoff_dimensions["self_reliance_vs_convenience"].value = -1.0

    result = resolve_leisure_profile(seed, fixture.evidence)

    detail = result.explanation.dimension_explanations["self_reliance_vs_convenience"]
    assert detail.initial_value == -1.0
    assert detail.resolved_value >= 0.35
    assert detail.value_delta == detail.resolved_value - detail.initial_value
    assert detail.value_delta > 1.0


def test_directional_seed_artifacts_removed_after_interaction_moves_off_zero() -> None:
    fixture = next(item for item in load_fixture_corpus() if item.id == "discovery-wanderer")
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
        not in result.explanation.dimension_explanations["movement_vs_friction"].tension_flag_ids
    )
    assert (
        "movement_vs_friction-needs-directional-seed" not in result.explanation.tension_explanations
    )
    assert all(
        "movement_vs_friction received evidence but remained at a zero-direction seed value."
        != note
        for note in result.profile.evidence_summary.confidence_notes
    )


def test_dimension_resolution_is_deterministic_for_input_order() -> None:
    records = [
        PreferenceEvidence(
            id="ev-b",
            evidence_type="scenario_reaction",
            source_type="scenario_prompt",
            affected_dimensions=["movement_vs_friction"],
            signal_direction="positive",
            confidence_hint=0.7,
            salience_hint=0.7,
            sequence=3,
        ),
        PreferenceEvidence(
            id="ev-a",
            evidence_type="direct_statement",
            source_type="user_message",
            affected_dimensions=["movement_vs_friction"],
            signal_direction="negative",
            confidence_hint=0.9,
            salience_hint=0.8,
            sequence=2,
        ),
    ]
    first = resolve_dimension_evidence("movement_vs_friction", 0.4, records)
    second = resolve_dimension_evidence("movement_vs_friction", 0.4, list(reversed(records)))
    assert first.final_value == second.final_value
    assert first.confidence == second.confidence
    assert first.explanation_code == second.explanation_code
    assert first.contributing_evidence_ids == second.contributing_evidence_ids


def test_dimension_resolution_explicit_override_beats_behavioral_signal() -> None:
    records = [
        PreferenceEvidence(
            id="ev-explicit",
            evidence_type="direct_statement",
            source_type="user_message",
            affected_dimensions=["movement_vs_friction"],
            signal_direction="negative",
            confidence_hint=0.95,
            salience_hint=0.8,
            sequence=9,
        ),
        PreferenceEvidence(
            id="ev-behavior",
            evidence_type="scenario_reaction",
            source_type="scenario_prompt",
            affected_dimensions=["movement_vs_friction"],
            signal_direction="positive",
            confidence_hint=0.7,
            salience_hint=0.7,
            sequence=10,
        ),
    ]
    resolved = resolve_dimension_evidence("movement_vs_friction", 0.6, records)
    assert resolved.final_value < 0.0
    assert resolved.explanation_code == "explicit_override"
    assert "ev-explicit" in resolved.contributing_evidence_ids


def test_dimension_resolution_tie_keeps_seed_value() -> None:
    records = [
        PreferenceEvidence(
            id="ev-left",
            evidence_type="scenario_reaction",
            source_type="scenario_prompt",
            affected_dimensions=["movement_vs_friction"],
            signal_direction="negative",
            confidence_hint=0.9,
            salience_hint=0.8,
            sequence=1,
        ),
        PreferenceEvidence(
            id="ev-right",
            evidence_type="scenario_reaction",
            source_type="scenario_prompt",
            affected_dimensions=["movement_vs_friction"],
            signal_direction="positive",
            confidence_hint=0.9,
            salience_hint=0.8,
            sequence=1,
        ),
    ]
    resolved = resolve_dimension_evidence("movement_vs_friction", 0.25, records)
    assert resolved.final_value == 0.25
    assert resolved.explanation_code == "balanced_conflict"
    assert {"ev-left", "ev-right"}.issubset(set(resolved.contributing_evidence_ids))


def test_dimension_resolution_pure_behavioral_conflict_emits_balanced_code() -> None:
    records = [
        PreferenceEvidence(
            id="ev-bpos",
            evidence_type="scenario_reaction",
            source_type="scenario_prompt",
            affected_dimensions=["movement_vs_friction"],
            signal_direction="positive",
            confidence_hint=0.85,
            salience_hint=0.7,
            sequence=10,
        ),
        PreferenceEvidence(
            id="ev-bneg",
            evidence_type="scenario_reaction",
            source_type="scenario_prompt",
            affected_dimensions=["movement_vs_friction"],
            signal_direction="negative",
            confidence_hint=0.85,
            salience_hint=0.7,
            sequence=10,
        ),
    ]
    resolved = resolve_dimension_evidence("movement_vs_friction", 0.0, records)
    assert resolved.final_value == 0.0
    assert resolved.explanation_code == "balanced_conflict"
    assert {"ev-bpos", "ev-bneg"}.issubset(set(resolved.contributing_evidence_ids))


def test_dimension_resolution_contradiction_only_evidence_uses_default_seed() -> None:
    # Contradiction-direction signals carry no directional weight on their own,
    # so a record-set containing only contradictions must NOT be labelled
    # "balanced_conflict" — there is no opposing directional support to balance.
    # Confidence/salience are kept low so contradiction_support stays under
    # the 0.18 conflict_low_confidence override threshold and we exercise the
    # default_seed branch.
    records = [
        PreferenceEvidence(
            id="ev-contradicting",
            evidence_type="direct_statement",
            source_type="user_message",
            affected_dimensions=["movement_vs_friction"],
            signal_direction="contradiction",
            confidence_hint=0.0,
            salience_hint=0.0,
            sequence=5,
        ),
    ]
    resolved = resolve_dimension_evidence("movement_vs_friction", 0.25, records)
    assert resolved.final_value == 0.25
    assert resolved.explanation_code == "default_seed"


def test_dimension_resolution_stale_behavior_is_discounted() -> None:
    records = [
        PreferenceEvidence(
            id="ev-stale",
            evidence_type="scenario_reaction",
            source_type="scenario_prompt",
            affected_dimensions=["movement_vs_friction"],
            signal_direction="negative",
            confidence_hint=0.8,
            salience_hint=0.8,
            sequence=1,
        ),
        PreferenceEvidence(
            id="ev-recent",
            evidence_type="scenario_reaction",
            source_type="scenario_prompt",
            affected_dimensions=["movement_vs_friction"],
            signal_direction="positive",
            confidence_hint=0.8,
            salience_hint=0.8,
            sequence=30,
        ),
    ]
    resolved = resolve_dimension_evidence("movement_vs_friction", 0.0, records)
    assert resolved.recent_behavior_support > abs(resolved.older_behavior_support)
    assert resolved.final_value > 0.0


def test_dimension_resolution_missing_evidence_uses_default_seed() -> None:
    resolved = resolve_dimension_evidence("movement_vs_friction", -0.35, [])
    assert resolved.final_value == -0.35
    assert resolved.explanation_code == "default_seed"
    assert resolved.contributing_evidence_ids == []
