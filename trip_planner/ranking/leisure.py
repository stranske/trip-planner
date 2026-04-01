"""Deterministic leisure candidate ranking built on resolved profiles and bundles."""

from __future__ import annotations

from collections.abc import Iterable
from statistics import mean

from trip_planner.candidates import CandidateSeed, CandidateSet
from trip_planner.contracts import ComparisonAxis, ItineraryObjectives
from trip_planner.itinerary import derive_itinerary_objectives, evaluate_bundle_feasibility
from trip_planner.itinerary.feasibility import FeasibilityAssessment
from trip_planner.options import InventoryBundle
from trip_planner.preferences.explanations import ResolvedLeisureProfile

from .explanations import ExplanationRecord
from .models import (
    RankedResult,
    RankedResultSet,
    RiskFlag,
    ScoreAdjustment,
    ScoreBreakdown,
    ScoreConfidenceSummary,
    ScoreContribution,
)

_DIMENSION_WEIGHTS: dict[str, float] = {
    "movement_vs_friction": 0.08,
    "recovery_vs_intensity": 0.09,
    "structure_vs_elasticity": 0.08,
    "breadth_vs_depth": 0.08,
    "iconic_vs_discovery": 0.09,
    "route_coherence_vs_eclectic_contrast": 0.08,
    "scenic_transit_vs_destination_time": 0.08,
}
_HYBRID_KEYWORDS: dict[str, tuple[str, ...]] = {
    "food": ("food", "cafe", "market", "restaurant", "dining"),
    "rest": ("rest", "quiet", "recovery", "sleep", "retreat", "calm"),
    "music": ("music", "concert", "theater", "performance", "festival"),
    "route_modes": ("rail", "ferry", "flight", "car", "route", "transit"),
}
_ANCHOR_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "lodging": ("hotel", "lodging", "retreat", "rental", "sleep"),
    "museum": ("museum", "gallery", "exhibit"),
    "food": ("food", "market", "restaurant", "cafe"),
    "scenic": ("scenic", "view", "hike", "outdoors"),
    "district": ("district", "wander", "neighborhood"),
}


def rank_leisure_candidates(
    *,
    trip_id: str,
    resolved_profile: ResolvedLeisureProfile,
    candidate_set: CandidateSet | None = None,
    bundles: Iterable[InventoryBundle] | None = None,
    objectives: ItineraryObjectives | None = None,
    feasibility_by_bundle_id: dict[str, FeasibilityAssessment] | None = None,
) -> RankedResultSet:
    """Rank leisure candidates from either a candidate set or raw bundles."""
    seeds, comparison_axes = _collect_inputs(
        trip_id=trip_id,
        candidate_set=candidate_set,
        bundles=bundles,
    )
    derived_objectives = objectives or derive_itinerary_objectives(
        resolved_profile,
        trip_id=trip_id,
    )
    feasibility_index = dict(feasibility_by_bundle_id or {})

    scored_results: list[tuple[float, RankedResult]] = []
    for seed in seeds:
        feasibility = feasibility_index.get(seed.bundle.bundle_id) or evaluate_bundle_feasibility(seed.bundle)
        score, result = _build_ranked_result(
            seed=seed,
            resolved_profile=resolved_profile,
            objectives=derived_objectives,
            feasibility=feasibility,
        )
        scored_results.append((score, result))

    ranked = sorted(
        scored_results,
        key=lambda item: (
            item[0],
            item[1].confidence_summary.overall_confidence or 0.0,
            item[1].target_bundle_id or "",
        ),
        reverse=True,
    )
    results = [
        _with_rank(result, rank=index)
        for index, (_, result) in enumerate(ranked, start=1)
    ]
    result_set_id = f"ranking:{trip_id}:leisure"
    result_explanations = [
        "Leisure ranking remains downstream from preference resolution, objective derivation, and feasibility evaluation.",
        "Scores keep component breakdowns, confidence penalties, and tension handling explicit for inspection.",
    ]
    source_refs = _dedupe_strings(
        source_ref
        for seed in seeds
        for source_ref in seed.bundle.provenance_summary.source_refs
    )
    return RankedResultSet(
        result_set_id=result_set_id,
        trip_id=trip_id,
        purpose="profile_learning",
        scope="mixed",
        title="Leisure candidate ranking",
        results=results,
        comparison_axes=comparison_axes,
        explanation=result_explanations,
        source_refs=source_refs,
    )


