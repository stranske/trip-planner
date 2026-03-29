from tests.preferences.fixture_corpus import load_fixture_corpus
from trip_planner.preferences import EvidenceSummary, resolve_leisure_profile


def _resolution_seed(fixture_profile):
    seed = fixture_profile.__class__.from_dict(fixture_profile.to_dict())
    for dimension in seed.tradeoff_dimensions.values():
        dimension.confidence = 0.2
        dimension.salience = 0.2
        dimension.stability = 0.2
    seed.interaction_rules = []
    seed.tension_flags = []
    seed.evidence_summary = EvidenceSummary()
    return seed


def test_resolution_clears_directional_seed_artifacts_after_interactions() -> None:
    fixture = next(item for item in load_fixture_corpus() if item.id == "scenic-rail-nomad")
    seed = _resolution_seed(fixture.profile)
    seed.tradeoff_dimensions["movement_vs_friction"].value = 0.0
    seed.tradeoff_dimensions["breadth_vs_depth"].value = -0.6
    seed.tradeoff_dimensions["recovery_vs_intensity"].value = -0.6

    result = resolve_leisure_profile(seed, fixture.evidence)
    tension_id = "movement_vs_friction-needs-directional-seed"
    confidence_note = (
        "movement_vs_friction received evidence but remained at a zero-direction seed value."
    )

    assert result.profile.tradeoff_dimensions["movement_vs_friction"].value > 0.0
    assert tension_id not in {flag.id for flag in result.profile.tension_flags}
    assert tension_id not in result.explanation.tension_explanations
    assert tension_id not in (
        result.explanation.dimension_explanations["movement_vs_friction"].tension_flag_ids
    )
    assert confidence_note not in result.profile.evidence_summary.confidence_notes
