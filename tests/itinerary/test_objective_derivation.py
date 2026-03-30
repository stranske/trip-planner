from copy import deepcopy

from trip_planner.itinerary import derive_itinerary_objectives
from trip_planner.preferences import resolve_leisure_profile
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
    assert payload["route_shape"] in {"hub_and_spoke", "linear", "regional_cluster", "mixed"}
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
                "spending_priorities": {"food": 0.9, "lodging_location": 0.75, "museums": 0.25},
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
    assert objectives.budget_protection.protected_categories[:2] == ["food", "lodging_location"]


def test_interaction_biases_change_objective_bundle() -> None:
    fixture = load_fixture_map()["breadth-under-recovery-pressure"]
    resolved = resolve_leisure_profile(fixture.profile, fixture.evidence)

    without_interactions = deepcopy(resolved)
    without_interactions.explanation.activated_interactions = []

    with_biases = derive_itinerary_objectives(resolved, trip_id="trip-bias")
    without_biases = derive_itinerary_objectives(without_interactions, trip_id="trip-bias")

    assert with_biases.target_base_count.min_value >= without_biases.target_base_count.min_value
    assert with_biases.move_density.max_moves < without_biases.move_density.max_moves
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

    assert objectives.target_base_count.min_value >= 2
    assert any("Hard budget ceiling=4200" in note for note in objectives.budget_protection.notes)
    assert any(
        line.startswith("hard_constraints:must_include_places=") for line in objectives.explanations
    )
