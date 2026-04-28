"""Preference normalization tests for the named traveler persona archetypes.

Each test verifies that the fixture's loaded profile encodes the expected normalized
dimension signature and constraint properties for its declared persona. These tests
protect the behavioral intent documented in each fixture's intended_interpretation.
"""

from tests.preferences.fixture_corpus import load_fixture_map


def test_all_required_persona_archetypes_are_present() -> None:
    fixture_map = load_fixture_map()

    required_personas = {
        "budget-focused",
        "schedule-sensitive",
        "accessibility-aware",
        "family-leisure",
        "business-policy-constrained",
    }
    assert required_personas.issubset(
        fixture_map.keys()
    ), f"Missing persona fixtures: {required_personas - fixture_map.keys()}"
    for persona_id in required_personas:
        assert fixture_map[persona_id].fixture_kind == "archetype"


def test_budget_focused_persona_encodes_cost_discipline() -> None:
    fixture_map = load_fixture_map()
    fixture = fixture_map["budget-focused"]
    profile = fixture.profile

    # Hard budget constraint is present and meaningful
    assert profile.hard_constraints.budget_ceiling is not None
    assert profile.hard_constraints.budget_ceiling <= 3000.0

    # Budget sensitivity is high — this traveler responds strongly to cost signals
    assert profile.budget_model.total_budget_sensitivity >= 0.85

    # Splurging is off — no exceptions to cost discipline
    assert profile.budget_model.splurge_allowed is False

    # Self-reliance dimension is strongly positive (prefers cheap self-managed options)
    self_reliance = profile.tradeoff_dimensions["self_reliance_vs_convenience"]
    assert (
        self_reliance.value >= 0.6
    ), f"budget-focused should lean toward self-reliance, got {self_reliance.value}"
    assert self_reliance.salience >= 0.8

    # Dominant dimensions match documented persona intent
    assert "self_reliance_vs_convenience" in fixture.intended_interpretation.dominant_dimensions


def test_schedule_sensitive_persona_encodes_calendar_structure() -> None:
    fixture_map = load_fixture_map()
    fixture = fixture_map["schedule-sensitive"]
    profile = fixture.profile

    # Hard date window is set — fixed travel window
    assert profile.hard_constraints.date_window.start is not None
    assert profile.hard_constraints.date_window.end is not None

    # Must-protect experiences cover a fixed calendar commitment
    assert profile.hard_constraints.must_protect_experiences

    # Calendar anchors are present and non-negotiable
    assert profile.anchors["calendar_anchors"], "schedule-sensitive must have calendar anchors"
    calendar_anchor = profile.anchors["calendar_anchors"][0]
    assert calendar_anchor.strength >= 0.95

    # Structure dimension is strongly negative (highly structured, not elastic)
    structure = profile.tradeoff_dimensions["structure_vs_elasticity"]
    assert (
        structure.value <= -0.7
    ), f"schedule-sensitive should lean strongly toward structure, got {structure.value}"
    assert structure.salience >= 0.9

    # Convenience preference reflects need for reliable logistics
    convenience = profile.tradeoff_dimensions["self_reliance_vs_convenience"]
    assert (
        convenience.value <= -0.4
    ), f"schedule-sensitive should lean toward convenience/reliability, got {convenience.value}"

    # Dominant dimensions match documented persona intent
    assert "structure_vs_elasticity" in fixture.intended_interpretation.dominant_dimensions


def test_accessibility_aware_persona_declares_mobility_and_lodging_constraints() -> None:
    fixture_map = load_fixture_map()
    fixture = fixture_map["accessibility-aware"]
    profile = fixture.profile

    # Mobility constraints are declared as hard requirements
    assert (
        profile.hard_constraints.mobility_constraints
    ), "accessibility-aware must declare mobility constraints"
    mobility_text = " ".join(profile.hard_constraints.mobility_constraints).lower()
    assert "wheelchair" in mobility_text or "step-free" in mobility_text

    # Lodging constraints are declared (accessible room required)
    assert (
        profile.hard_constraints.lodging_constraints
    ), "accessibility-aware must declare lodging constraints"

    # Quality floor anchors exist for verified accessible lodging
    assert profile.anchors[
        "quality_floor_anchors"
    ], "accessibility-aware must have quality floor anchors for accessible lodging"
    quality_anchor = profile.anchors["quality_floor_anchors"][0]
    assert quality_anchor.strength >= 0.9

    # Convenience dimension is negative (needs logistical support, not pure self-reliance)
    convenience = profile.tradeoff_dimensions["self_reliance_vs_convenience"]
    assert (
        convenience.value <= -0.4
    ), f"accessibility-aware should lean toward convenience/support, got {convenience.value}"

    # Friction dimension is positive (friction has higher real cost for mobility-constrained traveler)
    friction = profile.tradeoff_dimensions["movement_vs_friction"]
    assert (
        friction.value >= 0.5
    ), f"accessibility-aware should show elevated friction sensitivity, got {friction.value}"

    # movement_vs_friction is the key dominant dimension for this persona
    # (self_reliance_vs_convenience is excluded from dominant_dims because the resolution
    # engine guardrail forces it positive when quality floor anchors exist, which conflicts
    # with the persona's actual need for logistical support)
    assert "movement_vs_friction" in fixture.intended_interpretation.dominant_dimensions
    assert "self_reliance_vs_convenience" not in fixture.intended_interpretation.dominant_dimensions