def _collect_inputs(
    *,
    trip_id: str,
    candidate_set: CandidateSet | None,
    bundles: Iterable[InventoryBundle] | None,
) -> tuple[list[CandidateSeed], list[ComparisonAxis]]:
    if (candidate_set is None) == (bundles is None):
        raise ValueError("provide exactly one of candidate_set or bundles")
    if candidate_set is not None:
        return list(candidate_set.seeds), list(candidate_set.comparison_axes)

    assert bundles is not None
    seeds = [
        CandidateSeed(
            candidate_id=f"candidate:{bundle.bundle_id}",
            bundle=bundle,
            supported_purposes=["profile_learning"],
            inclusion_reasons=list(bundle.explanation.strengths),
            unresolved_risks=list(bundle.explanation.tradeoffs),
        )
        for bundle in bundles
    ]
    if not seeds:
        raise ValueError("bundles must contain at least one InventoryBundle")
    axes = [
        ComparisonAxis(
            key="leisure_fit",
            label="Leisure fit",
            direction="higher_better",
            notes="Overall alignment with resolved leisure preferences and itinerary objectives.",
        ),
        ComparisonAxis(
            key="ranking_confidence",
            label="Ranking confidence",
            direction="higher_better",
            notes="Coverage and confidence after tension and missing-data penalties.",
        ),
    ]
    return seeds, axes


