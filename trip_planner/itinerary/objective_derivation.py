"""Deterministic itinerary-objective derivation from resolved leisure profiles."""

from __future__ import annotations

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
from trip_planner.preferences.explanations import ResolvedLeisureProfile


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def _dimension(resolved: ResolvedLeisureProfile, key: str) -> float:
    return resolved.profile.tradeoff_dimensions[key].value


def _duration_days(resolved: ResolvedLeisureProfile) -> int:
    trip_days = resolved.profile.trip_frame.duration_days
    if trip_days:
        return trip_days
    bounds_max = resolved.profile.hard_constraints.duration_bounds.max_days
    if bounds_max:
        return bounds_max
    return 14


def _interaction_biases(resolved: ResolvedLeisureProfile) -> dict[str, float]:
    bias_values: dict[str, float] = {}
    for activation in resolved.explanation.activated_interactions:
        for bias, weight in activation.planning_biases.items():
            bias_values[bias] = max(bias_values.get(bias, 0.0), weight)
    return bias_values


def _route_shape(
    coherence: float,
    breadth_vs_depth: float,
    movement: float,
    interaction_biases: dict[str, float],
) -> str:
    if interaction_biases.get("compress_route_before_downgrading_lodging", 0.0) >= 0.9:
        return "hub_and_spoke"
    if interaction_biases.get("cluster_bases", 0.0) >= 0.9:
        return "regional_cluster"
    if coherence >= 0.45:
        return "hub_and_spoke"
    if coherence <= -0.45 and movement >= 0.2:
        return "linear"
    if breadth_vs_depth <= -0.2:
        return "regional_cluster"
    return "mixed"


