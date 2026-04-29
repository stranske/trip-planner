"""Resolution engine for leisure preference profiles."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

from . import schema
from .evidence import PreferenceEvidence
from .evidence_catalog import (
    support_for_dimension,
    support_for_hybrid_factor,
)
from .explanations import (
    DimensionResolutionExplanation,
    HybridFactorExplanation,
    MaterialInfluence,
    ResolutionExplanation,
    ResolvedLeisureProfile,
)
from .interactions import apply_interactions
from .models import LeisurePreferenceProfile, TensionFlag

SUPPORT_WEIGHTS: dict[str, float] = {
    "weak": 0.3,
    "medium": 0.6,
    "strong": 0.9,
}
ANCHOR_GROUP_DIMENSIONS: dict[str, list[str]] = {
    "place_anchors": ["route_coherence_vs_eclectic_contrast", "breadth_vs_depth"],
    "experience_anchors": ["breadth_vs_depth", "iconic_vs_discovery"],
    "mode_anchors": ["movement_vs_friction", "scenic_transit_vs_destination_time"],
    "rhythm_anchors": ["recovery_vs_intensity", "structure_vs_elasticity"],
    "calendar_anchors": [
        "structure_vs_elasticity",
        "route_coherence_vs_eclectic_contrast",
    ],
    "quality_floor_anchors": [
        "movement_vs_friction",
        "self_reliance_vs_convenience",
        "recovery_vs_intensity",
    ],
    "regional_adjacency_preferences": [
        "route_coherence_vs_eclectic_contrast",
        "scenic_transit_vs_destination_time",
    ],
}
EVIDENCE_STAGE_BOOSTS: dict[str, dict[str, float]] = {
    "direct_statement": {"initial_design": 0.15},
    "hard_constraint_declaration": {
        "initial_design": 0.18,
        "inventory_selection": 0.08,
    },
    "anchor_declaration": {"initial_design": 0.18, "daily_activity_design": 0.06},
    "forced_tradeoff_choice": {"initial_design": 0.16},
    "scenario_reaction": {"initial_design": 0.14, "inventory_selection": 0.08},
    "option_selection": {"inventory_selection": 0.18, "daily_activity_design": 0.08},
    "option_rejection": {"inventory_selection": 0.14},
    "trip_revision": {"in_trip_adjustment": 0.18, "daily_activity_design": 0.1},
}
EXPLICIT_EVIDENCE_TYPES: tuple[str, ...] = (
    "direct_statement",
    "hard_constraint_declaration",
    "anchor_declaration",
    "forced_tradeoff_choice",
)
BEHAVIORAL_EVIDENCE_TYPES: tuple[str, ...] = (
    "scenario_reaction",
    "option_selection",
    "option_rejection",
    "trip_revision",
)
STALE_SEQUENCE_WINDOW = 12


@dataclass(slots=True)
class DimensionEvidenceResolution:
    dimension_key: str
    final_value: float
    confidence: float
    contributing_evidence_ids: list[str] = field(default_factory=list)
    explanation_code: str = "default_seed"
    explanation_text: str = ""
    recent_behavior_support: float = 0.0
    older_behavior_support: float = 0.0


def _clamp_probability(value: float) -> float:
    return max(0.0, min(1.0, value))


def _clamp_axis(value: float) -> float:
    return max(-1.0, min(1.0, value))


def _sorted_evidence(
    evidence_records: list[PreferenceEvidence],
) -> list[PreferenceEvidence]:
    return sorted(
        evidence_records,
        key=lambda record: (
            record.sequence if record.sequence is not None else 10**6,
            record.observed_at or "",
            record.id,
        ),
    )


def _influence_weight(record: PreferenceEvidence, support_level: str) -> float:
    support_weight = SUPPORT_WEIGHTS[support_level]
    contradiction_penalty = (
        sum(marker.weakening_strength for marker in record.contradictions) * 0.12
    )
    return _clamp_probability(
        support_weight * (0.5 + (record.confidence_hint * 0.3) + (record.salience_hint * 0.2))
        - contradiction_penalty
    )


def _base_direction(value: float) -> float:
    if value < 0:
        return -1.0
    if value > 0:
        return 1.0
    return 0.0


def _new_dimension_explanation(
    dimension_key: str, profile: LeisurePreferenceProfile
) -> DimensionResolutionExplanation:
    dimension = profile.tradeoff_dimensions[dimension_key]
    return DimensionResolutionExplanation(
        dimension_key=dimension_key,
        initial_value=dimension.value,
        resolved_value=dimension.value,
        confidence=dimension.confidence,
        salience=dimension.salience,
        stability=dimension.stability,
    )


def _new_hybrid_explanation(
    hybrid_key: str, profile: LeisurePreferenceProfile
) -> HybridFactorExplanation:
    factor = profile.hybrid_factors[hybrid_key]
    return HybridFactorExplanation(
        hybrid_factor_key=hybrid_key,
        mode=factor.mode,
        salience=factor.salience,
        anchor_strength=factor.anchor_strength,
    )


def resolve_dimension_evidence(
    dimension_key: str,
    seed_value: float,
    evidence_records: list[PreferenceEvidence],
    *,
    stale_sequence_window: int = STALE_SEQUENCE_WINDOW,
) -> DimensionEvidenceResolution:
    applicable = [item for item in evidence_records if dimension_key in item.affected_dimensions]
    if not applicable:
        return DimensionEvidenceResolution(
            dimension_key=dimension_key,
            final_value=seed_value,
            confidence=0.0,
            explanation_code="default_seed",
            explanation_text="No evidence found; retained seed value.",
        )

    max_sequence = max(
        (item.sequence for item in applicable if item.sequence is not None),
        default=None,
    )
    explicit_support = 0.0
    recent_behavior_support = 0.0
    older_behavior_support = 0.0
    contradiction_support = 0.0
    salience_boost = 0.0
    stability_bonus = 0.0
    stage_boosts = {stage: 0.0 for stage in schema.PLANNING_STAGES}
    contributions: list[tuple[float, str]] = []

    for record in _sorted_evidence(applicable):
        support_level = support_for_dimension(dimension_key, record.evidence_type)
        if support_level is None:
            continue
        weight = _influence_weight(record, support_level)
        signed_weight = 0.0
        if record.signal_direction == "positive":
            signed_weight = weight
        elif record.signal_direction == "negative":
            signed_weight = -weight
        elif record.signal_direction == "contradiction":
            contradiction_support += weight * 0.5
        contradiction_support += sum(
            marker.weakening_strength * weight * 0.65 for marker in record.contradictions
        )

        if record.evidence_type in EXPLICIT_EVIDENCE_TYPES:
            explicit_support += signed_weight
        elif record.evidence_type in BEHAVIORAL_EVIDENCE_TYPES:
            is_stale = (
                max_sequence is not None
                and record.sequence is not None
                and (max_sequence - record.sequence) > stale_sequence_window
            )
            if is_stale:
                older_behavior_support += signed_weight * 0.6
            else:
                recent_behavior_support += signed_weight
        salience_boost += max(0.0, weight) * record.salience_hint * 0.45
        stability_bonus += max(0.0, weight) * 0.12
        for stage, boost in EVIDENCE_STAGE_BOOSTS.get(record.evidence_type, {}).items():
            stage_boosts[stage] = max(stage_boosts[stage], boost)
        contributions.append((abs(signed_weight), record.id))

    seed_direction = _base_direction(seed_value)
    precedence_score = (
        (explicit_support * 1.4)
        + (recent_behavior_support * 0.75)
        + (older_behavior_support * 0.45)
    )
    behavioral_net = recent_behavior_support + older_behavior_support
    if explicit_support != 0.0 and behavioral_net != 0.0:
        if _base_direction(explicit_support) != _base_direction(behavioral_net):
            if abs(explicit_support) >= abs(behavioral_net) * 0.6:
                precedence_score = explicit_support
    if precedence_score == 0.0:
        final_value = seed_value
        code = "default_seed"
        text = "Evidence netted to neutral; retained seed value."
    elif precedence_score > 0.0:
        direction = 1.0
        magnitude = _clamp_probability(
            abs(seed_value) + abs(explicit_support) * 0.22 + abs(recent_behavior_support) * 0.18
        )
        final_value = _clamp_axis(direction * magnitude)
        code = "explicit_override" if explicit_support > 0 else "behavioral_inference"
        text = "Evidence favored the positive pole after precedence and recency weighting."
    else:
        direction = -1.0
        magnitude = _clamp_probability(
            abs(seed_value) + abs(explicit_support) * 0.22 + abs(recent_behavior_support) * 0.18
        )
        final_value = _clamp_axis(direction * magnitude)
        code = "explicit_override" if explicit_support < 0 else "behavioral_inference"
        text = "Evidence favored the negative pole after precedence and recency weighting."

    if (
        seed_direction != 0.0
        and precedence_score != 0.0
        and _base_direction(final_value) != seed_direction
    ):
        code = "explicit_override" if explicit_support != 0 else "conflict_override"

    if contradiction_support >= 0.18:
        code = "conflict_low_confidence"
        text = "Conflicting evidence reduced confidence and triggered contradiction handling."

    ordered_ids = [
        item[1] for item in sorted(contributions, key=lambda pair: (-pair[0], pair[1]))[:5]
    ]
    return DimensionEvidenceResolution(
        dimension_key=dimension_key,
        final_value=final_value,
        confidence=_clamp_probability(
            0.25
            + min(0.55, abs(explicit_support) * 0.5 + abs(recent_behavior_support) * 0.3)
            - contradiction_support * 0.22
        ),
        contributing_evidence_ids=ordered_ids,
        explanation_code=code,
        explanation_text=text,
        recent_behavior_support=recent_behavior_support,
        older_behavior_support=older_behavior_support,
    )


def resolve_leisure_profile(
    base_profile: LeisurePreferenceProfile,
    evidence_records: list[PreferenceEvidence],
) -> ResolvedLeisureProfile:
    profile = deepcopy(base_profile)
    profile.interaction_rules = []
    profile.tension_flags = []
    profile.evidence_summary.sources = {}
    profile.evidence_summary.confidence_notes = []

    explanation = ResolutionExplanation(
        dimension_explanations={
            key: _new_dimension_explanation(key, profile) for key in schema.TRADEOFF_DIMENSION_KEYS
        },
        hybrid_factor_explanations={
            key: _new_hybrid_explanation(key, profile) for key in schema.HYBRID_FACTOR_KEYS
        },
    )
    ordered_evidence = _sorted_evidence(evidence_records)

    _apply_dimension_resolution(profile, ordered_evidence, explanation)
    _apply_hybrid_resolution(profile, ordered_evidence, explanation)
    _apply_anchor_and_constraint_precedence(profile, explanation)
    apply_interactions(profile, explanation)
    _finalize_explanations(profile, explanation)

    return ResolvedLeisureProfile(profile=profile, explanation=explanation)


def _apply_dimension_resolution(
    profile: LeisurePreferenceProfile,
    evidence_records: list[PreferenceEvidence],
    explanation: ResolutionExplanation,
) -> None:
    for dimension_key in schema.TRADEOFF_DIMENSION_KEYS:
        dimension = profile.tradeoff_dimensions[dimension_key]
        seed_value = dimension.value
        base_direction = _base_direction(dimension.value)
        base_magnitude = abs(dimension.value)
        positive_support = 0.0
        weakening_support = 0.0
        contradiction_support = 0.0
        salience_boost = 0.0
        stability_bonus = 0.0
        stage_boosts = {stage: 0.0 for stage in schema.PLANNING_STAGES}

        for record in evidence_records:
            if dimension_key not in record.affected_dimensions:
                continue
            support_level = support_for_dimension(dimension_key, record.evidence_type)
            if support_level is None:
                continue
            weight = _influence_weight(record, support_level)
            influence = MaterialInfluence(
                source_kind="evidence",
                source_id=record.id,
                weight=weight,
                summary=record.note or f"{record.evidence_type} affected {dimension_key}",
            )
            explanation.dimension_explanations[dimension_key].influences.append(influence)
            profile.evidence_summary.sources.setdefault(dimension_key, []).append(record.id)
            if record.signal_direction == "positive":
                positive_support += weight
            elif record.signal_direction == "negative":
                weakening_support += weight
            contradiction_support += sum(
                marker.weakening_strength * weight * 0.65 for marker in record.contradictions
            )
            if record.signal_direction == "contradiction":
                contradiction_support += weight * 0.5
            salience_boost += weight * record.salience_hint * 0.45
            stability_bonus += weight * 0.12
            for stage, boost in EVIDENCE_STAGE_BOOSTS.get(record.evidence_type, {}).items():
                stage_boosts[stage] = max(stage_boosts[stage], boost)

        if base_direction != 0.0:
            magnitude = _clamp_probability(
                base_magnitude + (positive_support * 0.2) - (weakening_support * 0.1)
            )
            value = _clamp_axis(base_direction * magnitude)
        else:
            value = 0.0
            if positive_support > 0.0 or weakening_support > 0.0 or contradiction_support > 0.0:
                tension_id = f"{dimension_key}-needs-directional-seed"
                flag = TensionFlag(
                    id=tension_id,
                    severity=_clamp_probability(0.45 + positive_support + contradiction_support),
                    description=(
                        f"{dimension_key} has evidence support but still needs directional seeding."
                    ),
                )
                profile.tension_flags.append(flag)
                explanation.tension_explanations[tension_id] = list(
                    explanation.dimension_explanations[dimension_key].influences
                )
                explanation.dimension_explanations[dimension_key].tension_flag_ids.append(
                    tension_id
                )
                profile.evidence_summary.confidence_notes.append(
                    f"{dimension_key} received evidence but remained at a zero-direction seed value."
                )
        dimension.value = value
        dimension.confidence = _clamp_probability(
            max(dimension.confidence, 0.25)
            + (positive_support * 0.32)
            - (contradiction_support * 0.18)
        )
        dimension.salience = _clamp_probability(
            max(dimension.salience, 0.22) + salience_boost + (positive_support * 0.12)
        )
        dimension.stability = _clamp_probability(
            max(dimension.stability, 0.2) + stability_bonus - (contradiction_support * 0.18)
        )
        for stage in schema.PLANNING_STAGES:
            dimension.trip_stage_sensitivity[stage] = _clamp_probability(
                max(dimension.trip_stage_sensitivity[stage], stage_boosts[stage])
            )
        if contradiction_support >= 0.18:
            tension_id = f"{dimension_key}-contradiction"
            flag = TensionFlag(
                id=tension_id,
                severity=_clamp_probability(0.45 + contradiction_support),
                description=(f"Contradictory evidence remains unresolved for {dimension_key}."),
            )
            profile.tension_flags.append(flag)
            explanation.tension_explanations[tension_id] = list(
                explanation.dimension_explanations[dimension_key].influences
            )
            explanation.dimension_explanations[dimension_key].tension_flag_ids.append(tension_id)
            profile.evidence_summary.confidence_notes.append(
                f"{dimension_key} includes contradictory evidence that should remain visible downstream."
            )
        provenance = resolve_dimension_evidence(dimension_key, seed_value, evidence_records)
        dim_expl = explanation.dimension_explanations[dimension_key]
        dim_expl.explanation_code = provenance.explanation_code
        dim_expl.explanation_text = provenance.explanation_text
        dim_expl.contributing_evidence_ids = provenance.contributing_evidence_ids


def _apply_hybrid_resolution(
    profile: LeisurePreferenceProfile,
    evidence_records: list[PreferenceEvidence],
    explanation: ResolutionExplanation,
) -> None:
    for hybrid_key in schema.HYBRID_FACTOR_KEYS:
        factor = profile.hybrid_factors[hybrid_key]
        salience_boost = 0.0
        anchor_boost = 0.0
        for record in evidence_records:
            if hybrid_key not in record.affected_hybrid_factors:
                continue
            support_level = support_for_hybrid_factor(hybrid_key, record.evidence_type)
            if support_level is None:
                continue
            weight = _influence_weight(record, support_level)
            explanation.hybrid_factor_explanations[hybrid_key].influences.append(
                MaterialInfluence(
                    source_kind="evidence",
                    source_id=record.id,
                    weight=weight,
                    summary=record.note or f"{record.evidence_type} affected {hybrid_key}",
                )
            )
            profile.evidence_summary.sources.setdefault(hybrid_key, []).append(record.id)
            if record.signal_direction == "positive":
                salience_boost += weight * 0.42
                if factor.mode in {"anchor", "both"}:
                    anchor_boost += weight * 0.32
            else:
                salience_boost -= weight * 0.12
        factor.salience = _clamp_probability(max(factor.salience, 0.18) + salience_boost)
        factor.anchor_strength = _clamp_probability(max(factor.anchor_strength, 0.0) + anchor_boost)


def _apply_anchor_and_constraint_precedence(
    profile: LeisurePreferenceProfile,
    explanation: ResolutionExplanation,
) -> None:
    for anchor_group, anchors in profile.anchors.items():
        if not anchors:
            continue
        average_strength = sum(anchor.strength for anchor in anchors) / len(anchors)
        flexibility_discount = sum(anchor.flexibility for anchor in anchors) / len(anchors)
        effective_weight = _clamp_probability(
            average_strength * (1.0 - (flexibility_discount * 0.35))
        )
        for dimension_key in ANCHOR_GROUP_DIMENSIONS.get(anchor_group, []):
            dimension = profile.tradeoff_dimensions[dimension_key]
            dimension.salience = _clamp_probability(
                max(dimension.salience, 0.3) + (effective_weight * 0.22)
            )
            dimension.confidence = _clamp_probability(
                max(dimension.confidence, 0.28) + (effective_weight * 0.12)
            )
            explanation.dimension_explanations[dimension_key].influences.append(
                MaterialInfluence(
                    source_kind="anchor_group",
                    source_id=anchor_group,
                    weight=effective_weight,
                    summary=f"{anchor_group} raises the salience of {dimension_key}.",
                )
            )
            if anchor_group not in profile.evidence_summary.sources:
                profile.evidence_summary.sources[anchor_group] = [
                    anchor.label for anchor in anchors
                ]

    if profile.hard_constraints.budget_ceiling is not None:
        profile.evidence_summary.confidence_notes.append(
            "Budget ceiling is treated as a hard constraint that later planning layers must protect."
        )
    if profile.anchors["quality_floor_anchors"] or profile.budget_model.quality_floors:
        dimension = profile.tradeoff_dimensions["self_reliance_vs_convenience"]
        dimension.value = max(dimension.value, 0.35)
        dimension.salience = max(dimension.salience, 0.66)
        dimension.confidence = max(dimension.confidence, 0.62)
        explanation.dimension_explanations["self_reliance_vs_convenience"].influences.append(
            MaterialInfluence(
                source_kind="quality_floor_guardrail",
                source_id="quality_floor_protection",
                weight=0.72,
                summary="Quality floors protect smoother arrivals and more reliable lodging choices.",
            )
        )


def _finalize_explanations(
    profile: LeisurePreferenceProfile,
    explanation: ResolutionExplanation,
) -> None:
    # Interactions run before this stage and may move values away from zero.
    # Drop stale "needs-directional-seed" artifacts when the final resolved value
    # is no longer zero, so tensions/notes reflect the final profile state.
    filtered_tension_flags: list[TensionFlag] = []
    confidence_notes = list(profile.evidence_summary.confidence_notes)
    for key, dimension in profile.tradeoff_dimensions.items():
        detail = explanation.dimension_explanations[key]
        directional_seed_tension_id = f"{key}-needs-directional-seed"
        directional_seed_note = (
            f"{key} received evidence but remained at a zero-direction seed value."
        )
        if dimension.value != 0.0:
            if directional_seed_tension_id in detail.tension_flag_ids:
                detail.tension_flag_ids = [
                    tension_id
                    for tension_id in detail.tension_flag_ids
                    if tension_id != directional_seed_tension_id
                ]
            explanation.tension_explanations.pop(directional_seed_tension_id, None)
            confidence_notes = [note for note in confidence_notes if note != directional_seed_note]
        detail.resolved_value = dimension.value
        # Both ``initial_value`` and ``dimension.value`` are clamped to [-1, 1], so the
        # delta naturally lies in [-2, 2]. Clamping it to [-1, 1] would silently lose
        # information for full-axis swings (e.g. -1 -> +1).
        detail.value_delta = dimension.value - detail.initial_value
        detail.confidence = dimension.confidence
        detail.salience = dimension.salience
        detail.stability = dimension.stability
        if not detail.influences:
            detail.notes.append(
                "No direct evidence was attached; value came from the seed profile."
            )
        if detail.interaction_rule_ids:
            detail.notes.append(
                "Interaction rules materially affected this dimension during resolution."
            )
    for tension in profile.tension_flags:
        if tension.id.endswith("-needs-directional-seed"):
            key = tension.id[: -len("-needs-directional-seed")]
        else:
            key = ""
        if tension.id.endswith("-needs-directional-seed") and key in profile.tradeoff_dimensions:
            if profile.tradeoff_dimensions[key].value != 0.0:
                continue
        filtered_tension_flags.append(tension)
    profile.tension_flags = filtered_tension_flags
    profile.evidence_summary.confidence_notes = confidence_notes
    for key, factor in profile.hybrid_factors.items():
        hybrid_detail = explanation.hybrid_factor_explanations[key]
        hybrid_detail.mode = factor.mode
        hybrid_detail.salience = factor.salience
        hybrid_detail.anchor_strength = factor.anchor_strength
        if not hybrid_detail.influences:
            hybrid_detail.notes.append(
                "No direct evidence was attached; hybrid factor stayed close to the seed profile."
            )