def _build_ranked_result(
    *,
    seed: CandidateSeed,
    resolved_profile: ResolvedLeisureProfile,
    objectives: ItineraryObjectives,
    feasibility: FeasibilityAssessment,
) -> tuple[float, RankedResult]:
    bundle = seed.bundle
    bundle_text = _bundle_text(bundle)

    quality_signal = _bundle_quality_signal(bundle)
    value_signal = bundle.quality_value_fit.value_signal or quality_signal
    fit_signal = bundle.quality_value_fit.fit_signal or quality_signal
    iconic_signal = _iconic_signal(bundle)
    discovery_signal = _discovery_signal(bundle)
    scenic_signal = _scenic_signal(bundle)
    efficiency_signal = _efficiency_signal(feasibility)
    recovery_signal = _recovery_signal(bundle, feasibility)
    intensity_signal = _intensity_signal(bundle)
    structure_signal = _structure_signal(bundle)
    elasticity_signal = _elasticity_signal(bundle)
    coherence_signal = _coherence_signal(bundle, feasibility)
    breadth_signal = _breadth_signal(bundle)
    depth_signal = _clamp(1.0 - breadth_signal)
    friction_signal = _clamp(1.0 - min(1.0, feasibility.friction_penalty_total))
    movement_signal = _movement_signal(bundle, feasibility)
    budget_signal = _budget_signal(seed, resolved_profile)
    quality_floor_signal = _quality_floor_signal(bundle)
    anchor_signal = _anchor_signal(resolved_profile, bundle_text)
    hybrid_signal = _hybrid_signal(resolved_profile, bundle_text, bundle)

    contributions = [
        _contribution(
            contribution_id=f"{bundle.bundle_id}:bundle-fit",
            label="Bundle fit foundation",
            axis_key="bundle_fit",
            normalized_signal=fit_signal,
            weighted_impact=(fit_signal - 0.5) * 0.16,
            summary="Carries forward the bundle-level fit signal from candidate assembly.",
        ),
        _contribution(
            contribution_id=f"{bundle.bundle_id}:quality-value",
            label="Quality and value posture",
            axis_key="quality_value",
            normalized_signal=_mean([quality_signal, value_signal]),
            weighted_impact=((quality_signal * 0.55) + (value_signal * 0.45) - 0.5) * 0.12,
            summary="Rewards bundles that preserve quality and value instead of collapsing them into one scalar.",
        ),
        _axis_contribution(
            bundle=bundle,
            resolved_profile=resolved_profile,
            dimension_key="iconic_vs_discovery",
            label="Discovery vs iconic alignment",
            positive_signal=iconic_signal,
            negative_signal=discovery_signal,
            positive_summary="Bundle better fits iconic or anchor-heavy priorities.",
            negative_summary="Bundle better fits discovery-forward wandering priorities.",
        ),
        _axis_contribution(
            bundle=bundle,
            resolved_profile=resolved_profile,
            dimension_key="scenic_transit_vs_destination_time",
            label="Transit style alignment",
            positive_signal=scenic_signal,
            negative_signal=efficiency_signal,
            positive_summary="Bundle rewards scenic transit as part of the experience.",
            negative_summary="Bundle protects destination time when scenic transit is not the main goal.",
        ),
        _axis_contribution(
            bundle=bundle,
            resolved_profile=resolved_profile,
            dimension_key="recovery_vs_intensity",
            label="Recovery alignment",
            positive_signal=recovery_signal,
            negative_signal=intensity_signal,
            positive_summary="Bundle protects recovery and schedule buffers.",
            negative_summary="Bundle tolerates higher activity intensity and movement load.",
        ),
        _axis_contribution(
            bundle=bundle,
            resolved_profile=resolved_profile,
            dimension_key="structure_vs_elasticity",
            label="Structure alignment",
            positive_signal=structure_signal,
            negative_signal=elasticity_signal,
            positive_summary="Bundle offers more structure and timed anchors.",
            negative_summary="Bundle preserves elastic, open-ended wandering room.",
        ),
        _axis_contribution(
            bundle=bundle,
            resolved_profile=resolved_profile,
            dimension_key="breadth_vs_depth",
            label="Breadth vs depth alignment",
            positive_signal=depth_signal,
            negative_signal=breadth_signal,
            positive_summary="Bundle favors deeper focus and fewer destination pivots.",
            negative_summary="Bundle supports broader coverage across more places.",
        ),
        _axis_contribution(
            bundle=bundle,
            resolved_profile=resolved_profile,
            dimension_key="route_coherence_vs_eclectic_contrast",
            label="Route shape alignment",
            positive_signal=coherence_signal,
            negative_signal=_clamp((breadth_signal * 0.75) + (discovery_signal * 0.25)),
            positive_summary="Bundle keeps the route coherent and lower-friction.",
            negative_summary="Bundle tolerates more eclectic contrast across the route.",
        ),
        _axis_contribution(
            bundle=bundle,
            resolved_profile=resolved_profile,
            dimension_key="movement_vs_friction",
            label="Movement vs friction alignment",
            positive_signal=movement_signal,
            negative_signal=friction_signal,
            positive_summary="Bundle keeps movement itself meaningful rather than dead travel.",
            negative_summary="Bundle limits travel friction when that matters more than movement.",
        ),
        _contribution(
            contribution_id=f"{bundle.bundle_id}:anchors",
            label="Anchor coverage",
            axis_key="anchors",
            normalized_signal=anchor_signal,
            weighted_impact=(anchor_signal - 0.5) * 0.08,
            summary="Matches named anchors against bundle tags, names, and summaries.",
        ),
        _contribution(
            contribution_id=f"{bundle.bundle_id}:hybrid-factors",
            label="Hybrid factor support",
            axis_key="hybrid_factors",
            normalized_signal=hybrid_signal,
            weighted_impact=(hybrid_signal - 0.5) * 0.07,
            summary="Recognizes salient hybrid factors such as food, rest, music, and route modes.",
        ),
        _contribution(
            contribution_id=f"{bundle.bundle_id}:budget",
            label="Budget posture",
            axis_key="budget",
            normalized_signal=budget_signal,
            weighted_impact=(budget_signal - 0.5) * 0.08,
            summary="Keeps budget posture explicit instead of silently assuming the cheapest bundle wins.",
        ),
        _contribution(
            contribution_id=f"{bundle.bundle_id}:quality-floor",
            label="Quality floors",
            axis_key="quality_floor",
            normalized_signal=quality_floor_signal,
            weighted_impact=(quality_floor_signal - 0.5) * 0.08,
            summary="Protects quality floors downstream from preference resolution and itinerary objective derivation.",
        ),
    ]

    penalties: list[ScoreAdjustment] = []
    missing_penalties: list[ScoreAdjustment] = []
    bonuses: list[ScoreAdjustment] = []

    if feasibility.friction_penalty_total > 0.35:
        penalties.append(
            ScoreAdjustment(
                adjustment_id=f"{bundle.bundle_id}:friction",
                label="Travel friction penalty",
                kind="penalty",
                amount=round(min(0.12, feasibility.friction_penalty_total * 0.06), 4),
                reason_code="travel_friction",
                summary="Higher transfer or movement friction remains visible in the score.",
                affected_factor_keys=["movement_vs_friction", "route_coherence_vs_eclectic_contrast"],
            )
        )
    if feasibility.blocking_reasons:
        penalties.append(
            ScoreAdjustment(
                adjustment_id=f"{bundle.bundle_id}:blocking",
                label="Feasibility blocker penalty",
                kind="penalty",
                amount=round(min(0.24, 0.08 * len(feasibility.blocking_reasons)), 4),
                reason_code="feasibility_blocking",
                summary="Bundle carries explicit feasibility blockers that should suppress ranking confidence.",
                affected_factor_keys=["feasibility"],
            )
        )
    if resolved_profile.profile.tension_flags:
        penalties.append(
            ScoreAdjustment(
                adjustment_id=f"{bundle.bundle_id}:tension",
                label="Preference tension penalty",
                kind="penalty",
                amount=round(
                    min(
                        0.12,
                        sum(flag.severity for flag in resolved_profile.profile.tension_flags) * 0.03,
                    ),
                    4,
                ),
                reason_code="preference_tension",
                summary="Unresolved preference tensions reduce ranking confidence and score.",
                affected_factor_keys=["tension_flags"],
            )
        )
    if feasibility.missing_data_fields:
        missing_penalties.append(
            ScoreAdjustment(
                adjustment_id=f"{bundle.bundle_id}:missing",
                label="Missing feasibility inputs",
                kind="missing_data",
                amount=round(min(0.12, 0.025 * len(feasibility.missing_data_fields)), 4),
                reason_code="missing_feasibility_data",
                summary="Missing feasibility inputs remain visible as ranking discounts.",
                affected_factor_keys=["missing_data"],
                notes=list(feasibility.missing_data_fields),
            )
        )
    if anchor_signal >= 0.75:
        bonuses.append(
            ScoreAdjustment(
                adjustment_id=f"{bundle.bundle_id}:anchor-bonus",
                label="Anchor match bonus",
                kind="bonus",
                amount=round((anchor_signal - 0.5) * 0.06, 4),
                reason_code="anchor_match",
                summary="Bundle directly matches one or more explicit anchors.",
                affected_factor_keys=["anchors"],
            )
        )

    low_confidence_flags = _low_confidence_flags(resolved_profile)
    coverage = _clamp(1.0 - (0.08 * len(feasibility.missing_data_fields)))
    stability = _mean(
        dimension.stability
        for dimension in resolved_profile.profile.tradeoff_dimensions.values()
    )
    overall_confidence = _clamp(
        mean(
            [
                feasibility.confidence_signal or 0.7,
                coverage,
                stability,
                max(0.0, 1.0 - (0.08 * len(resolved_profile.profile.tension_flags))),
            ]
        )
    )

    baseline_score = 0.5
    final_score = round(
        baseline_score
        + sum(item.weighted_impact for item in contributions)
        + sum(item.amount for item in bonuses)
        - sum(item.amount for item in penalties)
        - sum(item.amount for item in missing_penalties),
        4,
    )
    breakdown = ScoreBreakdown(
        baseline_score=baseline_score,
        component_contributions=contributions,
        penalties=penalties,
        bonuses=bonuses,
        missing_data_penalties=missing_penalties,
        final_score=final_score,
        notes=[
            "Leisure scoring stays deterministic and inspectable.",
            "Feasibility blockers and missing data remain visible instead of being collapsed into one opaque score.",
        ],
    )
    confidence_summary = ScoreConfidenceSummary(
        overall_confidence=overall_confidence,
        input_coverage=coverage,
        data_freshness=_freshness_signal(bundle),
        scoring_stability=stability,
        low_confidence_flags=low_confidence_flags,
        missing_data_fields=list(feasibility.missing_data_fields),
        notes=[
            f"Derived from {len(resolved_profile.profile.tension_flags)} active tension flags.",
            f"Feasibility confidence signal={feasibility.confidence_signal or 0.7:.2f}.",
        ],
    )
    explanation_records = _explanations_for_result(
        seed=seed,
        objectives=objectives,
        breakdown=breakdown,
        confidence_summary=confidence_summary,
    )
    unresolved_risks = _risks_for_result(
        resolved_profile=resolved_profile,
        feasibility=feasibility,
    )
    result = RankedResult(
        result_id=f"ranked:{bundle.bundle_id}",
        result_kind="bundle",
        rank=1,
        score=final_score,
        target_bundle_id=bundle.bundle_id,
        supporting_option_ids=bundle.option_ids,
        supporting_destination_ids=bundle.destination_ids,
        score_breakdown=breakdown,
        confidence_summary=confidence_summary,
        explanation_records=explanation_records,
        unresolved_risks=unresolved_risks,
        source_refs=list(bundle.provenance_summary.source_refs),
        notes=[
            "Leisure ranking outputs feed downstream explanation and review layers.",
            f"Objective route shape target: {objectives.route_shape}.",
        ],
    )
    return final_score, result