def test_family_leisure_persona_encodes_recovery_and_stable_logistics() -> None:
    fixture_map = load_fixture_map()
    fixture = fixture_map["family-leisure"]
    profile = fixture.profile

    # Traveler party is family
    assert profile.trip_frame.traveler_party == "family"

    # Recovery dimension is strongly negative (family needs recovery, not maximum intensity)
    recovery = profile.tradeoff_dimensions["recovery_vs_intensity"]
    assert (
        recovery.value <= -0.5
    ), f"family-leisure should lean toward recovery, got {recovery.value}"
    assert recovery.salience >= 0.85

    # Movement/friction dimension is positive (family logistics create friction sensitivity)
    friction = profile.tradeoff_dimensions["movement_vs_friction"]
    assert (
        friction.value >= 0.5
    ), f"family-leisure should show high friction sensitivity, got {friction.value}"

    # Structure dimension is negative (needs some structure for children's needs)
    structure = profile.tradeoff_dimensions["structure_vs_elasticity"]
    assert (
        structure.value <= -0.3
    ), f"family-leisure should lean toward structure, got {structure.value}"

    # Quality floors exist for family-suitable lodging
    lodging_floor = profile.budget_model.quality_floors.get("lodging")
    assert lodging_floor, "family-leisure must define a lodging quality floor"
    assert "family" in lodging_floor.lower()

    # Tension flag is present reflecting pacing vs breadth conflict
    assert profile.tension_flags, "family-leisure should surface a pacing tension flag"

    # Dominant dimensions match documented persona intent
    assert "recovery_vs_intensity" in fixture.intended_interpretation.dominant_dimensions
    assert "movement_vs_friction" in fixture.intended_interpretation.dominant_dimensions


def test_business_policy_constrained_persona_encodes_budget_ceiling_and_calendar_lock() -> None:
    fixture_map = load_fixture_map()
    fixture = fixture_map["business-policy-constrained"]
    profile = fixture.profile

    # Hard budget ceiling from policy is present
    assert profile.hard_constraints.budget_ceiling is not None
    assert profile.hard_constraints.budget_ceiling <= 4000.0

    # Work commitments are protected in hard constraints
    assert (
        profile.hard_constraints.must_protect_experiences
    ), "business-policy-constrained must protect work commitments"

    # Splurge is not allowed — policy compliance extends to leisure portion
    assert profile.budget_model.splurge_allowed is False

    # Budget sensitivity is high
    assert profile.budget_model.total_budget_sensitivity >= 0.8

    # Calendar anchors protect the work window
    assert profile.anchors[
        "calendar_anchors"
    ], "business-policy-constrained must have calendar anchors for work days"
    work_anchor = profile.anchors["calendar_anchors"][0]
    assert work_anchor.strength >= 0.95

    # Structure dimension is negative (work schedule imposes structure on whole trip)
    structure = profile.tradeoff_dimensions["structure_vs_elasticity"]
    assert (
        structure.value <= -0.6
    ), f"business-policy-constrained should lean strongly toward structure, got {structure.value}"

    # structure_vs_elasticity is the primary dominant dimension
    # (self_reliance_vs_convenience is excluded from dominant_dims because the resolution
    # engine guardrail forces it positive when quality floors exist, which conflicts with
    # the persona's intent of needing logistical reliability support)
    assert "structure_vs_elasticity" in fixture.intended_interpretation.dominant_dimensions
    assert "self_reliance_vs_convenience" not in fixture.intended_interpretation.dominant_dimensions


def test_persona_fixtures_each_carry_at_least_two_evidence_records() -> None:
    fixture_map = load_fixture_map()
    persona_ids = [
        "budget-focused",
        "schedule-sensitive",
        "accessibility-aware",
        "family-leisure",
        "business-policy-constrained",
    ]
    for persona_id in persona_ids:
        fixture = fixture_map[persona_id]
        assert len(fixture.evidence) >= 2, (
            f"{persona_id} must carry at least two evidence records, "
            f"found {len(fixture.evidence)}"
        )


def test_persona_fixtures_have_documented_planning_implications() -> None:
    fixture_map = load_fixture_map()
    persona_ids = [
        "budget-focused",
        "schedule-sensitive",
        "accessibility-aware",
        "family-leisure",
        "business-policy-constrained",
    ]
    for persona_id in persona_ids:
        fixture = fixture_map[persona_id]
        assert (
            fixture.intended_interpretation.planning_implications
        ), f"{persona_id} must document planning_implications"
        assert (
            fixture.intended_interpretation.expected_tensions
        ), f"{persona_id} must document expected_tensions"


def test_persona_fixtures_have_distinct_dominant_dimension_signatures() -> None:
    fixture_map = load_fixture_map()

    budget = set(fixture_map["budget-focused"].intended_interpretation.dominant_dimensions)
    schedule = set(fixture_map["schedule-sensitive"].intended_interpretation.dominant_dimensions)
    accessibility = set(
        fixture_map["accessibility-aware"].intended_interpretation.dominant_dimensions
    )
    family = set(fixture_map["family-leisure"].intended_interpretation.dominant_dimensions)

    # budget-focused and schedule-sensitive differ in at least one dominant dimension
    assert budget != schedule, "budget-focused and schedule-sensitive should have distinct profiles"

    # family-leisure is uniquely recovery-dominant — not shared by budget or schedule
    assert "recovery_vs_intensity" in family
    assert "recovery_vs_intensity" not in budget
    assert "recovery_vs_intensity" not in schedule

    # accessibility-aware focuses on movement_vs_friction; family adds recovery and structure
    assert "movement_vs_friction" in accessibility
    assert "movement_vs_friction" in family
    assert "recovery_vs_intensity" in family
    assert "recovery_vs_intensity" not in accessibility
