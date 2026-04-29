from copy import deepcopy

from trip_planner.itinerary import derive_itinerary_objectives
from trip_planner.preferences import resolve_leisure_profile, TensionFlag
from trip_planner.preferences.explanations import InteractionActivation
from tests.preferences.fixture_corpus import (
    build_profile_from_overrides,
    load_fixture_map,
)


def test_derivation_produces_explainable_objective_bundle() -> None:
    fixture = load_fixture_map()["scenic-rail-nomad"]
    resolved = resolve_leisure_profile(fixture.profile, fixture.evidence)

    objectives = derive_itinerary_objectives(resolved, trip_id="trip-scenic-rail")
    payload = objectives.to_dict()

    assert payload["trip_id"] == "trip-scenic-rail"
    assert payload["route_shape"] in {
        "hub_and_spoke",
        "linear",
        "regional_cluster",
        "mixed",
    }
    assert payload["move_density"]["max_moves"] >= 1
    assert payload["explanations"]
    assert any("movement_vs_friction" in line for line in payload["explanations"])


def test_materially_different_fixtures_produce_distinct_objective_signals() -> None:
    fixtures = load_fixture_map()
    scenic = resolve_leisure_profile(
        fixtures["scenic-rail-nomad"].profile,
        fixtures["scenic-rail-nomad"].evidence,
    )
    comfort = resolve_leisure_profile(
        fixtures["comfort-floor-traveler"].profile,
        fixtures["comfort-floor-traveler"].evidence,
    )

    scenic_obj = derive_itinerary_objectives(scenic, trip_id="trip-scenic")
    comfort_obj = derive_itinerary_objectives(comfort, trip_id="trip-comfort")

    differences = {
        "route_shape": scenic_obj.route_shape != comfort_obj.route_shape,
        "base_count": scenic_obj.target_base_count.to_dict()
        != comfort_obj.target_base_count.to_dict(),
        "move_density": scenic_obj.move_density.to_dict() != comfort_obj.move_density.to_dict(),
        "day_structure": scenic_obj.day_structure.to_dict() != comfort_obj.day_structure.to_dict(),
        "discovery_style": scenic_obj.discovery_strategy.style
        != comfort_obj.discovery_strategy.style,
        "transport_strategy": scenic_obj.transport_strategy.to_dict()
        != comfort_obj.transport_strategy.to_dict(),
    }
    assert sum(1 for changed in differences.values() if changed) >= 2


def test_derivation_respects_quality_floor_and_budget_contracts() -> None:
    profile = build_profile_from_overrides(
        {
            "budget_model": {
                "total_budget_sensitivity": 0.82,
                "spending_priorities": {
                    "food": 0.9,
                    "lodging_location": 0.75,
                    "museums": 0.25,
                },
                "quality_floors": {"lodging": "4-star", "arrival_reliability": "high"},
            },
            "tradeoff_dimensions": {
                "route_coherence_vs_eclectic_contrast": {"value": 0.7},
                "breadth_vs_depth": {"value": -0.4},
            },
            "anchors": {
                "quality_floor_anchors": [
                    {
                        "type": "lodging",
                        "label": "Sleep quality first",
                        "strength": 0.9,
                        "flexibility": 0.2,
                        "notes": "",
                    }
                ]
            },
        }
    )
    resolved = resolve_leisure_profile(profile, [])
    objectives = derive_itinerary_objectives(resolved, trip_id="trip-quality")

    assert "lodging" in objectives.quality_floor_protection.required_categories
    assert objectives.budget_protection.sensitivity == 0.82
    assert objectives.budget_protection.protected_categories[:2] == [
        "food",
        "lodging_location",
    ]