def _with_rank(result: RankedResult, *, rank: int) -> RankedResult:
    return RankedResult(
        result_id=result.result_id,
        result_kind=result.result_kind,
        rank=rank,
        score=result.score,
        target_bundle_id=result.target_bundle_id,
        supporting_option_ids=list(result.supporting_option_ids),
        supporting_destination_ids=list(result.supporting_destination_ids),
        score_breakdown=result.score_breakdown,
        confidence_summary=result.confidence_summary,
        explanation_records=list(result.explanation_records),
        unresolved_risks=list(result.unresolved_risks),
        source_refs=list(result.source_refs),
        notes=list(result.notes),
    )


def _contribution(
    *,
    contribution_id: str,
    label: str,
    axis_key: str,
    normalized_signal: float,
    weighted_impact: float,
    summary: str,
) -> ScoreContribution:
    return ScoreContribution(
        contribution_id=contribution_id,
        label=label,
        axis_key=axis_key,
        direction="higher_better",
        normalized_signal=_clamp(normalized_signal),
        weighted_impact=round(weighted_impact, 4),
        summary=summary,
    )


def _axis_contribution(
    *,
    bundle: InventoryBundle,
    resolved_profile: ResolvedLeisureProfile,
    dimension_key: str,
    label: str,
    positive_signal: float,
    negative_signal: float,
    positive_summary: str,
    negative_summary: str,
) -> ScoreContribution:
    dimension = resolved_profile.profile.tradeoff_dimensions[dimension_key]
    weight = _DIMENSION_WEIGHTS[dimension_key]
    if dimension.value >= 0:
        signal = positive_signal
        summary = positive_summary
    else:
        signal = negative_signal
        summary = negative_summary
    magnitude = 0.6 + (abs(dimension.value) * 0.4)
    return _contribution(
        contribution_id=f"{bundle.bundle_id}:{dimension_key}",
        label=label,
        axis_key=dimension_key,
        normalized_signal=signal,
        weighted_impact=(signal - 0.5) * weight * magnitude * 2.0,
        summary=summary,
    )


