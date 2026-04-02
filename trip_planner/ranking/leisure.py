"""Deterministic leisure ranking built on top of preference, objective, and feasibility contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import fmean

from trip_planner._option_contracts import (
    ComparisonAxis,
    MoneyRange,
    Option,
    OptionCostSummary,
    OptionQualitySummary,
)
from trip_planner.candidates import CandidateSet
from trip_planner.contracts import ItineraryObjectives
from trip_planner.itinerary import evaluate_bundle_feasibility
from trip_planner.itinerary.feasibility import FeasibilityAssessment
from trip_planner.options import InventoryBundle
from trip_planner.preferences import LeisurePreferenceProfile
from trip_planner.preferences.models import Anchor

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


def _clamp(value: float, min_value: float = 0.0, max_value: float = 1.0) -> float:
    return max(min_value, min(max_value, value))


def _round(value: float) -> float:
    return round(value, 4)


def _average(values: Sequence[float | None], default: float = 0.5) -> float:
    numeric = [value for value in values if value is not None]
    if not numeric:
        return default
    return _clamp(fmean(numeric))


def _searchable_bundle_text(bundle: InventoryBundle) -> str:
    values: list[str] = [bundle.title, bundle.summary, *bundle.tags, *bundle.notes]
    for destination in bundle.destinations:
        values.extend((destination.name, destination.place_kind, destination.summary))
    for lodging in bundle.lodging_options:
        values.extend(
            (
                lodging.name,
                lodging.location_summary.location_context,
                lodging.location_summary.access_summary,
                lodging.room_summary.lodging_kind,
            )
        )
    for transport in bundle.transport_options:
        values.extend((transport.name, transport.transport_kind))
        values.extend(segment.mode for segment in transport.segments)
    for activity in bundle.activity_options:
        values.extend(
            (activity.name, activity.activity_kind, activity.category.primary)
        )
    return " ".join(part.lower() for part in values if part)


def _estimate_bundle_total(bundle: InventoryBundle) -> MoneyRange | None:
    currency: str | None = None
    total = 0.0
    seen = False

    for lodging in bundle.lodging_options:
        amount = lodging.cost_summary.total or lodging.cost_summary.nightly
        if amount is None or amount.typical_amount is None:
            continue
        currency = currency or amount.currency
        if amount.currency != currency:
            return None
        total += amount.typical_amount
        seen = True

    for transport in bundle.transport_options:
        amount = transport.cost_summary.total
        if amount is None or amount.typical_amount is None:
            continue
        currency = currency or amount.currency
        if amount.currency != currency:
            return None
        total += amount.typical_amount
        seen = True

    for activity in bundle.activity_options:
        amount = activity.cost_summary.total or activity.cost_summary.per_person
        if amount is None or amount.typical_amount is None:
            continue
        currency = currency or amount.currency
        if amount.currency != currency:
            return None
        total += amount.typical_amount
        seen = True

    if not seen:
        return None
    return MoneyRange(currency=currency or "USD", typical_amount=round(total, 2))


@dataclass(slots=True)
class _RankableCandidate:
    candidate_id: str
    bundle: InventoryBundle
    target_option: Option
    source_refs: list[str]


class LeisureRankingEngine:
    """Rank leisure candidates without bypassing upstream profile or objective layers."""

    BASELINE_SCORE = 0.2
    COMPONENT_WEIGHTS: Mapping[str, float] = {
        "anchor_alignment": 0.16,
        "quality_floor_fit": 0.14,
        "budget_posture": 0.12,
        "route_coherence": 0.12,
        "discovery_fit": 0.12,
        "movement_friction_fit": 0.14,
        "recovery_protection": 0.10,
    }

    def validate_profile(
        self, profile: LeisurePreferenceProfile
    ) -> LeisurePreferenceProfile:
        if not isinstance(profile, LeisurePreferenceProfile):
            raise ValueError("profile must be a LeisurePreferenceProfile")
        return profile

    def validate_objectives(
        self, objectives: ItineraryObjectives
    ) -> ItineraryObjectives:
        if not isinstance(objectives, ItineraryObjectives):
            raise ValueError("objectives must be an ItineraryObjectives")
        return objectives

    def validate_feasibility_outputs(
        self,
        feasibility_outputs: (
            Mapping[str, FeasibilityAssessment] | Sequence[FeasibilityAssessment] | None
        ),
    ) -> dict[str, FeasibilityAssessment]:
        if feasibility_outputs is None:
            return {}
        if isinstance(feasibility_outputs, Mapping):
            values = dict(feasibility_outputs)
        elif isinstance(feasibility_outputs, Sequence):
            values = {item.bundle_id: item for item in feasibility_outputs}
        else:
            raise ValueError(
                "feasibility_outputs must be a mapping, a sequence of FeasibilityAssessment values, or None"
            )
        if any(not isinstance(item, FeasibilityAssessment) for item in values.values()):
            raise ValueError(
                "feasibility_outputs must contain FeasibilityAssessment instances"
            )
        return values

    def validate_candidate_set(self, candidate_set: CandidateSet) -> CandidateSet:
        if not isinstance(candidate_set, CandidateSet):
            raise ValueError("candidate_set must be a CandidateSet")
        return candidate_set

    def validate_bundles(
        self, bundles: Sequence[InventoryBundle]
    ) -> list[InventoryBundle]:
        if isinstance(bundles, (str, bytes)) or not isinstance(bundles, Sequence):
            raise ValueError("bundles must be a sequence of InventoryBundle instances")
        bundle_list = list(bundles)
        if not bundle_list:
            raise ValueError("bundles must contain at least one InventoryBundle")
        if any(not isinstance(item, InventoryBundle) for item in bundle_list):
            raise ValueError("bundles must contain InventoryBundle instances")
        return bundle_list

    def rank_candidate_set(
        self,
        profile: LeisurePreferenceProfile,
        objectives: ItineraryObjectives,
        candidate_set: CandidateSet,
        *,
        feasibility_outputs: (
            Mapping[str, FeasibilityAssessment] | Sequence[FeasibilityAssessment] | None
        ) = None,
        title: str = "Leisure candidate ranking",
    ) -> RankedResultSet:
        self.validate_profile(profile)
        self.validate_objectives(objectives)
        validated_set = self.validate_candidate_set(candidate_set)
        assessments = self.validate_feasibility_outputs(feasibility_outputs)

        candidates = [
            _RankableCandidate(
                candidate_id=seed.candidate_id,
                bundle=seed.bundle,
                target_option=seed.to_option(),
                source_refs=list(seed.bundle.provenance_summary.source_refs),
            )
            for seed in validated_set.seeds
        ]
        return self._rank(
            profile,
            objectives,
            candidates,
            trip_id=validated_set.trip_id,
            purpose=validated_set.purpose,
            title=title,
            source_refs=[validated_set.candidate_set_id, *validated_set.source_refs],
            assessments=assessments,
        )

    def rank_bundles(
        self,
        profile: LeisurePreferenceProfile,
        objectives: ItineraryObjectives,
        bundles: Sequence[InventoryBundle],
        *,
        trip_id: str,
        purpose: str = "final_selection",
        title: str = "Leisure bundle ranking",
        feasibility_outputs: (
            Mapping[str, FeasibilityAssessment] | Sequence[FeasibilityAssessment] | None
        ) = None,
    ) -> RankedResultSet:
        self.validate_profile(profile)
        self.validate_objectives(objectives)
        validated_bundles = self.validate_bundles(bundles)
        assessments = self.validate_feasibility_outputs(feasibility_outputs)
        candidates = [
            _RankableCandidate(
                candidate_id=bundle.bundle_id,
                bundle=bundle,
                target_option=self._bundle_to_option(bundle),
                source_refs=list(bundle.provenance_summary.source_refs),
            )
            for bundle in validated_bundles
        ]
        return self._rank(
            profile,
            objectives,
            candidates,
            trip_id=trip_id,
            purpose=purpose,
            title=title,
            source_refs=[],
            assessments=assessments,
        )

    def _rank(
        self,
        profile: LeisurePreferenceProfile,
        objectives: ItineraryObjectives,
        candidates: list[_RankableCandidate],
        *,
        trip_id: str,
        purpose: str,
        title: str,
        source_refs: list[str],
        assessments: dict[str, FeasibilityAssessment],
    ) -> RankedResultSet:
        scored: list[tuple[float, RankedResult]] = []
        for candidate in candidates:
            assessment = assessments.get(
                candidate.bundle.bundle_id
            ) or evaluate_bundle_feasibility(candidate.bundle)
            result = self._score_candidate(profile, objectives, candidate, assessment)
            scored.append((result.score, result))

        scored.sort(
            key=lambda item: (
                -item[0],
                item[1].confidence_summary.overall_confidence or 0.0,
                item[1].result_id,
            )
        )

        reranked_results: list[RankedResult] = []
        for rank, (_, result) in enumerate(scored, start=1):
            reranked_results.append(
                RankedResult(
                    result_id=result.result_id,
                    result_kind=result.result_kind,
                    rank=rank,
                    score=result.score,
                    target_option=result.target_option,
                    supporting_option_ids=result.supporting_option_ids,
                    supporting_destination_ids=result.supporting_destination_ids,
                    score_breakdown=result.score_breakdown,
                    confidence_summary=result.confidence_summary,
                    explanation_records=result.explanation_records,
                    unresolved_risks=result.unresolved_risks,
                    source_refs=result.source_refs,
                    notes=result.notes,
                )
            )

        return RankedResultSet(
            result_set_id=f"ranked-results:{trip_id}:{purpose}:leisure",
            trip_id=trip_id,
            purpose=purpose,
            scope="mixed",
            title=title,
            results=reranked_results,
            comparison_axes=self._comparison_axes(),
            explanation=[
                "Leisure ranking remains downstream from preference resolution and itinerary-objective derivation.",
                "Scores combine profile fit, objective alignment, feasibility friction, and confidence penalties.",
            ],
            source_refs=source_refs,
        )

    def _score_candidate(
        self,
        profile: LeisurePreferenceProfile,
        objectives: ItineraryObjectives,
        candidate: _RankableCandidate,
        assessment: FeasibilityAssessment,
    ) -> RankedResult:
        bundle = candidate.bundle
        contributions = [
            self._build_component(
                "anchor_alignment",
                "Anchor alignment",
                self._anchor_alignment_signal(bundle, profile),
                "Anchors reward candidates that preserve explicitly requested places, experiences, modes, and rhythms.",
                source_refs=candidate.source_refs,
            ),
            self._build_component(
                "quality_floor_fit",
                "Quality floor fit",
                self._quality_floor_signal(bundle, profile, objectives),
                "Quality-floor fit reflects lodging comfort, bundle quality, and required floor categories.",
                source_refs=candidate.source_refs,
            ),
            self._build_component(
                "budget_posture",
                "Budget posture",
                self._budget_posture_signal(bundle, profile, objectives),
                "Budget posture stays sensitive to hard ceilings and the profile's cost posture.",
                source_refs=candidate.source_refs,
            ),
            self._build_component(
                "route_coherence",
                "Route coherence",
                self._route_coherence_signal(bundle, objectives, assessment),
                "Route coherence rewards destination flow that matches the derived itinerary shape.",
                source_refs=candidate.source_refs,
            ),
            self._build_component(
                "discovery_fit",
                "Discovery fit",
                self._discovery_fit_signal(bundle, objectives),
                "Discovery fit compares candidate character with the derived discovery strategy.",
                source_refs=candidate.source_refs,
            ),
            self._build_component(
                "movement_friction_fit",
                "Movement and friction fit",
                self._movement_friction_fit_signal(bundle, objectives, assessment),
                "Movement fit uses transfer burden and travel friction instead of bypassing feasibility output.",
                source_refs=candidate.source_refs,
            ),
            self._build_component(
                "recovery_protection",
                "Recovery protection",
                self._recovery_protection_signal(bundle, objectives, assessment),
                "Recovery protection rewards quiet lodging and schedule slack when the objectives require it.",
                source_refs=candidate.source_refs,
            ),
        ]

        penalties = self._build_penalties(profile, objectives, bundle, assessment)
        bonuses = self._build_bonuses(objectives, bundle, assessment)
        missing_data_penalties = self._build_missing_data_penalties(profile, assessment)

        baseline_score = self.BASELINE_SCORE
        final_score = _round(
            baseline_score
            + sum(item.weighted_impact for item in contributions)
            + sum(item.amount for item in bonuses)
            - sum(item.amount for item in penalties)
            - sum(item.amount for item in missing_data_penalties)
        )
        score_breakdown = ScoreBreakdown(
            baseline_score=baseline_score,
            component_contributions=contributions,
            penalties=penalties,
            bonuses=bonuses,
            missing_data_penalties=missing_data_penalties,
            final_score=final_score,
            notes=[
                "Feasibility output informs ranking friction but does not replace preference or objective fit.",
            ],
        )
        confidence_summary = self._confidence_summary(profile, assessment)
        unresolved_risks = self._risk_flags(profile, assessment)
        explanation_records = self._explanation_records(
            candidate,
            contributions,
            penalties,
            bonuses,
            missing_data_penalties,
            confidence_summary,
            unresolved_risks,
        )

        return RankedResult(
            result_id=f"ranked:item:{candidate.candidate_id}",
            result_kind="item",
            rank=1,
            score=final_score,
            target_option=candidate.target_option,
            supporting_option_ids=list(candidate.bundle.option_ids),
            supporting_destination_ids=list(candidate.bundle.destination_ids),
            score_breakdown=score_breakdown,
            confidence_summary=confidence_summary,
            explanation_records=explanation_records,
            unresolved_risks=unresolved_risks,
            source_refs=list(dict.fromkeys(candidate.source_refs)),
            notes=[f"bundle_id={candidate.bundle.bundle_id}"],
        )

    def _build_component(
        self,
        key: str,
        label: str,
        signal: float,
        summary: str,
        *,
        source_refs: list[str],
    ) -> ScoreContribution:
        normalized_signal = _round(signal)
        weighted_impact = _round(normalized_signal * self.COMPONENT_WEIGHTS[key])
        return ScoreContribution(
            contribution_id=key,
            label=label,
            axis_key=key,
            direction="higher_better",
            raw_value=normalized_signal,
            normalized_signal=normalized_signal,
            weighted_impact=weighted_impact,
            summary=summary,
            evidence_refs=source_refs[:3],
        )

    def _anchor_alignment_signal(
        self, bundle: InventoryBundle, profile: LeisurePreferenceProfile
    ) -> float:
        anchors = [anchor for group in profile.anchors.values() for anchor in group]
        if not anchors:
            return 0.5
        searchable = _searchable_bundle_text(bundle)
        matched_weight = 0.0
        total_weight = 0.0
        for anchor in anchors:
            weight = max(0.05, anchor.strength)
            total_weight += weight
            matched_weight += weight * self._anchor_match(bundle, searchable, anchor)
        return _clamp(matched_weight / total_weight if total_weight else 0.5)

    def _anchor_match(
        self, bundle: InventoryBundle, searchable: str, anchor: Anchor
    ) -> float:
        label_tokens = [
            token for token in anchor.label.lower().replace("-", " ").split() if token
        ]
        type_token = anchor.type.lower().replace("_", " ")
        if anchor.label.lower() in searchable or type_token in searchable:
            return 1.0
        if any(token in searchable for token in label_tokens):
            return 0.8
        if "museum" in type_token and any(
            activity.activity_kind == "museum" for activity in bundle.activity_options
        ):
            return 0.95
        if any(
            word in type_token for word in ("wander", "district", "discovery")
        ) and any(
            activity.activity_kind in {"district", "market", "neighborhood"}
            for activity in bundle.activity_options
        ):
            return 0.95
        if any(word in type_token for word in ("rail", "ferry", "transit")) and any(
            transport.transport_kind in {"rail", "ferry"}
            for transport in bundle.transport_options
        ):
            return 0.95
        if any(word in type_token for word in ("quiet", "sleep", "recovery")):
            recovery_signal = _average(
                [
                    lodging.fit_summary.quiet_recovery_signal
                    for lodging in bundle.lodging_options
                ],
                default=0.5,
            )
            return recovery_signal
        return 0.1 + (anchor.flexibility * 0.2)

    def _quality_floor_signal(
        self,
        bundle: InventoryBundle,
        profile: LeisurePreferenceProfile,
        objectives: ItineraryObjectives,
    ) -> float:
        bundle_quality = bundle.quality_value_fit.quality_signal
        lodging_quality = _average(
            [
                lodging.quality_summary.overall_signal
                for lodging in bundle.lodging_options
            ],
            default=0.5,
        )
        comfort_signal = _average(
            [lodging.room_summary.comfort_signal for lodging in bundle.lodging_options],
            default=0.5,
        )
        activity_quality = _average(
            [
                activity.quality_summary.overall_signal
                for activity in bundle.activity_options
            ],
            default=0.5,
        )
        quality_signal = _average(
            [bundle_quality, lodging_quality, comfort_signal, activity_quality],
            default=0.5,
        )
        required = set(objectives.quality_floor_protection.required_categories)
        if "lodging" in required or "sleep_recovery" in required:
            quality_signal = _average(
                [quality_signal, comfort_signal, lodging_quality], default=0.5
            )
        if profile.anchors["quality_floor_anchors"]:
            quality_signal = _clamp(quality_signal + 0.08)
        return quality_signal

    def _budget_posture_signal(
        self,
        bundle: InventoryBundle,
        profile: LeisurePreferenceProfile,
        objectives: ItineraryObjectives,
    ) -> float:
        sensitivity = profile.budget_model.total_budget_sensitivity
        estimated_total = _estimate_bundle_total(bundle)
        ceiling = profile.hard_constraints.budget_ceiling
        if estimated_total is None or estimated_total.typical_amount is None:
            return 0.55 - (0.1 * sensitivity)
        if ceiling is not None and ceiling > 0:
            ratio = estimated_total.typical_amount / ceiling
            if ratio <= 0.85:
                return _clamp(0.95 - (sensitivity * 0.05))
            if ratio <= 1.0:
                return _clamp(0.82 - ((ratio - 0.85) / 0.15) * 0.18)
            overrun = min(1.0, ratio - 1.0)
            return _clamp(0.55 - overrun * (0.35 + (0.3 * sensitivity)))
        protected_categories = objectives.budget_protection.protected_categories
        signal = 0.72 - (0.18 * sensitivity)
        if "lodging" in protected_categories and bundle.lodging_options:
            signal += 0.06
        return _clamp(signal)

    def _route_coherence_signal(
        self,
        bundle: InventoryBundle,
        objectives: ItineraryObjectives,
        assessment: FeasibilityAssessment,
    ) -> float:
        destination_count = max(1, len(bundle.destination_ids))
        route_warning_penalty = min(0.35, 0.12 * len(assessment.route_warnings))
        base = 0.82 - route_warning_penalty
        if objectives.route_shape == "hub_and_spoke":
            base -= 0.1 * max(0, destination_count - 2)
        elif objectives.route_shape == "linear":
            base -= 0.06 * max(0, 2 - destination_count)
        elif objectives.route_shape == "regional_cluster":
            base -= 0.04 * abs(destination_count - 2)
        transfer_penalty = min(0.2, assessment.total_transfer_count * 0.04)
        return _clamp(base - transfer_penalty)

    def _discovery_fit_signal(
        self, bundle: InventoryBundle, objectives: ItineraryObjectives
    ) -> float:
        if objectives.discovery_strategy.style == "discovery_forward":
            target = 0.9
        elif objectives.discovery_strategy.style == "iconic":
            target = 0.15
        else:
            target = 0.5

        discovery_features: list[float] = []
        for activity in bundle.activity_options:
            if activity.activity_kind in {"district", "market", "neighborhood"}:
                discovery_features.append(0.95)
            elif activity.activity_kind in {"museum", "monument", "ticketed_event"}:
                discovery_features.append(0.15)
            elif activity.activity_kind in {"landscape", "hike", "outdoor"}:
                discovery_features.append(0.7)
            else:
                discovery_features.append(0.5)
        observed = _average(discovery_features, default=0.45)
        observed = _clamp(
            observed + ((objectives.day_structure.wandering_support_level - 0.5) * 0.2)
        )
        return _clamp(1.0 - abs(observed - target))

    def _movement_friction_fit_signal(
        self,
        bundle: InventoryBundle,
        objectives: ItineraryObjectives,
        assessment: FeasibilityAssessment,
    ) -> float:
        burden_from_minutes = min(1.0, assessment.total_travel_minutes / 360.0)
        burden_from_transfers = min(1.0, assessment.total_transfer_count / 4.0)
        friction = _clamp(
            0.5 * burden_from_minutes
            + 0.3 * burden_from_transfers
            + 0.2 * min(1.0, assessment.friction_penalty_total / 1.5)
        )
        move_budget = objectives.move_density.max_moves or 2
        tolerance = _clamp(0.25 + (min(move_budget, 5) / 5.0) * 0.45)
        if objectives.transport_strategy.transit_is_feature:
            tolerance = _clamp(tolerance + 0.12)
        return _clamp(1.0 - max(0.0, friction - tolerance))

    def _recovery_protection_signal(
        self,
        bundle: InventoryBundle,
        objectives: ItineraryObjectives,
        assessment: FeasibilityAssessment,
    ) -> float:
        quiet_recovery = _average(
            [
                lodging.fit_summary.quiet_recovery_signal
                for lodging in bundle.lodging_options
            ],
            default=0.5,
        )
        buffer_support = _clamp(1.0 - min(1.0, len(assessment.timing_conflicts) / 3.0))
        desired = objectives.recovery_expectations.recovery_priority
        observed = _average([quiet_recovery, buffer_support], default=0.5)
        if desired >= 0.7:
            return _average([observed, quiet_recovery], default=0.5)
        return _clamp(1.0 - abs(observed - max(0.35, desired)))

    def _build_penalties(
        self,
        profile: LeisurePreferenceProfile,
        objectives: ItineraryObjectives,
        bundle: InventoryBundle,
        assessment: FeasibilityAssessment,
    ) -> list[ScoreAdjustment]:
        penalties: list[ScoreAdjustment] = []
        if not assessment.recommended_for_ranking or not assessment.feasible:
            penalties.append(
                ScoreAdjustment(
                    adjustment_id="feasibility-blocker",
                    label="Feasibility blocker",
                    kind="penalty",
                    amount=0.2,
                    reason_code="feasibility_blocker",
                    summary="The feasibility layer found blocking issues that should materially suppress rank.",
                    affected_factor_keys=["movement_friction_fit", "route_coherence"],
                )
            )
        if assessment.route_warnings:
            penalties.append(
                ScoreAdjustment(
                    adjustment_id="route-warning",
                    label="Route warning penalty",
                    kind="penalty",
                    amount=_round(min(0.12, 0.04 * len(assessment.route_warnings))),
                    reason_code=assessment.route_warnings[0].code,
                    summary="Route continuity warnings reduce confidence in the itinerary shape.",
                    affected_factor_keys=["route_coherence"],
                )
            )
        quality_signal = self._quality_floor_signal(bundle, profile, objectives)
        if (
            objectives.quality_floor_protection.required_categories
            and quality_signal < 0.7
        ):
            penalties.append(
                ScoreAdjustment(
                    adjustment_id="quality-floor",
                    label="Quality floor penalty",
                    kind="penalty",
                    amount=_round((0.7 - quality_signal) * 0.2),
                    reason_code="quality_floor_gap",
                    summary="The candidate falls short of the requested minimum comfort or quality floor.",
                    affected_factor_keys=["quality_floor_fit"],
                )
            )
        tension_penalty = _round(
            min(0.12, sum(flag.severity for flag in profile.tension_flags) * 0.05)
        )
        if tension_penalty:
            penalties.append(
                ScoreAdjustment(
                    adjustment_id="tension-flags",
                    label="Tension penalty",
                    kind="penalty",
                    amount=tension_penalty,
                    reason_code="preference_tension",
                    summary="Unresolved preference tensions reduce ranking confidence and slightly suppress promotion.",
                    affected_factor_keys=["anchor_alignment", "recovery_protection"],
                )
            )
        return penalties

    def _build_bonuses(
        self,
        objectives: ItineraryObjectives,
        bundle: InventoryBundle,
        assessment: FeasibilityAssessment,
    ) -> list[ScoreAdjustment]:
        bonuses: list[ScoreAdjustment] = []
        if (
            objectives.transport_strategy.transit_is_feature
            and any(
                transport.transport_kind in {"rail", "ferry"}
                for transport in bundle.transport_options
            )
            and assessment.total_transfer_count <= 1
        ):
            bonuses.append(
                ScoreAdjustment(
                    adjustment_id="transit-feature",
                    label="Transit-as-feature bonus",
                    kind="bonus",
                    amount=0.04,
                    reason_code="transit_is_feature",
                    summary="The candidate turns transport into part of the leisure experience without excessive friction.",
                    affected_factor_keys=["movement_friction_fit", "discovery_fit"],
                )
            )
        return bonuses

    def _build_missing_data_penalties(
        self,
        profile: LeisurePreferenceProfile,
        assessment: FeasibilityAssessment,
    ) -> list[ScoreAdjustment]:
        penalties: list[ScoreAdjustment] = []
        if assessment.missing_data_fields:
            penalties.append(
                ScoreAdjustment(
                    adjustment_id="missing-feasibility-data",
                    label="Missing feasibility data",
                    kind="missing_data",
                    amount=_round(min(0.1, 0.02 * len(assessment.missing_data_fields))),
                    reason_code="missing_feasibility_data",
                    summary="Incomplete timing or travel detail lowers ranking confidence.",
                    affected_factor_keys=[
                        "movement_friction_fit",
                        "recovery_protection",
                    ],
                    notes=assessment.missing_data_fields[:4],
                )
            )
        low_confidence_dimensions = [
            key
            for key, dimension in profile.tradeoff_dimensions.items()
            if dimension.confidence < 0.45 and dimension.salience >= 0.5
        ]
        if low_confidence_dimensions:
            penalties.append(
                ScoreAdjustment(
                    adjustment_id="low-confidence-profile",
                    label="Low-confidence preference inputs",
                    kind="missing_data",
                    amount=_round(min(0.08, 0.015 * len(low_confidence_dimensions))),
                    reason_code="low_confidence_profile",
                    summary="High-salience preference dimensions remain weakly evidenced.",
                    affected_factor_keys=low_confidence_dimensions[:4],
                    notes=low_confidence_dimensions[:4],
                )
            )
        return penalties

    def _confidence_summary(
        self,
        profile: LeisurePreferenceProfile,
        assessment: FeasibilityAssessment,
    ) -> ScoreConfidenceSummary:
        dimension_confidences = [
            dimension.confidence for dimension in profile.tradeoff_dimensions.values()
        ]
        dimension_stabilities = [
            dimension.stability for dimension in profile.tradeoff_dimensions.values()
        ]
        input_coverage = _round(
            _clamp(
                1.0
                - (0.03 * len(assessment.missing_data_fields))
                - (
                    0.02
                    * len(
                        [
                            key
                            for key, dimension in profile.tradeoff_dimensions.items()
                            if dimension.confidence < 0.45
                        ]
                    )
                )
            )
        )
        data_freshness = _round(assessment.confidence_signal or 0.72)
        scoring_stability = _round(
            _clamp(
                (_average(dimension_stabilities, default=0.65) * 0.7)
                + (_average(dimension_confidences, default=0.65) * 0.3)
                - (0.05 * len(profile.tension_flags))
            )
        )
        overall_confidence = _round(
            _clamp(fmean([input_coverage, data_freshness, scoring_stability]))
        )
        low_confidence_flags = sorted(
            {
                *assessment.blocking_reasons,
                *[
                    f"low_confidence:{key}"
                    for key, dimension in profile.tradeoff_dimensions.items()
                    if dimension.confidence < 0.45 and dimension.salience >= 0.5
                ],
                *[f"tension:{flag.id}" for flag in profile.tension_flags],
            }
        )
        return ScoreConfidenceSummary(
            overall_confidence=overall_confidence,
            input_coverage=input_coverage,
            data_freshness=data_freshness,
            scoring_stability=scoring_stability,
            low_confidence_flags=low_confidence_flags,
            missing_data_fields=list(assessment.missing_data_fields),
            notes=[
                "Confidence falls when feasibility gaps or unresolved preference tensions remain in play."
            ],
        )

    def _explanation_records(
        self,
        candidate: _RankableCandidate,
        contributions: list[ScoreContribution],
        penalties: list[ScoreAdjustment],
        bonuses: list[ScoreAdjustment],
        missing_data_penalties: list[ScoreAdjustment],
        confidence_summary: ScoreConfidenceSummary,
        unresolved_risks: list[RiskFlag],
    ) -> list[ExplanationRecord]:
        dominant = sorted(
            contributions,
            key=lambda item: (-item.weighted_impact, item.contribution_id),
        )[:2]
        records = [
            ExplanationRecord(
                explanation_id=f"summary:{candidate.candidate_id}",
                record_type="summary",
                target_kind="item",
                target_id=candidate.target_option.option_id,
                headline="Preference-aware leisure ranking summary",
                summary=(
                    f"{candidate.target_option.label} ranks on objective fit, profile alignment, and "
                    "feasibility-aware movement tradeoffs."
                ),
                factor_keys=[item.contribution_id for item in dominant],
                machine_context={
                    "primary_axis": dominant[0].contribution_id
                    if dominant
                    else "anchor_alignment",
                    "confidence": f"{confidence_summary.overall_confidence or 0.0:.2f}",
                },
                human_summary=[item.label for item in dominant]
                + [penalty.label for penalty in penalties[:1]],
                source_refs=candidate.source_refs[:3],
            )
        ]
        for bonus in bonuses[:2]:
            records.append(
                ExplanationRecord(
                    explanation_id=f"promotion:{candidate.candidate_id}:{bonus.adjustment_id}",
                    record_type="promotion",
                    target_kind="item",
                    target_id=candidate.target_option.option_id,
                    headline=bonus.label,
                    summary=bonus.summary,
                    factor_keys=list(bonus.affected_factor_keys),
                    machine_context={"reason_code": bonus.reason_code},
                    human_summary=[bonus.label, bonus.summary],
                    source_refs=candidate.source_refs[:2],
                )
            )
        for penalty in penalties[:2]:
            records.append(
                ExplanationRecord(
                    explanation_id=f"penalty:{candidate.candidate_id}:{penalty.adjustment_id}",
                    record_type="penalty",
                    target_kind="item",
                    target_id=candidate.target_option.option_id,
                    headline=penalty.label,
                    summary=penalty.summary,
                    factor_keys=list(penalty.affected_factor_keys),
                    machine_context={"reason_code": penalty.reason_code},
                    human_summary=[penalty.label, penalty.summary],
                    source_refs=candidate.source_refs[:2],
                )
            )
        if confidence_summary.low_confidence_flags or missing_data_penalties:
            records.append(
                ExplanationRecord(
                    explanation_id=f"confidence:{candidate.candidate_id}",
                    record_type="confidence",
                    target_kind="item",
                    target_id=candidate.target_option.option_id,
                    headline="Confidence caveats",
                    summary=(
                        "Ranking confidence is reduced by low-confidence preference areas or incomplete feasibility data."
                    ),
                    factor_keys=[
                        *confidence_summary.low_confidence_flags[:3],
                        *[
                            penalty.reason_code
                            for penalty in missing_data_penalties[:1]
                        ],
                    ],
                    machine_context={
                        "overall_confidence": f"{confidence_summary.overall_confidence or 0.0:.2f}"
                    },
                    human_summary=confidence_summary.low_confidence_flags[:3]
                    or ["Missing data penalty applied"],
                    source_refs=candidate.source_refs[:2],
                )
            )
        for risk in unresolved_risks[:2]:
            records.append(
                ExplanationRecord(
                    explanation_id=f"risk:{candidate.candidate_id}:{risk.risk_id}",
                    record_type="risk",
                    target_kind="item",
                    target_id=candidate.target_option.option_id,
                    headline=risk.code,
                    summary=risk.summary,
                    factor_keys=[risk.code],
                    machine_context={"severity": risk.severity},
                    human_summary=[risk.summary],
                    source_refs=candidate.source_refs[:2],
                )
            )
        return records

    def _risk_flags(
        self,
        profile: LeisurePreferenceProfile,
        assessment: FeasibilityAssessment,
    ) -> list[RiskFlag]:
        risks: list[RiskFlag] = []
        for blocking_reason in assessment.blocking_reasons:
            risks.append(
                RiskFlag(
                    risk_id=f"risk:{assessment.bundle_id}:{blocking_reason}",
                    code=blocking_reason,
                    severity="critical"
                    if not assessment.recommended_for_ranking
                    else "warning",
                    summary=f"Feasibility issue remains unresolved: {blocking_reason}.",
                    blocking=not assessment.recommended_for_ranking,
                )
            )
        for warning in assessment.route_warnings[:2]:
            risks.append(
                RiskFlag(
                    risk_id=f"risk:{warning.warning_id}",
                    code=warning.code,
                    severity="warning",
                    summary=warning.summary,
                )
            )
        for flag in profile.tension_flags[:2]:
            risks.append(
                RiskFlag(
                    risk_id=f"risk:tension:{flag.id}",
                    code="preference_tension",
                    severity="warning",
                    summary=flag.description,
                )
            )
        return risks

    def _bundle_to_option(self, bundle: InventoryBundle) -> Option:
        estimated_total = _estimate_bundle_total(bundle)
        fit_signal = bundle.quality_value_fit.fit_signal
        quality_signal = bundle.quality_value_fit.quality_signal
        value_signal = bundle.quality_value_fit.value_signal
        return Option(
            option_id=bundle.bundle_id,
            kind="mixed",
            label=bundle.title,
            summary=bundle.summary,
            fit_signals={
                key: value
                for key, value in {
                    "quality": quality_signal,
                    "value": value_signal,
                    "fit": fit_signal,
                }.items()
                if value is not None
            },
            cost_summary=OptionCostSummary(total=estimated_total),
            quality_summary=OptionQualitySummary(
                quality_signal=quality_signal,
                value_signal=value_signal,
                fit_signal=fit_signal,
            ),
            drawbacks=list(bundle.explanation.tradeoffs)
            + list(bundle.feasibility.blocking_reasons),
            booking_links=list(bundle.provenance_summary.booking_links),
            source_refs=list(bundle.provenance_summary.source_refs),
            supporting_place_ids=list(bundle.destination_ids),
            explanation=list(bundle.explanation.strengths)
            + list(bundle.explanation.evidence),
        )

    def _comparison_axes(self) -> list[ComparisonAxis]:
        return [
            ComparisonAxis(
                key="profile_fit",
                label="Profile fit",
                direction="higher_better",
                notes="Alignment with resolved leisure preferences and anchors.",
            ),
            ComparisonAxis(
                key="feasibility_friction",
                label="Feasibility friction",
                direction="lower_better",
                notes="Transfer burden, timing conflicts, and ranking blockers remain visible.",
            ),
            ComparisonAxis(
                key="confidence",
                label="Ranking confidence",
                direction="higher_better",
                notes="Low-confidence preference areas and missing data lower certainty.",
            ),
        ]