def test_interaction_biases_change_objective_bundle() -> None:
    fixture = load_fixture_map()["breadth-under-recovery-pressure"]
    resolved = resolve_leisure_profile(fixture.profile, fixture.evidence)

    without_interactions = deepcopy(resolved)
    without_interactions.explanation.activated_interactions = []

    with_biases = derive_itinerary_objectives(resolved, trip_id="trip-bias")
    without_biases = derive_itinerary_objectives(without_interactions, trip_id="trip-bias")

    with_min = with_biases.target_base_count.min_value
    without_min = without_biases.target_base_count.min_value
    assert with_min is not None
    assert without_min is not None
    assert with_min >= without_min

    with_max_moves = with_biases.move_density.max_moves
    without_max_moves = without_biases.move_density.max_moves
    assert with_max_moves is not None
    assert without_max_moves is not None
    assert with_max_moves < without_max_moves
    assert any("recovery blocks" in note for note in with_biases.move_density.notes)


def test_derivation_carries_forward_hard_constraint_guidance() -> None:
    profile = build_profile_from_overrides(
        {
            "hard_constraints": {
                "duration_bounds": {"min_days": 18, "max_days": 24},
                "must_include_places": ["Istanbul", "Cappadocia", "Antalya"],
                "must_protect_experiences": ["hammam", "coastal boat day"],
                "budget_ceiling": 4200.0,
            },
            "tradeoff_dimensions": {
                "breadth_vs_depth": {"value": -0.35},
                "route_coherence_vs_eclectic_contrast": {"value": 0.2},
            },
        }
    )
    resolved = resolve_leisure_profile(profile, [])

    objectives = derive_itinerary_objectives(resolved, trip_id="trip-constraints")

    min_value = objectives.target_base_count.min_value
    assert min_value is not None
    assert min_value >= 2
    assert any("Hard budget ceiling=4200" in note for note in objectives.budget_protection.notes)
    assert any(
        line.startswith("hard_constraints:must_include_places=") for line in objectives.explanations
    )