def _bundle_text(bundle: InventoryBundle) -> str:
    values = [
        bundle.title,
        bundle.summary,
        *bundle.tags,
        *bundle.notes,
        *bundle.explanation.strengths,
        *bundle.explanation.tradeoffs,
        *(item.name for item in bundle.lodging_options),
        *(item.name for item in bundle.activity_options),
        *(item.name for item in bundle.transport_options),
    ]
    return " ".join(values).lower()


def _mean(values: Iterable[float | None]) -> float:
    present = [value for value in values if value is not None]
    if not present:
        return 0.5
    return round(mean(present), 4)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, round(value, 4)))


def _dedupe_strings(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(item for item in values if item))


def _bundle_quality_signal(bundle: InventoryBundle) -> float:
    lodging_quality = _mean(item.quality_summary.overall_signal for item in bundle.lodging_options)
    activity_quality = _mean(item.quality_summary.overall_signal for item in bundle.activity_options)
    return _mean([bundle.quality_value_fit.quality_signal, lodging_quality, activity_quality])


def _iconic_signal(bundle: InventoryBundle) -> float:
    values = [
        item.significance_summary.local_icon_signal
        for item in bundle.activity_options
        if item.significance_summary.local_icon_signal is not None
    ]
    anchor_bonus = [
        1.0 if item.significance_summary.anchor_worthy else 0.0
        for item in bundle.activity_options
    ]
    return _mean(values + anchor_bonus)