def _target_base_count(
    duration_days: int,
    breadth_vs_depth: float,
    must_include_places: int,
    interaction_biases: dict[str, float],
) -> CountRange:
    if breadth_vs_depth >= 0.45:
        min_value, max_value = 1, 2
    elif breadth_vs_depth >= 0.1:
        min_value, max_value = 1, 3
    elif breadth_vs_depth <= -0.45:
        min_value, max_value = 3, 6
    else:
        min_value, max_value = 2, 4

    trip_factor = max(1, duration_days // 10)
    max_value = min(max_value + max(0, trip_factor - 2), max(2, duration_days // 2))
    if must_include_places >= 3:
        min_value = max(min_value, 2)
        max_value = max(max_value, min(must_include_places, max(3, duration_days // 3)))
    if interaction_biases.get("cluster_bases", 0.0) >= 0.9:
        min_value = max(min_value, 2)
    if interaction_biases.get("compress_route_before_downgrading_lodging", 0.0) >= 0.9:
        max_value = max(min_value, min(max_value, 3))
    duration_cap = max(2, duration_days // 2)
    if min_value > duration_cap:
        min_value = duration_cap
    if max_value > duration_cap:
        max_value = max(min_value, duration_cap)
    return CountRange(min_value=min_value, max_value=max_value)


def _move_density(
    duration_days: int,
    movement: float,
    recovery_vs_intensity: float,
    interaction_biases: dict[str, float],
) -> MoveDensityTarget:
    baseline_moves = max(1, round(duration_days / 7))
    move_adjustment = round(movement * 2.0) - round(max(0.0, recovery_vs_intensity) * 1.0)
    if interaction_biases.get("protect_recovery_blocks", 0.0) >= 0.9:
        move_adjustment -= 1
    if interaction_biases.get("alternate_social_and_recovery_days", 0.0) >= 0.9:
        move_adjustment -= 1
    max_moves = max(1, baseline_moves + move_adjustment)
    cadence_days = max(2, round(duration_days / max_moves))
    notes = [
        f"Derived from movement_vs_friction={movement:.2f}.",
        f"Recovery adjustment uses recovery_vs_intensity={recovery_vs_intensity:.2f}.",
    ]
    if interaction_biases.get("protect_recovery_blocks", 0.0) >= 0.9:
        notes.append("Interaction bias keeps recovery blocks intact by lowering move density.")
    if interaction_biases.get("alternate_social_and_recovery_days", 0.0) >= 0.9:
        notes.append("Interaction bias reserves slower pacing between social peaks.")
    return MoveDensityTarget(max_moves=max_moves, cadence_days=cadence_days, notes=notes)


def _recovery_expectations(
    recovery_vs_intensity: float, tension_count: int
) -> RecoveryExpectations:
    buffer_days = 1 + round(max(0.0, recovery_vs_intensity) * 2.0)
    recovery_priority = _clamp((recovery_vs_intensity + 1.0) / 2.0, 0.0, 1.0)
    notes = [f"Derived from recovery_vs_intensity={recovery_vs_intensity:.2f}."]
    if tension_count:
        notes.append(f"Includes {tension_count} unresolved preference tensions.")
    return RecoveryExpectations(
        buffer_days=buffer_days,
        recovery_priority=recovery_priority,
        notes=notes,
    )


def _day_structure(
    structure_vs_elasticity: float,
    interaction_biases: dict[str, float],
) -> DayStructureObjectives:
    if structure_vs_elasticity >= 0.33:
        structure_level = "high"
    elif structure_vs_elasticity <= -0.33:
        structure_level = "elastic"
    else:
        structure_level = "moderate"
    wandering_support_level = _clamp((1.0 - structure_vs_elasticity) / 2.0, 0.0, 1.0)
    reservation_density = _clamp((structure_vs_elasticity + 1.0) / 2.0, 0.0, 1.0)
    if interaction_biases.get("favor_wandering_zones", 0.0) >= 0.9:
        structure_level = "elastic" if structure_level != "high" else "moderate"
        wandering_support_level = _clamp(wandering_support_level + 0.2, 0.0, 1.0)
    if interaction_biases.get("keep_daily_skeleton_light", 0.0) >= 0.8:
        reservation_density = _clamp(reservation_density - 0.2, 0.0, 1.0)
    return DayStructureObjectives(
        structure_level=structure_level,
        wandering_support_level=wandering_support_level,
        reservation_density=reservation_density,
    )


def _discovery_strategy(
    iconic_vs_discovery: float,
    structure_vs_elasticity: float,
    interaction_biases: dict[str, float],
) -> DiscoveryStrategy:
    if iconic_vs_discovery >= 0.3:
        style = "iconic"
    elif iconic_vs_discovery <= -0.3:
        style = "discovery_forward"
    else:
        style = "balanced"
    protect_open_blocks = style == "discovery_forward" or structure_vs_elasticity < 0.0
    notes = [f"Derived from iconic_vs_discovery={iconic_vs_discovery:.2f}."]
    if interaction_biases.get("favor_wandering_zones", 0.0) >= 0.9 and style == "balanced":
        style = "discovery_forward"
    if interaction_biases.get("keep_daily_skeleton_light", 0.0) >= 0.8:
        protect_open_blocks = True
        notes.append("Interaction bias keeps the daily skeleton intentionally light.")
    return DiscoveryStrategy(style=style, protect_open_blocks=protect_open_blocks, notes=notes)


def _budget_protection(
    resolved: ResolvedLeisureProfile,
    interaction_biases: dict[str, float],
) -> BudgetProtection:
    priorities = resolved.profile.budget_model.spending_priorities
    # Canonical sort: alphabetical by category key so output is independent of dict iteration order.
    protected_categories = sorted(key for key, value in priorities.items() if value >= 0.45)
    if not protected_categories:
        # Tie-break: descending value, then ascending key so equal-priority categories resolve
        # deterministically regardless of the dict's insertion order.
        protected_categories = [
            key
            for key, _ in sorted(
                priorities.items(),
                key=lambda item: (-item[1], item[0]),
            )[:2]
        ]
    sensitivity = _clamp(resolved.profile.budget_model.total_budget_sensitivity, 0.0, 1.0)
    notes = [f"Derived from budget sensitivity={sensitivity:.2f}."]
    if resolved.profile.hard_constraints.budget_ceiling is not None:
        notes.append(
            f"Hard budget ceiling={resolved.profile.hard_constraints.budget_ceiling:.0f} is preserved."
        )
    if interaction_biases.get("protect_quality_floors", 0.0) >= 0.9:
        if not any(category.startswith("lodging") for category in protected_categories):
            protected_categories.append("lodging")
            protected_categories.sort()
        notes.append("Interaction bias protects quality floors before relaxing comfort targets.")
    return BudgetProtection(
        protected_categories=protected_categories,
        sensitivity=sensitivity,
        notes=notes,
    )


def _quality_floor(resolved: ResolvedLeisureProfile) -> QualityFloorProtection:
    categories: set[str] = set()
    categories.update(
        key for key, value in resolved.profile.budget_model.quality_floors.items() if value
    )
    if resolved.profile.anchors.get("quality_floor_anchors"):
        categories.update(("lodging", "sleep_recovery"))
    if not categories:
        categories.add("transport_reliability")
    # Canonical sort: alphabetical so set iteration order does not affect output.
    return QualityFloorProtection(required_categories=sorted(categories))


def _lodging_strategy(
    coherence: float,
    breadth_vs_depth: float,
    recovery_vs_intensity: float,
    interaction_biases: dict[str, float],
) -> LodgingStrategy:
    if coherence >= 0.45:
        base_style = "single_base"
    elif breadth_vs_depth <= -0.35:
        base_style = "multi_base"
    elif breadth_vs_depth <= -0.1:
        base_style = "few_bases"
    else:
        base_style = "mixed"
    arrival_buffer_priority = _clamp((recovery_vs_intensity + 1.0) / 2.0, 0.0, 1.0)
    notes = [
        f"Derived from route_coherence_vs_eclectic_contrast={coherence:.2f}.",
        f"Derived from breadth_vs_depth={breadth_vs_depth:.2f}.",
    ]
    if interaction_biases.get("compress_route_before_downgrading_lodging", 0.0) >= 0.9:
        base_style = "few_bases" if base_style == "multi_base" else base_style
        arrival_buffer_priority = _clamp(arrival_buffer_priority + 0.15, 0.0, 1.0)
        notes.append("Interaction bias contracts route scope before lowering lodging standards.")
    return LodgingStrategy(
        base_style=base_style,
        arrival_buffer_priority=arrival_buffer_priority,
        notes=notes,
    )


def _transport_strategy(
    scenic_transit: float,
    self_reliance_vs_convenience: float,
    interaction_biases: dict[str, float],
) -> TransportStrategy:
    preferred_modes: list[str] = []
    avoid_modes: list[str] = []
    if scenic_transit >= 0.25:
        preferred_modes.extend(["rail", "ferry"])
    elif scenic_transit <= -0.25:
        preferred_modes.append("direct_flight")
        avoid_modes.append("scenic_detour")
    if interaction_biases.get("prefer_overland_modes", 0.0) >= 0.9:
        preferred_modes.extend(["rail", "ferry"])
        avoid_modes.append("direct_flight")
    if self_reliance_vs_convenience <= -0.3:
        preferred_modes.append("door_to_door_transfer")
    if self_reliance_vs_convenience >= 0.3:
        avoid_modes.append("chauffeur_transfer")
    # Canonical sort: alphabetical so list-build order does not affect output.
    preferred_modes = sorted(set(preferred_modes))
    avoid_modes = sorted(set(avoid_modes))
    notes = [
        f"Derived from scenic_transit_vs_destination_time={scenic_transit:.2f}.",
        f"Derived from self_reliance_vs_convenience={self_reliance_vs_convenience:.2f}.",
    ]
    return TransportStrategy(
        preferred_modes=preferred_modes,
        avoid_modes=avoid_modes,
        transit_is_feature=(
            scenic_transit > 0.15
            or interaction_biases.get("treat_transit_as_experience", 0.0) >= 0.9
        ),
        notes=notes,
    )


def _build_explanations(resolved: ResolvedLeisureProfile) -> list[str]:
    """Build a deterministic explanation list.

    Sorting rules (canonical tie-breaking):
    - Tradeoff dimensions: fixed iteration order defined by the tuple below.
    - tension_flags: ascending ``tension.id`` (alphabetical string sort).
    - activated_interactions: ascending ``activation.rule_id`` (alphabetical string sort).
    - Bias items within each interaction: ascending key (``sorted(items())``).
    - must_include_places / must_protect_experiences: alphabetical join.
    """
    explanations: list[str] = []
    for key in (
        "movement_vs_friction",
        "recovery_vs_intensity",
        "structure_vs_elasticity",
        "breadth_vs_depth",
        "iconic_vs_discovery",
        "route_coherence_vs_eclectic_contrast",
    ):
        dimension = resolved.profile.tradeoff_dimensions[key]
        evidence_code = resolved.explanation.dimension_explanations[key].explanation_code
        explanations.append(
            (
                f"{key}: value={dimension.value:.2f}, confidence={dimension.confidence:.2f}, "
                f"salience={dimension.salience:.2f}, evidence_code={evidence_code}"
            )
        )
    for tension in sorted(resolved.profile.tension_flags, key=lambda t: t.id):
        explanations.append(f"tension:{tension.id}:{tension.description}")
    for activation in sorted(resolved.explanation.activated_interactions, key=lambda a: a.rule_id):
        explanations.append(
            f"interaction:{activation.rule_id}:biases={sorted(activation.planning_biases.items())}"
        )
    if resolved.profile.hard_constraints.must_include_places:
        explanations.append(
            "hard_constraints:must_include_places="
            + ",".join(sorted(resolved.profile.hard_constraints.must_include_places))
        )
    if resolved.profile.hard_constraints.must_protect_experiences:
        explanations.append(
            "hard_constraints:must_protect_experiences="
            + ",".join(sorted(resolved.profile.hard_constraints.must_protect_experiences))
        )
    return explanations


def derive_itinerary_objectives(
    resolved: ResolvedLeisureProfile,
    trip_id: str,
    objective_id: str | None = None,
) -> ItineraryObjectives:
    """Derive deterministic itinerary objectives from a resolved leisure profile."""
    movement = _dimension(resolved, "movement_vs_friction")
    recovery_vs_intensity = _dimension(resolved, "recovery_vs_intensity")
    structure_vs_elasticity = _dimension(resolved, "structure_vs_elasticity")
    breadth_vs_depth = _dimension(resolved, "breadth_vs_depth")
    self_reliance_vs_convenience = _dimension(resolved, "self_reliance_vs_convenience")
    scenic_transit = _dimension(resolved, "scenic_transit_vs_destination_time")
    coherence = _dimension(resolved, "route_coherence_vs_eclectic_contrast")
    iconic_vs_discovery = _dimension(resolved, "iconic_vs_discovery")

    duration_days = _duration_days(resolved)
    derived_objective_id = objective_id or f"{trip_id}-objectives-v1"
    interaction_biases = _interaction_biases(resolved)

    return ItineraryObjectives(
        objective_id=derived_objective_id,
        trip_id=trip_id,
        route_shape=_route_shape(coherence, breadth_vs_depth, movement, interaction_biases),
        target_base_count=_target_base_count(
            duration_days,
            breadth_vs_depth,
            must_include_places=len(resolved.profile.hard_constraints.must_include_places),
            interaction_biases=interaction_biases,
        ),
        move_density=_move_density(
            duration_days,
            movement,
            recovery_vs_intensity,
            interaction_biases,
        ),
        recovery_expectations=_recovery_expectations(
            recovery_vs_intensity,
            tension_count=len(resolved.profile.tension_flags),
        ),
        day_structure=_day_structure(structure_vs_elasticity, interaction_biases),
        discovery_strategy=_discovery_strategy(
            iconic_vs_discovery,
            structure_vs_elasticity,
            interaction_biases,
        ),
        budget_protection=_budget_protection(resolved, interaction_biases),
        quality_floor_protection=_quality_floor(resolved),
        lodging_strategy=_lodging_strategy(
            coherence,
            breadth_vs_depth,
            recovery_vs_intensity,
            interaction_biases,
        ),
        transport_strategy=_transport_strategy(
            scenic_transit,
            self_reliance_vs_convenience,
            interaction_biases,
        ),
        explanations=_build_explanations(resolved),
    )