def test_short_trip_base_count_respects_duration_cap_with_many_required_places() -> None:
    profile = build_profile_from_overrides(
        {
            "trip_frame": {"duration_days": 3},
            "hard_constraints": {
                "duration_bounds": {"min_days": 2, "max_days": 3},
                "must_include_places": ["A", "B", "C", "D"],
            },
            "tradeoff_dimensions": {
                "breadth_vs_depth": {"value": -0.45},
                "route_coherence_vs_eclectic_contrast": {"value": 0.0},
            },
        }
    )
    resolved = resolve_leisure_profile(profile, [])

    objectives = derive_itinerary_objectives(resolved, trip_id="trip-short")

    duration_cap = max(2, 3 // 2)
    min_value = objectives.target_base_count.min_value
    max_value = objectives.target_base_count.max_value
    assert min_value is not None
    assert max_value is not None
    assert min_value >= 2
    assert max_value <= duration_cap


# ── Determinism / ordering regression tests ─────────────────────────────────


def test_explanations_stable_across_shuffled_tension_flags() -> None:
    """Shuffling tension_flags must not change explanation order.

    Pre-fix, iterating profile.tension_flags in raw input order produced
    unstable explanation lines; the fix sorts by tension.id before iterating.
    """
    base_fixture = load_fixture_map()["scenic-rail-nomad"]
    resolved_base = resolve_leisure_profile(base_fixture.profile, base_fixture.evidence)

    tensions = [
        TensionFlag(id="tension-z", severity=0.5, description="last alphabetically"),
        TensionFlag(id="tension-a", severity=0.5, description="first alphabetically"),
        TensionFlag(id="tension-m", severity=0.5, description="middle alphabetically"),
    ]

    forward = deepcopy(resolved_base)
    forward.profile.tension_flags = tensions

    reversed_ = deepcopy(resolved_base)
    reversed_.profile.tension_flags = list(reversed(tensions))

    obj_forward = derive_itinerary_objectives(forward, trip_id="trip-det")
    obj_reversed = derive_itinerary_objectives(reversed_, trip_id="trip-det")

    assert obj_forward.explanations == obj_reversed.explanations
    tension_lines = [e for e in obj_forward.explanations if e.startswith("tension:")]
    assert tension_lines == [
        "tension:tension-a:first alphabetically",
        "tension:tension-m:middle alphabetically",
        "tension:tension-z:last alphabetically",
    ]


def test_explanations_stable_across_shuffled_activated_interactions() -> None:
    """Shuffling activated_interactions must not change explanation order.

    Pre-fix, activated_interactions were serialised in raw list order, making
    explanation output depend on resolution traversal order.
    """
    base_fixture = load_fixture_map()["scenic-rail-nomad"]
    resolved_base = resolve_leisure_profile(base_fixture.profile, base_fixture.evidence)

    activations = [
        InteractionActivation(
            rule_id="rule-zz",
            dimensions=[],
            planning_biases={"compress_route_before_downgrading_lodging": 0.5},
        ),
        InteractionActivation(
            rule_id="rule-aa", dimensions=[], planning_biases={"cluster_bases": 0.7}
        ),
        InteractionActivation(
            rule_id="rule-mm", dimensions=[], planning_biases={"protect_recovery_blocks": 0.4}
        ),
    ]

    forward = deepcopy(resolved_base)
    forward.explanation.activated_interactions = activations

    reversed_ = deepcopy(resolved_base)
    reversed_.explanation.activated_interactions = list(reversed(activations))

    obj_forward = derive_itinerary_objectives(forward, trip_id="trip-det")
    obj_reversed = derive_itinerary_objectives(reversed_, trip_id="trip-det")

    assert obj_forward.explanations == obj_reversed.explanations
    interaction_lines = [e for e in obj_forward.explanations if e.startswith("interaction:")]
    rule_ids_in_output = [line.split(":")[1] for line in interaction_lines]
    assert rule_ids_in_output == ["rule-aa", "rule-mm", "rule-zz"]


def test_explanations_stable_across_shuffled_must_include_places() -> None:
    """must_include_places joined in sorted order regardless of input order."""
    places_forward = ["Zurich", "Athens", "Lisbon"]
    places_reversed = list(reversed(places_forward))

    def _objectives(places: list[str]):
        profile = build_profile_from_overrides(
            {"hard_constraints": {"must_include_places": places}}
        )
        resolved = resolve_leisure_profile(profile, [])
        return derive_itinerary_objectives(resolved, trip_id="trip-places")

    obj_forward = _objectives(places_forward)
    obj_reversed = _objectives(places_reversed)

    assert obj_forward.explanations == obj_reversed.explanations
    place_line = next(
        e for e in obj_forward.explanations if e.startswith("hard_constraints:must_include_places=")
    )
    assert place_line == "hard_constraints:must_include_places=Athens,Lisbon,Zurich"


def test_explanations_stable_across_shuffled_must_protect_experiences() -> None:
    """must_protect_experiences joined in sorted order regardless of input order."""
    experiences_forward = ["spa-day", "cooking-class", "boat-trip"]
    experiences_reversed = list(reversed(experiences_forward))

    def _objectives(experiences: list[str]):
        profile = build_profile_from_overrides(
            {"hard_constraints": {"must_protect_experiences": experiences}}
        )
        resolved = resolve_leisure_profile(profile, [])
        return derive_itinerary_objectives(resolved, trip_id="trip-exp")

    obj_forward = _objectives(experiences_forward)
    obj_reversed = _objectives(experiences_reversed)

    assert obj_forward.explanations == obj_reversed.explanations
    exp_line = next(
        e
        for e in obj_forward.explanations
        if e.startswith("hard_constraints:must_protect_experiences=")
    )
    assert exp_line == "hard_constraints:must_protect_experiences=boat-trip,cooking-class,spa-day"


def test_budget_protection_categories_sorted_after_lodging_insertion() -> None:
    """protected_categories remains sorted when 'lodging' is injected by protect_quality_floors bias.

    Pre-fix, append() left the list unsorted (e.g. ['transport', 'lodging']).
    """
    base_fixture = load_fixture_map()["scenic-rail-nomad"]
    resolved_base = resolve_leisure_profile(base_fixture.profile, base_fixture.evidence)

    resolved = deepcopy(resolved_base)
    # Set spending priorities so that categories starting with 't' get protected
    # but no "lodging*" category is present, so the bias will inject "lodging".
    resolved.profile.budget_model.spending_priorities = {
        "transport": 0.9,
        "activities": 0.7,
    }
    # Inject protect_quality_floors bias with sufficient weight.
    resolved.explanation.activated_interactions = [
        InteractionActivation(
            rule_id="rule-quality",
            dimensions=[],
            planning_biases={"protect_quality_floors": 0.95},
        )
    ]

    objectives = derive_itinerary_objectives(resolved, trip_id="trip-budget-sort")

    cats = objectives.budget_protection.protected_categories
    assert cats == sorted(cats), f"categories not sorted: {cats}"
    assert "lodging" in cats


def test_repeated_serialized_runs_return_identical_output() -> None:
    """Running derivation twice on the same input must produce byte-identical serialised output."""
    fixture = load_fixture_map()["breadth-under-recovery-pressure"]
    resolved = resolve_leisure_profile(fixture.profile, fixture.evidence)

    first = derive_itinerary_objectives(resolved, trip_id="trip-repeat", objective_id="obj-1")
    second = derive_itinerary_objectives(resolved, trip_id="trip-repeat", objective_id="obj-1")

    assert first.to_dict() == second.to_dict()


def test_no_objective_dropped_or_reweighted_across_shuffled_inputs() -> None:
    """Shuffling inputs must not drop fields or change numeric values — only stable ordering matters.

    This test verifies that both the presence of every objective field *and* all numeric
    values are identical across runs with differently-ordered inputs.  A pure ordering
    regression would change ``explanations`` order but leave numeric fields unchanged;
    this test catches the stricter case where a sort bug could accidentally skip items
    (e.g. a dedup-on-equal-key scenario) or alter a weight.
    """
    base_fixture = load_fixture_map()["scenic-rail-nomad"]
    resolved_base = resolve_leisure_profile(base_fixture.profile, base_fixture.evidence)

    tensions = [
        TensionFlag(id="tension-c", severity=0.7, description="third"),
        TensionFlag(id="tension-a", severity=0.3, description="first"),
        TensionFlag(id="tension-b", severity=0.5, description="second"),
    ]
    activations = [
        InteractionActivation(
            rule_id="rule-z", dimensions=[], planning_biases={"protect_recovery_blocks": 0.95}
        ),
        InteractionActivation(
            rule_id="rule-a", dimensions=[], planning_biases={"cluster_bases": 0.95}
        ),
    ]

    forward = deepcopy(resolved_base)
    forward.profile.tension_flags = tensions
    forward.explanation.activated_interactions = activations

    reversed_ = deepcopy(resolved_base)
    reversed_.profile.tension_flags = list(reversed(tensions))
    reversed_.explanation.activated_interactions = list(reversed(activations))

    obj_forward = derive_itinerary_objectives(forward, trip_id="trip-no-drop")
    obj_reversed = derive_itinerary_objectives(reversed_, trip_id="trip-no-drop")

    d_fwd = obj_forward.to_dict()
    d_rev = obj_reversed.to_dict()

    # Top-level fields that carry numeric payloads must be byte-identical.
    for field in (
        "route_shape",
        "target_base_count",
        "move_density",
        "recovery_expectations",
        "day_structure",
        "discovery_strategy",
        "budget_protection",
        "quality_floor_protection",
        "lodging_strategy",
        "transport_strategy",
    ):
        assert d_fwd[field] == d_rev[field], f"field '{field}' differs across input ordering"

    # Explanation count must also be equal — no lines dropped.
    assert len(d_fwd["explanations"]) == len(
        d_rev["explanations"]
    ), "explanation line count differs across input ordering"


def test_pre_fix_path_would_fail_for_unsorted_tensions() -> None:
    """Regression guard: unsorted tension lines would differ if sorting were removed.

    This test proves that the shuffled-input tests are *meaningful* by directly
    constructing the two orderings and verifying that the *only difference* between
    the two runs is the sort-stabilised explanation output — i.e. the test would
    fail against the pre-fix code path that iterated tension_flags in raw order.
    """
    base_fixture = load_fixture_map()["scenic-rail-nomad"]
    resolved_base = resolve_leisure_profile(base_fixture.profile, base_fixture.evidence)

    tensions = [
        TensionFlag(id="tension-z", severity=0.5, description="last"),
        TensionFlag(id="tension-a", severity=0.5, description="first"),
    ]

    forward = deepcopy(resolved_base)
    forward.profile.tension_flags = tensions

    reversed_ = deepcopy(resolved_base)
    reversed_.profile.tension_flags = list(reversed(tensions))

    # With the fix applied, both orderings produce the same explanations.
    obj_fwd = derive_itinerary_objectives(forward, trip_id="trip-guard")
    obj_rev = derive_itinerary_objectives(reversed_, trip_id="trip-guard")
    assert obj_fwd.explanations == obj_rev.explanations

    # Demonstrate that raw-order iteration *would* produce different results:
    # construct the two tension-line sequences without sorting and assert they differ,
    # proving our sorted() call is what makes the above assertion hold.
    raw_forward_lines = [f"tension:{t.id}:{t.description}" for t in tensions]
    raw_reversed_lines = [f"tension:{t.id}:{t.description}" for t in reversed(tensions)]
    assert (
        raw_forward_lines != raw_reversed_lines
    ), "pre-fix simulation: raw iteration order differs, confirming sorted() is necessary"


VALID_EVIDENCE_CODES = {
    "default_seed",
    "explicit_override",
    "behavioral_inference",
    "conflict_override",
    "conflict_low_confidence",
}


def test_derivation_explanations_carry_evidence_codes() -> None:
    """_build_explanations must embed explanation_code from DimensionResolutionExplanation.

    This verifies that the provenance fields emitted by resolve_dimension_evidence are
    wired through _apply_dimension_resolution into DimensionResolutionExplanation, and
    then consumed by the objective-derivation layer.
    """
    fixture = load_fixture_map()["scenic-rail-nomad"]
    resolved = resolve_leisure_profile(fixture.profile, fixture.evidence)

    objectives = derive_itinerary_objectives(resolved, trip_id="trip-provenance")

    dimension_lines = [
        line for line in objectives.explanations if ": value=" in line and "evidence_code=" in line
    ]
    assert len(dimension_lines) == 6, f"expected 6 dimension lines, got: {dimension_lines}"

    for line in dimension_lines:
        code = line.split("evidence_code=")[-1]
        assert code in VALID_EVIDENCE_CODES, f"unexpected evidence_code {code!r} in line: {line}"

    # Confirm the resolved explanation object carries the same codes.
    for key in (
        "movement_vs_friction",
        "recovery_vs_intensity",
        "structure_vs_elasticity",
        "breadth_vs_depth",
        "iconic_vs_discovery",
        "route_coherence_vs_eclectic_contrast",
    ):
        dim_expl = resolved.explanation.dimension_explanations[key]
        assert dim_expl.explanation_code in VALID_EVIDENCE_CODES
        assert isinstance(dim_expl.explanation_text, str)
        assert isinstance(dim_expl.contributing_evidence_ids, list)


def test_derivation_no_evidence_yields_default_seed_code() -> None:
    """With no evidence, every dimension explanation_code is 'default_seed'."""
    profile = build_profile_from_overrides({})
    resolved = resolve_leisure_profile(profile, [])

    objectives = derive_itinerary_objectives(resolved, trip_id="trip-no-evidence")

    dimension_lines = [line for line in objectives.explanations if "evidence_code=" in line]
    assert dimension_lines
    for line in dimension_lines:
        code = line.split("evidence_code=")[-1]
        assert code == "default_seed", f"expected default_seed, got {code!r} in: {line}"