def _discovery_signal(bundle: InventoryBundle) -> float:
    open_ended = [
        1.0 if item.category.open_ended else 0.0
        for item in bundle.activity_options
    ]
    wander_tags = [
        1.0
        for item in bundle.activity_options
        if {"wander", "open-ended", "district"} & set(item.tags)
    ]
    return _mean(open_ended + wander_tags or [0.45])


def _scenic_signal(bundle: InventoryBundle) -> float:
    scenic_values = [
        item.experience_summary.scenic_value_signal
        for item in bundle.transport_options
        if item.experience_summary.scenic_value_signal is not None
    ]
    scenic_values.extend(
        item.significance_summary.scenic_signal
        for item in bundle.activity_options
        if item.significance_summary.scenic_signal is not None
    )
    return _mean(scenic_values or [0.35])


def _efficiency_signal(feasibility: FeasibilityAssessment) -> float:
    travel_minutes = feasibility.total_travel_minutes
    transfer_count = feasibility.total_transfer_count
    return _clamp(1.0 - min(0.7, (travel_minutes / 540.0)) - min(0.3, transfer_count * 0.08))


def _recovery_signal(bundle: InventoryBundle, feasibility: FeasibilityAssessment) -> float:
    lodging_recovery = _mean(
        item.location_summary.recovery_signal for item in bundle.lodging_options
    )
    quiet_signal = _mean(
        item.location_summary.quiet_signal for item in bundle.lodging_options
    )
    conflict_penalty = min(
        0.4,
        len([item for item in feasibility.timing_conflicts if item.blocking]) * 0.18,
    )
    return _clamp(_mean([lodging_recovery, quiet_signal]) - conflict_penalty)


def _intensity_signal(bundle: InventoryBundle) -> float:
    values = [
        item.effort_summary.intensity_signal
        for item in bundle.activity_options
        if item.effort_summary.intensity_signal is not None
    ]
    values.extend(
        item.transfer_burden.self_navigation_burden_signal
        for item in bundle.transport_options
        if item.transfer_burden.self_navigation_burden_signal is not None
    )
    return _mean(values or [0.4])


def _structure_signal(bundle: InventoryBundle) -> float:
    values = [
        1.0 if item.booking_terms.booking_required else 0.35
        for item in bundle.activity_options
    ]
    return _mean(values or [0.45])


def _elasticity_signal(bundle: InventoryBundle) -> float:
    values = [
        1.0 if item.category.open_ended else 0.25
        for item in bundle.activity_options
    ]
    return _mean(values or [0.45])


def _coherence_signal(bundle: InventoryBundle, feasibility: FeasibilityAssessment) -> float:
    destination_penalty = max(0, len(bundle.destination_ids) - 1) * 0.14
    route_penalty = len(feasibility.route_warnings) * 0.1
    transfer_penalty = feasibility.total_transfer_count * 0.05
    return _clamp(1.0 - destination_penalty - route_penalty - transfer_penalty)


def _breadth_signal(bundle: InventoryBundle) -> float:
    return _clamp(min(1.0, max(0.0, (len(bundle.destination_ids) - 1) / 2.0)))


def _movement_signal(bundle: InventoryBundle, feasibility: FeasibilityAssessment) -> float:
    transport_weight = 0.25 if bundle.transport_options else 0.0
    travel_component = min(0.55, feasibility.total_travel_minutes / 420.0)
    scenic_component = _scenic_signal(bundle) * 0.2
    breadth_component = _breadth_signal(bundle) * 0.25
    return _clamp(travel_component + scenic_component + breadth_component + transport_weight)


