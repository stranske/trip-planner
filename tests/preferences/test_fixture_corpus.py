import json
from pathlib import Path

from tests.preferences.fixture_corpus import (
    fixture_corpus_path,
    load_fixture_corpus,
    load_fixture_map,
)
from trip_planner.preferences.schema import TRADEOFF_DIMENSION_KEYS


def test_fixture_corpus_loads_and_instantiates_profiles() -> None:
    fixtures = load_fixture_corpus()

    assert len(fixtures) >= 10
    assert {fixture.fixture_kind for fixture in fixtures} == {
        "archetype",
        "tension_case",
    }

    for fixture in fixtures:
        assert fixture.id
        assert fixture.summary
        assert fixture.raw_inputs["trip_brief"]
        assert fixture.raw_inputs["stated_constraints"]
        assert fixture.raw_inputs["planning_style_notes"]
        assert fixture.intended_interpretation.qualitative_summary
        assert fixture.intended_interpretation.dominant_dimensions
        assert fixture.intended_interpretation.planning_implications
        assert fixture.evidence
        assert fixture.profile.to_dict()["profile_kind"] == "leisure"


def test_fixture_corpus_covers_all_first_tier_dimensions() -> None:
    fixtures = load_fixture_corpus()
    covered_dimensions: set[str] = set()

    for fixture in fixtures:
        covered_dimensions.update(fixture.intended_interpretation.dominant_dimensions)
        for record in fixture.evidence:
            covered_dimensions.update(record.affected_dimensions)

    assert covered_dimensions == set(TRADEOFF_DIMENSION_KEYS)


def test_tension_cases_surface_real_conflicts() -> None:
    fixtures = load_fixture_map()

    breadth_case = fixtures["breadth-under-recovery-pressure"]
    anchor_case = fixtures["elastic-discovery-with-fixed-anchors"]
    budget_case = fixtures["quality-floors-under-budget-pressure"]

    assert breadth_case.fixture_kind == "tension_case"
    assert breadth_case.profile.tension_flags
    assert {
        "breadth_vs_depth",
        "recovery_vs_intensity",
    }.issubset(breadth_case.intended_interpretation.dominant_dimensions)

    assert anchor_case.profile.hard_constraints.must_include_places == [
        "Istanbul",
        "Cappadocia",
    ]
    assert anchor_case.profile.anchors["calendar_anchors"]
    assert anchor_case.profile.tradeoff_dimensions["structure_vs_elasticity"].value > 0.0

    assert budget_case.profile.hard_constraints.budget_ceiling == 5200.0
    assert budget_case.profile.anchors["quality_floor_anchors"]
    assert budget_case.profile.budget_model.quality_floors["lodging"]


def test_fixture_corpus_preserves_option_evidence_for_revealed_preferences() -> None:
    fixtures = load_fixture_map()

    rail_fixture = fixtures["scenic-rail-nomad"]
    comfort_fixture = fixtures["comfort-floor-traveler"]

    rail_option = next(
        record.option_evidence
        for record in rail_fixture.evidence
        if record.evidence_type == "option_selection"
    )
    comfort_option = next(
        record.option_evidence
        for record in comfort_fixture.evidence
        if record.evidence_type == "option_selection"
    )

    assert rail_option is not None
    assert rail_option.option_kind == "mixed_bundle"
    assert comfort_option is not None
    assert comfort_option.option_kind == "transport"


def test_fixture_corpus_rejects_wrong_schema_version(tmp_path: Path) -> None:
    payload = json.loads(fixture_corpus_path().read_text(encoding="utf-8"))
    payload["schema_version"] = "9.9.9"
    path = tmp_path / "bad-schema.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    try:
        load_fixture_corpus(path)
    except ValueError as exc:
        assert "schema_version" in str(exc)
    else:
        raise AssertionError("Fixture corpus should reject unsupported schema versions")


def test_fixture_corpus_rejects_duplicate_ids(tmp_path: Path) -> None:
    payload = json.loads(fixture_corpus_path().read_text(encoding="utf-8"))
    payload["fixtures"][1]["id"] = payload["fixtures"][0]["id"]
    path = tmp_path / "duplicate-ids.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    try:
        load_fixture_corpus(path)
    except ValueError as exc:
        assert "ids must be unique" in str(exc)
    else:
        raise AssertionError("Fixture corpus should reject duplicate fixture ids")


def test_fixture_corpus_rejects_missing_qualitative_summary(tmp_path: Path) -> None:
    payload = json.loads(fixture_corpus_path().read_text(encoding="utf-8"))
    payload["fixtures"][0]["intended_interpretation"]["qualitative_summary"] = ""
    path = tmp_path / "missing-summary.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    try:
        load_fixture_corpus(path)
    except ValueError as exc:
        assert "qualitative_summary" in str(exc)
    else:
        raise AssertionError("Fixture corpus should reject missing qualitative summaries")


def test_fixture_corpus_rejects_non_object_fixture_entries(tmp_path: Path) -> None:
    payload = json.loads(fixture_corpus_path().read_text(encoding="utf-8"))
    payload["fixtures"][0] = "not-a-fixture"
    path = tmp_path / "bad-entry.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    try:
        load_fixture_corpus(path)
    except ValueError as exc:
        assert "index 0" in str(exc)
    else:
        raise AssertionError("Fixture corpus should reject non-object fixture entries")


def test_fixture_corpus_rejects_unknown_hard_constraint_keys(tmp_path: Path) -> None:
    payload = json.loads(fixture_corpus_path().read_text(encoding="utf-8"))
    payload["fixtures"][8]["profile_overrides"]["hard_constraints"]["budget_ceiling_typo"] = 1000
    path = tmp_path / "bad-hard-constraints.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    try:
        load_fixture_corpus(path)
    except ValueError as exc:
        assert "hard constraint override keys" in str(exc)
    else:
        raise AssertionError("Fixture corpus should reject unknown hard constraint override keys")
