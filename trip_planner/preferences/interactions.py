"""Interaction rules for leisure preference resolution."""

from __future__ import annotations

from dataclasses import replace

from .explanations import (
    InteractionActivation,
    MaterialInfluence,
    ResolutionExplanation,
)
from .models import InteractionRule, LeisurePreferenceProfile, TensionFlag


def _clamp_probability(value: float) -> float:
    return max(0.0, min(1.0, value))


def _clamp_axis(value: float) -> float:
    return max(-1.0, min(1.0, value))


def _upsert_tension(
    profile: LeisurePreferenceProfile,
    explanation: ResolutionExplanation,
    flag_id: str,
    severity: float,
    description: str,
    influences: list[MaterialInfluence],
) -> None:
    existing = next((flag for flag in profile.tension_flags if flag.id == flag_id), None)
    if existing is None:
        profile.tension_flags.append(
            TensionFlag(
                id=flag_id,
                severity=_clamp_probability(severity),
                description=description,
            )
        )
    else:
        existing.severity = max(existing.severity, _clamp_probability(severity))
    explanation.tension_explanations.setdefault(flag_id, []).extend(influences)


def _record_rule_on_dimensions(
    explanation: ResolutionExplanation,
    rule_id: str,
    dimension_keys: list[str],
) -> None:
    for key in dimension_keys:
        detail = explanation.dimension_explanations[key]
        if rule_id not in detail.interaction_rule_ids:
            detail.interaction_rule_ids.append(rule_id)


def _record_rule_on_hybrid(
    explanation: ResolutionExplanation,
    rule_id: str,
    hybrid_key: str,
) -> None:
    detail = explanation.hybrid_factor_explanations[hybrid_key]
    if rule_id not in detail.interaction_rule_ids:
        detail.interaction_rule_ids.append(rule_id)