def _budget_signal(seed: CandidateSeed, resolved_profile: ResolvedLeisureProfile) -> float:
    estimated_total = seed.estimated_total()
    base_signal = _mean([seed.bundle.quality_value_fit.value_signal, seed.bundle.quality_value_fit.fit_signal])
    budget_ceiling = resolved_profile.profile.hard_constraints.budget_ceiling
    sensitivity = resolved_profile.profile.budget_model.total_budget_sensitivity
    if estimated_total is None or budget_ceiling is None:
        return _clamp((base_signal * (0.65 + (sensitivity * 0.35))))
    if estimated_total.typical_amount is None:
        return base_signal
    budget_ratio = estimated_total.typical_amount / budget_ceiling if budget_ceiling else 1.0
    if budget_ratio <= 0.85:
        return _clamp(max(base_signal, 0.75))
    if budget_ratio <= 1.0:
        return _clamp(max(base_signal, 0.6))
    overspend_penalty = min(0.55, (budget_ratio - 1.0) * (0.7 + sensitivity))
    return _clamp(base_signal - overspend_penalty)


def _quality_floor_signal(bundle: InventoryBundle) -> float:
    lodging_signals = [
        item.quality_summary.overall_signal
        for item in bundle.lodging_options
        if item.quality_summary.overall_signal is not None
    ]
    sleep_signals = [
        item.quality_summary.sleep_quality_signal
        for item in bundle.lodging_options
        if item.quality_summary.sleep_quality_signal is not None
    ]
    return _mean(lodging_signals + sleep_signals or [bundle.quality_value_fit.quality_signal])


def _anchor_signal(resolved_profile: ResolvedLeisureProfile, bundle_text: str) -> float:
    matches: list[float] = []
    for group_name, anchors in resolved_profile.profile.anchors.items():
        for anchor in anchors:
            label_terms = [term for term in anchor.label.lower().replace("-", " ").split() if len(term) > 2]
            if any(term in bundle_text for term in label_terms):
                matches.append(anchor.strength)
                continue
            for keyword in _ANCHOR_TYPE_KEYWORDS.get(anchor.type.lower(), ()):
                if keyword in bundle_text:
                    matches.append(max(anchor.strength, 0.6))
                    break
        if matches and group_name == "quality_floor_anchors":
            matches.append(0.8)
    return _mean(matches or [0.45])


def _hybrid_signal(
    resolved_profile: ResolvedLeisureProfile,
    bundle_text: str,
    bundle: InventoryBundle,
) -> float:
    signals: list[float] = []
    for key, factor in resolved_profile.profile.hybrid_factors.items():
        keywords = _HYBRID_KEYWORDS.get(key, ())
        matched = any(keyword in bundle_text for keyword in keywords)
        if key == "rest" and bundle.lodging_options:
            matched = matched or _recovery_signal(bundle, evaluate_bundle_feasibility(bundle)) >= 0.7
        if matched:
            signals.append(_clamp((factor.salience * 0.7) + (factor.anchor_strength * 0.3)))
    return _mean(signals or [0.45])


def _freshness_signal(bundle: InventoryBundle) -> float:
    freshness: list[float] = []
    for destination in bundle.destinations:
        for destination_source in destination.source_refs:
            freshness_days = getattr(destination_source, "freshness_days_at_capture", None)
            if freshness_days is not None:
                freshness.append(_clamp(1.0 - min(1.0, freshness_days / 90.0)))
    for collection in (bundle.lodging_options, bundle.transport_options, bundle.activity_options):
        for option in collection:
            for option_source in option.source_refs:
                trust = getattr(option_source, "trust_snapshot", None)
                if trust and trust.freshness_days is not None:
                    freshness.append(_clamp(1.0 - min(1.0, trust.freshness_days / 90.0)))
                else:
                    freshness_days = getattr(option_source, "freshness_days_at_capture", None)
                    if freshness_days is not None:
                        freshness.append(_clamp(1.0 - min(1.0, freshness_days / 90.0)))
    return _mean(freshness or [0.75])


