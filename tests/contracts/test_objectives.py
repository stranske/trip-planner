from trip_planner.contracts import (
    BudgetProtection,
    CountRange,
    DayStructureObjectives,
    DiscoveryStrategy,
    ItineraryObjectives,
    LodgingStrategy,
    MoveDensityTarget,
    QualityFloorProtection,
    RecoveryExpectations,
    TransportStrategy,
)


def test_itinerary_objectives_serialize_for_leisure_trip() -> None:
    objectives = ItineraryObjectives(
        objective_id="obj-1",
        trip_id="trip-leisure-1",
        route_shape="regional_cluster",
        target_base_count=CountRange(min_value=2, max_value=4),
        move_density=MoveDensityTarget(
            max_moves=3,
            cadence_days=5,
            notes=["Prefer clustered moves over frequent backtracking."],
        ),
        recovery_expectations=RecoveryExpectations(
            buffer_days=2,
            recovery_priority=0.82,
            notes=["Protect a recovery block after dense city stretches."],
        ),
        day_structure=DayStructureObjectives(
            structure_level="elastic",
            wandering_support_level=0.88,
            reservation_density=0.24,
        ),
        discovery_strategy=DiscoveryStrategy(
            style="discovery_forward",
            protect_open_blocks=True,
            notes=["Use strong wandering zones instead of overbooking."],
        ),
        budget_protection=BudgetProtection(
            protected_categories=["food", "lodging_location"],
            sensitivity=0.68,
        ),
        quality_floor_protection=QualityFloorProtection(
            required_categories=["lodging", "arrival_reliability"],
        ),
        lodging_strategy=LodgingStrategy(
            base_style="few_bases",
            arrival_buffer_priority=0.74,
        ),
        transport_strategy=TransportStrategy(
            preferred_modes=["rail"],
            avoid_modes=["short_haul_flight"],
            transit_is_feature=True,
        ),
        explanations=["Preference engine resolved toward elastic discovery with route coherence."],
    )

    payload = objectives.to_dict()

    assert payload["route_shape"] == "regional_cluster"
    assert payload["day_structure"]["structure_level"] == "elastic"
    assert payload["transport_strategy"]["transit_is_feature"] is True


def test_itinerary_objectives_reject_invalid_route_shape() -> None:
    try:
        ItineraryObjectives(objective_id="obj-2", trip_id="trip-leisure-2", route_shape="starfish")
    except ValueError as exc:
        assert "route_shape" in str(exc)
    else:
        raise AssertionError("ItineraryObjectives should reject unsupported route shapes")


def test_count_range_rejects_inverted_bounds() -> None:
    try:
        CountRange(min_value=5, max_value=2)
    except ValueError as exc:
        assert "min_value" in str(exc)
    else:
        raise AssertionError("CountRange should reject inverted bounds")