def apply_interactions(
    profile: LeisurePreferenceProfile,
    explanation: ResolutionExplanation,
) -> None:
    dims = profile.tradeoff_dimensions
    hybrids = profile.hybrid_factors

    breadth = dims["breadth_vs_depth"]
    recovery = dims["recovery_vs_intensity"]
    movement = dims["movement_vs_friction"]
    scenic = dims["scenic_transit_vs_destination_time"]
    structure = dims["structure_vs_elasticity"]
    discovery = dims["iconic_vs_discovery"]
    route = dims["route_coherence_vs_eclectic_contrast"]
    social = dims["social_energy_vs_solitude"]
    self_reliance = dims["self_reliance_vs_convenience"]

    if breadth.value <= -0.45 and recovery.value <= -0.45:
        strength = _clamp_probability((abs(breadth.value) + abs(recovery.value)) / 2.0)
        movement.value = _clamp_axis(movement.value + 0.12)
        route.salience = max(route.salience, 0.72)
        rule_id = "breadth-x-recovery"
        profile.interaction_rules.append(
            InteractionRule(
                id=rule_id,
                dimensions=["breadth_vs_depth", "recovery_vs_intensity"],
                activation={
                    "breadth_vs_depth": breadth.value,
                    "recovery_vs_intensity": recovery.value,
                },
                effect={
                    "planning_biases": {
                        "cluster_bases": 0.92,
                        "protect_recovery_blocks": 0.96,
                    },
                    "movement_bias_shift": 0.12,
                },
                strength=strength,
                priority=0.95,
            )
        )
        tension_id = "breadth-recovery-conflict"
        influences = [
            MaterialInfluence(
                source_kind="interaction",
                source_id=rule_id,
                weight=strength,
                summary="Breadth desire and recovery need require clustered routing and recovery blocks.",
            )
        ]
        _upsert_tension(
            profile,
            explanation,
            tension_id,
            severity=max(0.75, strength),
            description="Breadth ambitions conflict with recovery limits unless the route is tightly clustered.",
            influences=influences,
        )
        _record_rule_on_dimensions(
            explanation,
            rule_id,
            ["breadth_vs_depth", "recovery_vs_intensity", "movement_vs_friction"],
        )
        for key in ("breadth_vs_depth", "recovery_vs_intensity"):
            if tension_id not in explanation.dimension_explanations[key].tension_flag_ids:
                explanation.dimension_explanations[key].tension_flag_ids.append(tension_id)
        explanation.activated_interactions.append(
            InteractionActivation(
                rule_id=rule_id,
                dimensions=["breadth_vs_depth", "recovery_vs_intensity"],
                planning_biases={
                    "cluster_bases": 0.92,
                    "protect_recovery_blocks": 0.96,
                },
                triggered_tension_ids=[tension_id],
                notes=[
                    "Move density should stay constrained even when breadth remains attractive."
                ],
            )
        )

    if movement.value <= -0.45 and scenic.value <= -0.45:
        strength = _clamp_probability((abs(movement.value) + abs(scenic.value)) / 2.0)
        hybrids["route_modes"].mode = "both"
        hybrids["route_modes"].salience = max(hybrids["route_modes"].salience, 0.82)
        hybrids["route_modes"].anchor_strength = max(hybrids["route_modes"].anchor_strength, 0.62)
        route.salience = max(route.salience, 0.7)
        rule_id = "movement-x-scenic-transit"
        profile.interaction_rules.append(
            InteractionRule(
                id=rule_id,
                dimensions=[
                    "movement_vs_friction",
                    "scenic_transit_vs_destination_time",
                ],
                activation={
                    "movement_vs_friction": movement.value,
                    "scenic_transit_vs_destination_time": scenic.value,
                },
                effect={
                    "planning_biases": {
                        "prefer_overland_modes": 0.93,
                        "treat_transit_as_experience": 0.95,
                    },
                    "route_mode_anchor_boost": 0.62,
                },
                strength=strength,
                priority=0.88,
            )
        )
        _record_rule_on_dimensions(
            explanation,
            rule_id,
            ["movement_vs_friction", "scenic_transit_vs_destination_time"],
        )
        _record_rule_on_hybrid(explanation, rule_id, "route_modes")
        explanation.activated_interactions.append(
            InteractionActivation(
                rule_id=rule_id,
                dimensions=[
                    "movement_vs_friction",
                    "scenic_transit_vs_destination_time",
                ],
                planning_biases={
                    "prefer_overland_modes": 0.93,
                    "treat_transit_as_experience": 0.95,
                },
                notes=["The route itself should be treated as part of the trip payoff."],
            )
        )

    if structure.value >= 0.45 and discovery.value >= 0.45:
        strength = _clamp_probability((structure.value + discovery.value) / 2.0)
        rule_id = "structure-x-discovery"
        profile.interaction_rules.append(
            InteractionRule(
                id=rule_id,
                dimensions=["structure_vs_elasticity", "iconic_vs_discovery"],
                activation={
                    "structure_vs_elasticity": structure.value,
                    "iconic_vs_discovery": discovery.value,
                },
                effect={
                    "planning_biases": {
                        "favor_wandering_zones": 0.94,
                        "keep_daily_skeleton_light": 0.82,
                    }
                },
                strength=strength,
                priority=0.83,
            )
        )
        _record_rule_on_dimensions(
            explanation,
            rule_id,
            ["structure_vs_elasticity", "iconic_vs_discovery"],
        )
        if profile.anchors["place_anchors"] or profile.anchors["calendar_anchors"]:
            tension_id = "elasticity-anchor-conflict"
            influences = [
                MaterialInfluence(
                    source_kind="interaction",
                    source_id=rule_id,
                    weight=strength,
                    summary="Open-ended discovery must coexist with fixed anchors and calendar commitments.",
                )
            ]
            _upsert_tension(
                profile,
                explanation,
                tension_id,
                severity=max(0.72, strength),
                description="Elastic discovery needs a route skeleton because anchors cannot be allowed to drift.",
                influences=influences,
            )
            for key in ("structure_vs_elasticity", "iconic_vs_discovery"):
                if tension_id not in explanation.dimension_explanations[key].tension_flag_ids:
                    explanation.dimension_explanations[key].tension_flag_ids.append(tension_id)
            tension_ids = [tension_id]
        else:
            tension_ids = []
        explanation.activated_interactions.append(
            InteractionActivation(
                rule_id=rule_id,
                dimensions=["structure_vs_elasticity", "iconic_vs_discovery"],
                planning_biases={
                    "favor_wandering_zones": 0.94,
                    "keep_daily_skeleton_light": 0.82,
                },
                triggered_tension_ids=tension_ids,
                notes=[
                    "Discovery-heavy travelers still need directional wandering targets rather than empty free time."
                ],
            )
        )

    has_quality_floor = bool(
        profile.anchors["quality_floor_anchors"] or profile.budget_model.quality_floors
    )
    has_budget_pressure = (
        profile.budget_model.total_budget_sensitivity >= 0.55
        or profile.hard_constraints.budget_ceiling is not None
    )
    if has_quality_floor and has_budget_pressure:
        strength = _clamp_probability(0.5 + (profile.budget_model.total_budget_sensitivity * 0.4))
        self_reliance.value = max(self_reliance.value, 0.45)
        self_reliance.salience = max(self_reliance.salience, 0.7)
        route.salience = max(route.salience, 0.62)
        rule_id = "budget-x-quality-floors"
        profile.interaction_rules.append(
            InteractionRule(
                id=rule_id,
                dimensions=["self_reliance_vs_convenience"],
                activation={
                    "budget_sensitivity": profile.budget_model.total_budget_sensitivity,
                    "quality_floor_anchor_count": len(profile.anchors["quality_floor_anchors"]),
                },
                effect={
                    "planning_biases": {
                        "compress_route_before_downgrading_lodging": 0.95,
                        "protect_quality_floors": 0.92,
                    }
                },
                strength=strength,
                priority=0.9,
            )
        )
        tension_id = "quality-floor-budget-conflict"
        influences = [
            MaterialInfluence(
                source_kind="interaction",
                source_id=rule_id,
                weight=strength,
                summary="Budget pressure should contract route ambition before comfort floors are silently violated.",
            )
        ]
        _upsert_tension(
            profile,
            explanation,
            tension_id,
            severity=max(0.78, strength),
            description="Budget pressure conflicts with comfort floors unless route scope or timing adjusts.",
            influences=influences,
        )
        _record_rule_on_dimensions(explanation, rule_id, ["self_reliance_vs_convenience"])
        if (
            tension_id
            not in explanation.dimension_explanations[
                "self_reliance_vs_convenience"
            ].tension_flag_ids
        ):
            explanation.dimension_explanations[
                "self_reliance_vs_convenience"
            ].tension_flag_ids.append(tension_id)
        explanation.activated_interactions.append(
            InteractionActivation(
                rule_id=rule_id,
                dimensions=["self_reliance_vs_convenience"],
                planning_biases={
                    "compress_route_before_downgrading_lodging": 0.95,
                    "protect_quality_floors": 0.92,
                },
                triggered_tension_ids=[tension_id],
                notes=[
                    "Comfort floors should be protected by scope cuts before quiet lodging is sacrificed."
                ],
            )
        )

    if social.value <= -0.45 and recovery.value <= -0.45:
        strength = _clamp_probability((abs(social.value) + abs(recovery.value)) / 2.0)
        hybrids["rest"].mode = "both"
        hybrids["rest"].salience = max(hybrids["rest"].salience, 0.84)
        hybrids["rest"].anchor_strength = max(hybrids["rest"].anchor_strength, 0.52)
        rule_id = "social-energy-x-recovery"
        profile.interaction_rules.append(
            InteractionRule(
                id=rule_id,
                dimensions=["social_energy_vs_solitude", "recovery_vs_intensity"],
                activation={
                    "social_energy_vs_solitude": social.value,
                    "recovery_vs_intensity": recovery.value,
                },
                effect={
                    "planning_biases": {
                        "alternate_social_and_recovery_days": 0.96,
                        "protect_slow_mornings": 0.9,
                    }
                },
                strength=strength,
                priority=0.9,
            )
        )
        tension_id = "social-energy-recovery-conflict"
        influences = [
            MaterialInfluence(
                source_kind="interaction",
                source_id=rule_id,
                weight=strength,
                summary="Social-energy goals require explicit recovery protection instead of optimistic pacing.",
            )
        ]
        _upsert_tension(
            profile,
            explanation,
            tension_id,
            severity=max(0.76, strength),
            description="Social-energy preferences conflict with recovery limits unless late and quiet days alternate.",
            influences=influences,
        )
        _record_rule_on_dimensions(
            explanation,
            rule_id,
            ["social_energy_vs_solitude", "recovery_vs_intensity"],
        )
        _record_rule_on_hybrid(explanation, rule_id, "rest")
        for key in ("social_energy_vs_solitude", "recovery_vs_intensity"):
            if tension_id not in explanation.dimension_explanations[key].tension_flag_ids:
                explanation.dimension_explanations[key].tension_flag_ids.append(tension_id)
        explanation.activated_interactions.append(
            InteractionActivation(
                rule_id=rule_id,
                dimensions=["social_energy_vs_solitude", "recovery_vs_intensity"],
                planning_biases={
                    "alternate_social_and_recovery_days": 0.96,
                    "protect_slow_mornings": 0.9,
                },
                triggered_tension_ids=[tension_id],
                notes=[
                    "High-social-energy days should be paired with explicit decompression time."
                ],
            )
        )

    profile.tradeoff_dimensions["movement_vs_friction"] = replace(movement)
    profile.tradeoff_dimensions["route_coherence_vs_eclectic_contrast"] = replace(route)
    profile.tradeoff_dimensions["self_reliance_vs_convenience"] = replace(self_reliance)