def _low_confidence_flags(resolved_profile: ResolvedLeisureProfile) -> list[str]:
    flags = [
        key
        for key, dimension in resolved_profile.profile.tradeoff_dimensions.items()
        if dimension.confidence < 0.55 and dimension.salience >= 0.35
    ]
    flags.extend(flag.id for flag in resolved_profile.profile.tension_flags)
    return _dedupe_strings(flags)


def _explanations_for_result(
    *,
    seed: CandidateSeed,
    objectives: ItineraryObjectives,
    breakdown: ScoreBreakdown,
    confidence_summary: ScoreConfidenceSummary,
) -> list[ExplanationRecord]:
    top_positive = max(
        breakdown.component_contributions,
        key=lambda item: item.weighted_impact,
    )
    top_negative = min(
        breakdown.component_contributions,
        key=lambda item: item.weighted_impact,
    )
    bundle = seed.bundle
    return [
        ExplanationRecord(
            explanation_id=f"{bundle.bundle_id}:summary",
            record_type="summary",
            target_kind="bundle",
            target_id=bundle.bundle_id,
            headline=f"{bundle.title} ranks through explicit leisure-fit signals.",
            summary=(
                f"Top positive driver: {top_positive.label.lower()}; "
                f"largest drag: {top_negative.label.lower()}."
            ),
            factor_keys=[top_positive.axis_key, top_negative.axis_key],
            machine_context={
                "route_shape": objectives.route_shape,
                "top_positive": top_positive.axis_key,
                "top_negative": top_negative.axis_key,
            },
            human_summary=[
                bundle.summary,
                top_positive.summary,
                top_negative.summary,
            ],
            source_refs=list(bundle.provenance_summary.source_refs),
        ),
        ExplanationRecord(
            explanation_id=f"{bundle.bundle_id}:promotion",
            record_type="promotion",
            target_kind="bundle",
            target_id=bundle.bundle_id,
            headline=f"{top_positive.label} promotes this bundle.",
            summary=top_positive.summary,
            factor_keys=[top_positive.axis_key],
            machine_context={"normalized_signal": f"{top_positive.normalized_signal or 0.0:.2f}"},
            human_summary=list(bundle.explanation.strengths[:2]) or [bundle.summary],
            source_refs=list(bundle.provenance_summary.source_refs),
        ),
        ExplanationRecord(
            explanation_id=f"{bundle.bundle_id}:confidence",
            record_type="confidence",
            target_kind="bundle",
            target_id=bundle.bundle_id,
            headline="Confidence remains explicit downstream.",
            summary=(
                f"Overall confidence={confidence_summary.overall_confidence or 0.0:.2f} "
                "after missing-data and tension handling."
            ),
            factor_keys=["ranking_confidence"],
            machine_context={
                "input_coverage": f"{confidence_summary.input_coverage or 0.0:.2f}",
                "scoring_stability": f"{confidence_summary.scoring_stability or 0.0:.2f}",
            },
            human_summary=confidence_summary.notes[:2] or ["Confidence remains inspectable."],
            source_refs=list(bundle.provenance_summary.source_refs),
        ),
    ]


def _risks_for_result(
    *,
    resolved_profile: ResolvedLeisureProfile,
    feasibility: FeasibilityAssessment,
) -> list[RiskFlag]:
    risks: list[RiskFlag] = []
    for blocking_reason in feasibility.blocking_reasons:
        risks.append(
            RiskFlag(
                risk_id=f"risk:{blocking_reason}",
                code=blocking_reason,
                severity="critical",
                summary=f"Bundle remains blocked by {blocking_reason}.",
                blocking=True,
            )
        )
    for warning in feasibility.route_warnings:
        risks.append(
            RiskFlag(
                risk_id=warning.warning_id,
                code=warning.code,
                severity="warning",
                summary=warning.summary,
            )
        )
    for flag in resolved_profile.profile.tension_flags:
        risks.append(
            RiskFlag(
                risk_id=f"risk:{flag.id}",
                code="preference_tension",
                severity="warning",
                summary=flag.description,
                notes=[flag.id],
            )
        )
    return risks
