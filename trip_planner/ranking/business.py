"""Deterministic business ranking built on policy-aware planning objectives."""

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
from trip_planner.business import (
    BusinessPlanningObjectives,
    BusinessTravelProfile,
    PolicyConstraintSet,
)
from trip_planner.candidates import CandidateSet
from trip_planner.itinerary import evaluate_bundle_feasibility
from trip_planner.itinerary.feasibility import FeasibilityAssessment
from trip_planner.options import InventoryBundle

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

_APPROVAL_SIGNALS: dict[str, float] = {
    "approved": 1.0,
    "preferred": 0.92,
    "unknown": 0.55,
    "restricted": 0.28,
    "disallowed": 0.0,
}


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _round(value: float) -> float:
    return round(value, 4)


def _average(values: Sequence[float | None], *, default: float = 0.5) -> float:
    numeric = [value for value in values if value is not None]
    if not numeric:
        return default
    return _clamp(fmean(numeric))


def _dedupe_strings(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def _searchable_bundle_text(bundle: InventoryBundle) -> str:
    values: list[str] = [bundle.title, bundle.summary, *bundle.tags, *bundle.notes]
    values.extend(bundle.explanation.strengths)
    values.extend(bundle.explanation.tradeoffs)
    values.extend(bundle.explanation.evidence)
    for lodging in bundle.lodging_options:
        values.extend(
            [
                lodging.name,
                lodging.summary,
                *lodging.tags,
                *lodging.notes,
                *lodging.feasibility.constraints,
            ]
        )
    for transport in bundle.transport_options:
        values.extend(
            [
                transport.name,
                transport.summary,
                *transport.tags,
                *transport.notes,
                *transport.policy_summary.policy_notes,
                *transport.feasibility.constraints,
            ]
        )
    return " ".join(part.lower() for part in values if part)


@dataclass(slots=True)
class _RankableBusinessCandidate:
    candidate_id: str
    bundle: InventoryBundle
    target_option: Option
    source_refs: list[str]


class BusinessRankingEngine:
    """Rank business candidates without replacing policy evaluation or approvals."""

    BASELINE_SCORE = 0.24
    COMPONENT_WEIGHTS: Mapping[str, float] = {
        "policy_compliance": 0.2,
        "schedule_protection": 0.18,
        "cost_posture": 0.12,
        "comparable_readiness": 0.12,
        "justification_readiness": 0.12,
        "comfort_floor": 0.12,
        "exception_path_fit": 0.14,
    }

    def validate_profile(self, profile: BusinessTravelProfile) -> BusinessTravelProfile:
        if not isinstance(profile, BusinessTravelProfile):
            raise ValueError("profile must be a BusinessTravelProfile")
        return profile

    def validate_objectives(
        self, objectives: BusinessPlanningObjectives
    ) -> BusinessPlanningObjectives:
        if not isinstance(objectives, BusinessPlanningObjectives):
            raise ValueError("objectives must be a BusinessPlanningObjectives")
        return objectives

    def validate_constraint_set(
        self, constraint_set: PolicyConstraintSet | None
    ) -> PolicyConstraintSet | None:
        if constraint_set is not None and not isinstance(
            constraint_set, PolicyConstraintSet
        ):
            raise ValueError(
                "constraint_set must be a PolicyConstraintSet when provided"
            )
        return constraint_set

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
        profile: BusinessTravelProfile,
        objectives: BusinessPlanningObjectives,
        candidate_set: CandidateSet,
        *,
        constraint_set: PolicyConstraintSet | None = None,
        feasibility_outputs: (
            Mapping[str, FeasibilityAssessment] | Sequence[FeasibilityAssessment] | None
        ) = None,
        title: str = "Business candidate ranking",
    ) -> RankedResultSet:
        self.validate_profile(profile)
        self.validate_objectives(objectives)
        validated_set = self.validate_candidate_set(candidate_set)
        validated_constraint_set = self.validate_constraint_set(constraint_set)
        assessments = self.validate_feasibility_outputs(feasibility_outputs)
        candidates = [
            _RankableBusinessCandidate(
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
            constraint_set=validated_constraint_set,
        )

    def rank_bundles(
        self,
        profile: BusinessTravelProfile,
        objectives: BusinessPlanningObjectives,
        bundles: Sequence[InventoryBundle],
        *,
        trip_id: str,
        purpose: str = "final_selection",
        title: str = "Business bundle ranking",
        constraint_set: PolicyConstraintSet | None = None,
        feasibility_outputs: (
            Mapping[str, FeasibilityAssessment] | Sequence[FeasibilityAssessment] | None
        ) = None,
    ) -> RankedResultSet:
        self.validate_profile(profile)
        self.validate_objectives(objectives)
        validated_bundles = self.validate_bundles(bundles)
        validated_constraint_set = self.validate_constraint_set(constraint_set)
        assessments = self.validate_feasibility_outputs(feasibility_outputs)
        candidates = [
            _RankableBusinessCandidate(
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
            constraint_set=validated_constraint_set,
        )

    def _rank(
        self,
        profile: BusinessTravelProfile,
        objectives: BusinessPlanningObjectives,
        candidates: list[_RankableBusinessCandidate],
        *,
        trip_id: str,
        purpose: str,
        title: str,
        source_refs: list[str],
        assessments: dict[str, FeasibilityAssessment],
        constraint_set: PolicyConstraintSet | None,
    ) -> RankedResultSet:
        ranked_payloads: list[tuple[float, RankedResult]] = []
        for candidate in candidates:
            assessment = assessments.get(
                candidate.bundle.bundle_id
            ) or evaluate_bundle_feasibility(candidate.bundle)
            contributions = self._component_contributions(
                profile,
                objectives,
                candidate.bundle,
                assessment,
                constraint_set=constraint_set,
            )
            penalties, missing_data_penalties = self._penalties(
                objectives,
                candidate.bundle,
                assessment,
                constraint_set=constraint_set,
            )
            final_score = self.BASELINE_SCORE
            final_score += sum(item.weighted_impact for item in contributions)
            final_score -= sum(item.amount for item in penalties)
            final_score -= sum(item.amount for item in missing_data_penalties)
            final_score = _round(final_score)
            breakdown = ScoreBreakdown(
                baseline_score=self.BASELINE_SCORE,
                component_contributions=contributions,
                penalties=penalties,
                missing_data_penalties=missing_data_penalties,
                final_score=final_score,
                notes=[
                    "Business ranking remains policy-aware but not policy-authoritative.",
                    "Exception-path fit can outrank strict compliance only when objectives explicitly allow it.",
                ],
            )
            confidence = self._confidence_summary(
                profile,
                objectives,
                candidate.bundle,
                assessment,
                contributions,
                penalties + missing_data_penalties,
            )
            explanation_records = self._explanation_records(
                candidate,
                objectives,
                breakdown,
                confidence,
            )
            risks = self._risk_flags(candidate.bundle, assessment, objectives)
            ranked_payloads.append(
                (
                    final_score,
                    RankedResult(
                        result_id=f"ranked:{candidate.candidate_id}",
                        result_kind="item",
                        rank=1,
                        score=final_score,
                        target_option=candidate.target_option,
                        score_breakdown=breakdown,
                        confidence_summary=confidence,
                        explanation_records=explanation_records,
                        unresolved_risks=risks,
                        source_refs=_dedupe_strings(
                            source_refs + candidate.source_refs
                        ),
                        notes=[
                            "Business ranking is a planning recommendation, not a policy verdict."
                        ],
                    ),
                )
            )

        ordered_results = sorted(
            ranked_payloads,
            key=lambda item: (
                item[0],
                item[1].confidence_summary.overall_confidence or 0.0,
                item[1].target_option.option_id if item[1].target_option else "",
            ),
            reverse=True,
        )
        results = []
        for index, (_, result) in enumerate(ordered_results, start=1):
            result.rank = index
            results.append(result)
        return RankedResultSet(
            result_set_id=f"ranking:{trip_id}:business",
            trip_id=trip_id,
            purpose=purpose,
            scope="mixed",
            title=title,
            results=results,
            comparison_axes=self._comparison_axes(),
            explanation=[
                "Business ranking optimizes for compliance posture, schedule protection, and proposal readiness.",
                "The engine preserves explicit tradeoffs instead of collapsing planning into a cheapest-option sort.",
            ],
            source_refs=_dedupe_strings(source_refs),
        )

    def _component_contributions(
        self,
        profile: BusinessTravelProfile,
        objectives: BusinessPlanningObjectives,
        bundle: InventoryBundle,
        assessment: FeasibilityAssessment,
        *,
        constraint_set: PolicyConstraintSet | None,
    ) -> list[ScoreContribution]:
        compliance_signal, compliance_notes = self._policy_compliance_signal(
            objectives,
            bundle,
            constraint_set=constraint_set,
        )
        schedule_signal, schedule_notes = self._schedule_signal(
            profile, objectives, bundle, assessment
        )
        cost_signal, cost_notes = self._cost_signal(objectives, bundle)
        comparable_signal, comparable_notes = self._comparable_signal(
            objectives, bundle
        )
        justification_signal, justification_notes = self._justification_signal(
            objectives,
            bundle,
            constraint_set=constraint_set,
        )
        comfort_signal, comfort_notes = self._comfort_signal(
            profile, objectives, bundle
        )
        exception_signal, exception_notes = self._exception_path_signal(
            objectives, bundle
        )
        signals = [
            (
                "policy_compliance",
                "Policy compliance",
                compliance_signal,
                "Alignment with approved channels, approval posture, and policy-friendly inventory.",
                compliance_notes,
            ),
            (
                "schedule_protection",
                "Schedule protection",
                schedule_signal,
                "Ability to preserve business-critical arrival timing and low-friction movement.",
                schedule_notes,
            ),
            (
                "cost_posture",
                "Cost posture",
                cost_signal,
                "Fit with value and cost-control objectives once policy gates are considered.",
                cost_notes,
            ),
            (
                "comparable_readiness",
                "Comparable readiness",
                comparable_signal,
                "How well the bundle supports required comparable capture before escalation.",
                comparable_notes,
            ),
            (
                "justification_readiness",
                "Justification readiness",
                justification_signal,
                "Evidence and booking detail coverage for proposal packaging and approvals.",
                justification_notes,
            ),
            (
                "comfort_floor",
                "Comfort floor",
                comfort_signal,
                "Protection of workspace, arrival readiness, and business-access requirements.",
                comfort_notes,
            ),
            (
                "exception_path_fit",
                "Exception-path fit",
                exception_signal,
                "How well the bundle matches the configured compliant-first or policy-nearest posture.",
                exception_notes,
            ),
        ]
        contributions: list[ScoreContribution] = []
        for axis_key, label, signal, summary, notes in signals:
            weight = self.COMPONENT_WEIGHTS[axis_key]
            contributions.append(
                ScoreContribution(
                    contribution_id=f"{bundle.bundle_id}:{axis_key}",
                    label=label,
                    axis_key=axis_key,
                    direction="higher_better",
                    raw_value=_round(signal),
                    normalized_signal=_round(signal),
                    weighted_impact=_round(signal * weight),
                    summary=summary,
                    evidence_refs=list(bundle.provenance_summary.source_refs[:3]),
                    notes=notes,
                )
            )
        return contributions

    def _policy_compliance_signal(
        self,
        objectives: BusinessPlanningObjectives,
        bundle: InventoryBundle,
        *,
        constraint_set: PolicyConstraintSet | None,
    ) -> tuple[float, list[str]]:
        lodging_statuses = [
            _APPROVAL_SIGNALS[lodging.feasibility.business_approval_status]
            for lodging in bundle.lodging_options
        ]
        transport_statuses = [
            _APPROVAL_SIGNALS[transport.policy_summary.business_approval_status]
            for transport in bundle.transport_options
        ]
        required_channels = set(objectives.channel_strategy.required_channels)
        if constraint_set is not None:
            required_channels.update(constraint_set.required_booking_channels)
        channel_hits: list[float] = []
        for transport in bundle.transport_options:
            if transport.policy_summary.approved_booking_channel is True:
                channel_hits.append(1.0)
            elif (
                required_channels
                and transport.booking_terms.booking_channel in required_channels
            ):
                channel_hits.append(1.0)
            elif required_channels and any(
                channel in required_channels
                for channel in transport.booking_terms.approved_channels
            ):
                channel_hits.append(0.9)
            elif required_channels:
                channel_hits.append(0.25)
        policy_fit = [
            transport.fit_summary.policy_fit_signal
            for transport in bundle.transport_options
        ]
        policy_fit.extend(
            lodging.value_summary.policy_value_signal
            for lodging in bundle.lodging_options
        )
        signal = _average(
            [
                _average(lodging_statuses + transport_statuses, default=0.5),
                _average(channel_hits, default=1.0 if not required_channels else 0.35),
                _average(policy_fit, default=0.55),
            ],
            default=0.5,
        )
        notes = []
        if required_channels:
            notes.append("Required channels: " + ", ".join(sorted(required_channels)))
        notes.append(f"channel_mode={objectives.channel_strategy.channel_mode}")
        return signal, notes

    def _schedule_signal(
        self,
        profile: BusinessTravelProfile,
        objectives: BusinessPlanningObjectives,
        bundle: InventoryBundle,
        assessment: FeasibilityAssessment,
    ) -> tuple[float, list[str]]:
        transport_schedule = [
            transport.fit_summary.schedule_fit_signal
            for transport in bundle.transport_options
        ]
        protection = [
            transport.transfer_burden.schedule_protection_signal
            for transport in bundle.transport_options
        ]
        arrival_readiness = [
            lodging.location_summary.business_access_signal
            for lodging in bundle.lodging_options
        ]
        feasibility = 1.0 if assessment.recommended_for_ranking else 0.35
        friction = _clamp(1.0 - min(assessment.friction_penalty_total, 1.0))
        signal = _average(
            [
                _average(transport_schedule, default=0.5),
                _average(protection, default=0.5),
                _average(arrival_readiness, default=0.5),
                feasibility,
                friction,
            ]
        )
        if profile.trip_purpose.trip_criticality == "high":
            signal = _clamp(signal + 0.06 * _average(protection, default=0.5))
        notes = [
            f"protection_level={objectives.schedule_protection.protection_level}",
            f"trip_criticality={profile.trip_purpose.trip_criticality}",
        ]
        return signal, notes

    def _cost_signal(
        self, objectives: BusinessPlanningObjectives, bundle: InventoryBundle
    ) -> tuple[float, list[str]]:
        value_signal = _average(
            [
                bundle.quality_value_fit.value_signal,
                bundle.quality_value_fit.fit_signal,
            ],
            default=0.55,
        )
        quality_signal = _average(
            [bundle.quality_value_fit.quality_signal], default=0.6
        )
        posture = objectives.cost_control_posture.posture
        if posture == "cost_first":
            signal = _average(
                [value_signal, bundle.quality_value_fit.value_signal], default=0.55
            )
        elif posture == "policy_first":
            signal = _average([value_signal, quality_signal], default=0.55)
        else:
            signal = _average([value_signal, quality_signal], default=0.58)
        return signal, [f"posture={posture}"]

    def _comparable_signal(
        self, objectives: BusinessPlanningObjectives, bundle: InventoryBundle
    ) -> tuple[float, list[str]]:
        required_total = sum(
            objectives.comparable_requirements.required_categories.values()
        )
        comparable_refs = 0
        comparable_refs += sum(
            len(transport.booking_terms.comparable_reference_ids)
            for transport in bundle.transport_options
        )
        comparable_refs += sum(
            len(transport.policy_summary.comparable_reference_ids)
            for transport in bundle.transport_options
        )
        searchable_text = _searchable_bundle_text(bundle)
        if "comparable" in searchable_text:
            comparable_refs += 1
        if required_total <= 0:
            return 0.82, ["No explicit comparable requirements."]
        signal = _clamp(comparable_refs / required_total)
        return signal, [
            f"required_comparables={required_total}",
            f"captured_refs={comparable_refs}",
        ]

    def _justification_signal(
        self,
        objectives: BusinessPlanningObjectives,
        bundle: InventoryBundle,
        *,
        constraint_set: PolicyConstraintSet | None,
    ) -> tuple[float, list[str]]:
        required_fields = list(objectives.justification_readiness.required_fields)
        if constraint_set is not None:
            required_fields.extend(constraint_set.documentation_rules)
        evidence_count = len(bundle.provenance_summary.source_refs)
        evidence_count += len(bundle.provenance_summary.booking_links)
        evidence_count += len(bundle.explanation.evidence)
        evidence_count += sum(
            len(item.policy_summary.policy_notes) for item in bundle.transport_options
        )
        expected = max(
            1,
            len(required_fields)
            + len(objectives.justification_readiness.required_receipt_categories),
        )
        signal = _clamp(evidence_count / expected)
        notes = [
            f"required_fields={len(required_fields)}",
            f"booking_links={len(bundle.provenance_summary.booking_links)}",
        ]
        if objectives.justification_readiness.maintain_exception_packet:
            notes.append("exception_packet_required=true")
        return signal, notes

    def _comfort_signal(
        self,
        profile: BusinessTravelProfile,
        objectives: BusinessPlanningObjectives,
        bundle: InventoryBundle,
    ) -> tuple[float, list[str]]:
        lodging_scores = [
            _average(
                [
                    lodging.room_summary.workspace_signal,
                    lodging.room_summary.comfort_signal,
                    lodging.location_summary.business_access_signal,
                ],
                default=0.55,
            )
            for lodging in bundle.lodging_options
        ]
        transport_scores = [
            _average(
                [
                    transport.experience_summary.workability_signal,
                    transport.experience_summary.comfort_signal,
                ],
                default=0.5,
            )
            for transport in bundle.transport_options
        ]
        signal = _average(
            [
                _average(lodging_scores, default=0.55),
                _average(transport_scores, default=0.5),
            ],
            default=0.55,
        )
        if objectives.comfort_floor_protection.preserve_arrival_readiness:
            signal = _clamp(signal + 0.05 * _average(lodging_scores, default=0.5))
        notes = [
            "required_categories="
            + ",".join(
                objectives.comfort_floor_protection.required_categories or ["none"]
            ),
            f"mobility_needs={len(profile.traveler_context.mobility_or_access_needs)}",
        ]
        return signal, notes

    def _exception_path_signal(
        self, objectives: BusinessPlanningObjectives, bundle: InventoryBundle
    ) -> tuple[float, list[str]]:
        statuses = [
            lodging.feasibility.business_approval_status
            for lodging in bundle.lodging_options
        ]
        statuses.extend(
            transport.policy_summary.business_approval_status
            for transport in bundle.transport_options
        )
        status_values = [_APPROVAL_SIGNALS[status] for status in statuses]
        approval_flags = [
            0.0 if transport.policy_summary.approval_required else 1.0
            for transport in bundle.transport_options
        ]
        posture = objectives.exception_path_posture.posture
        baseline = _average(status_values, default=0.45)
        if posture == "compliant_first":
            signal = _average(
                [baseline, _average(approval_flags, default=1.0)], default=0.5
            )
        elif posture == "policy_nearest":
            if any(status == "restricted" for status in statuses):
                signal = _average(
                    [
                        0.88,
                        _average(approval_flags, default=0.7),
                    ],
                    default=0.78,
                )
            else:
                signal = _average(
                    [
                        0.52,
                        _average(approval_flags, default=0.9),
                    ],
                    default=0.6,
                )
        else:
            signal = _average([max(0.4, baseline), 0.75], default=0.55)
        return signal, [
            f"posture={posture}",
            f"fallback_mode={objectives.exception_path_posture.fallback_mode}",
        ]

    def _penalties(
        self,
        objectives: BusinessPlanningObjectives,
        bundle: InventoryBundle,
        assessment: FeasibilityAssessment,
        *,
        constraint_set: PolicyConstraintSet | None,
    ) -> tuple[list[ScoreAdjustment], list[ScoreAdjustment]]:
        penalties: list[ScoreAdjustment] = []
        missing: list[ScoreAdjustment] = []
        if not assessment.recommended_for_ranking:
            penalties.append(
                ScoreAdjustment(
                    adjustment_id=f"penalty:{bundle.bundle_id}:feasibility",
                    label="Feasibility drag",
                    kind="penalty",
                    amount=0.14,
                    reason_code="feasibility_not_recommended",
                    summary="The bundle is not currently recommended for ranking because route or timing issues remain unresolved.",
                    affected_factor_keys=["schedule_protection", "exception_path_fit"],
                )
            )
        if any(
            lodging.feasibility.business_approval_status == "disallowed"
            for lodging in bundle.lodging_options
        ) or any(
            transport.policy_summary.business_approval_status == "disallowed"
            for transport in bundle.transport_options
        ):
            penalties.append(
                ScoreAdjustment(
                    adjustment_id=f"penalty:{bundle.bundle_id}:disallowed",
                    label="Disallowed inventory",
                    kind="penalty",
                    amount=0.16,
                    reason_code="disallowed_inventory",
                    summary="At least one bundled option is explicitly disallowed in business approval metadata.",
                    affected_factor_keys=["policy_compliance", "exception_path_fit"],
                )
            )
        required_total = sum(
            objectives.comparable_requirements.required_categories.values()
        )
        comparable_refs = sum(
            len(transport.booking_terms.comparable_reference_ids)
            for transport in bundle.transport_options
        ) + sum(
            len(transport.policy_summary.comparable_reference_ids)
            for transport in bundle.transport_options
        )
        if (
            objectives.comparable_requirements.capture_required
            and required_total > comparable_refs
        ):
            missing.append(
                ScoreAdjustment(
                    adjustment_id=f"missing:{bundle.bundle_id}:comparables",
                    label="Comparable capture gap",
                    kind="missing_data",
                    amount=0.08,
                    reason_code="comparables_missing",
                    summary="Comparable capture requirements exceed the references carried by this bundle.",
                    affected_factor_keys=["comparable_readiness"],
                )
            )
        if (
            objectives.justification_readiness.booking_link_retention_required
            and not bundle.provenance_summary.booking_links
        ):
            missing.append(
                ScoreAdjustment(
                    adjustment_id=f"missing:{bundle.bundle_id}:booking-links",
                    label="Booking links missing",
                    kind="missing_data",
                    amount=0.05,
                    reason_code="booking_links_missing",
                    summary="Business proposal packaging expects booking links, but none were retained on this bundle.",
                    affected_factor_keys=["justification_readiness"],
                )
            )
        if (
            constraint_set is not None
            and constraint_set.documentation_rules
            and not bundle.provenance_summary.source_refs
        ):
            missing.append(
                ScoreAdjustment(
                    adjustment_id=f"missing:{bundle.bundle_id}:documentation",
                    label="Documentation coverage gap",
                    kind="missing_data",
                    amount=0.04,
                    reason_code="documentation_gap",
                    summary="Constraint-set documentation rules exist, but the bundle carries no provenance references.",
                    affected_factor_keys=["justification_readiness"],
                )
            )
        return penalties, missing

    def _confidence_summary(
        self,
        profile: BusinessTravelProfile,
        objectives: BusinessPlanningObjectives,
        bundle: InventoryBundle,
        assessment: FeasibilityAssessment,
        contributions: list[ScoreContribution],
        penalties: list[ScoreAdjustment],
    ) -> ScoreConfidenceSummary:
        missing_fields = list(assessment.missing_data_fields)
        if (
            objectives.justification_readiness.booking_link_retention_required
            and not bundle.provenance_summary.booking_links
        ):
            missing_fields.append("bundle:booking_links")
        input_coverage = _clamp(1.0 - 0.1 * len(missing_fields))
        policy_source_count = sum(
            1
            for lodging in bundle.lodging_options
            for source_ref in lodging.source_refs
            if source_ref.source_category == "managed_travel_policy"
        )
        policy_source_count += sum(
            1
            for transport in bundle.transport_options
            for source_ref in transport.source_refs
            if source_ref.source_category == "managed_travel_policy"
        )
        data_freshness = 0.85 if policy_source_count else 0.7
        scoring_stability = _clamp(1.0 - sum(item.amount for item in penalties))
        overall = _average(
            [
                assessment.confidence_signal,
                input_coverage,
                data_freshness,
                scoring_stability,
            ],
            default=0.72,
        )
        low_confidence_flags = []
        if (
            profile.approval_targets.needs_exception_preclearance
            and not bundle.provenance_summary.booking_links
        ):
            low_confidence_flags.append("exception_packet_sparse")
        if any(
            item.normalized_signal is not None and item.normalized_signal < 0.45
            for item in contributions
        ):
            low_confidence_flags.append("low_business_fit_component")
        return ScoreConfidenceSummary(
            overall_confidence=_round(overall),
            input_coverage=_round(input_coverage),
            data_freshness=_round(data_freshness),
            scoring_stability=_round(scoring_stability),
            low_confidence_flags=_dedupe_strings(low_confidence_flags),
            missing_data_fields=_dedupe_strings(missing_fields),
            notes=[
                f"policy_source_count={policy_source_count}",
                f"penalty_count={len(penalties)}",
            ],
        )

    def _explanation_records(
        self,
        candidate: _RankableBusinessCandidate,
        objectives: BusinessPlanningObjectives,
        breakdown: ScoreBreakdown,
        confidence: ScoreConfidenceSummary,
    ) -> list[ExplanationRecord]:
        top_positive = max(
            breakdown.component_contributions,
            key=lambda item: item.weighted_impact,
        )
        top_negative = min(
            breakdown.component_contributions,
            key=lambda item: item.weighted_impact,
        )
        records = [
            ExplanationRecord(
                explanation_id=f"{candidate.candidate_id}:summary",
                record_type="summary",
                target_kind="item",
                target_id=candidate.target_option.option_id,
                headline=f"{candidate.bundle.title} is ranked through explicit business-planning signals.",
                summary=(
                    f"Top positive driver: {top_positive.label.lower()}; "
                    f"largest drag: {top_negative.label.lower()}."
                ),
                factor_keys=[top_positive.axis_key, top_negative.axis_key],
                machine_context={
                    "compliant_first": str(
                        objectives.compliant_first_path.active
                    ).lower(),
                    "policy_nearest_fallback": str(
                        objectives.policy_nearest_fallback.active
                    ).lower(),
                },
                human_summary=_dedupe_strings(
                    [
                        candidate.bundle.summary or candidate.bundle.title,
                        top_positive.summary,
                        top_negative.summary,
                    ]
                ),
                source_refs=candidate.source_refs[:3],
            )
        ]
        if confidence.missing_data_fields:
            records.append(
                ExplanationRecord(
                    explanation_id=f"{candidate.candidate_id}:confidence",
                    record_type="confidence",
                    target_kind="item",
                    target_id=candidate.target_option.option_id,
                    headline="Confidence remains bounded by proposal-readiness coverage.",
                    summary="Missing data and policy-documentation gaps stay visible in the ranking output.",
                    factor_keys=["justification_readiness", "comparable_readiness"],
                    machine_context={
                        "overall_confidence": str(confidence.overall_confidence or 0.0)
                    },
                    human_summary=[
                        "Missing data fields: "
                        + ", ".join(confidence.missing_data_fields[:3])
                    ],
                    source_refs=candidate.source_refs[:2],
                )
            )
        return records

    def _risk_flags(
        self,
        bundle: InventoryBundle,
        assessment: FeasibilityAssessment,
        objectives: BusinessPlanningObjectives,
    ) -> list[RiskFlag]:
        risks: list[RiskFlag] = []
        for blocking_reason in assessment.blocking_reasons:
            risks.append(
                RiskFlag(
                    risk_id=f"risk:{assessment.bundle_id}:{blocking_reason}",
                    code=blocking_reason,
                    severity=(
                        "critical"
                        if not assessment.recommended_for_ranking
                        else "warning"
                    ),
                    summary=f"Feasibility issue remains unresolved: {blocking_reason}.",
                    blocking=not assessment.recommended_for_ranking,
                )
            )
        for transport in bundle.transport_options:
            if transport.policy_summary.approval_required:
                risks.append(
                    RiskFlag(
                        risk_id=f"risk:{transport.option_id}:approval",
                        code="approval_required",
                        severity="warning",
                        summary=f"{transport.name} still requires manual approval.",
                    )
                )
        if (
            objectives.justification_readiness.maintain_exception_packet
            and not bundle.provenance_summary.booking_links
        ):
            risks.append(
                RiskFlag(
                    risk_id=f"risk:{bundle.bundle_id}:exception-packet",
                    code="exception_packet_gap",
                    severity="warning",
                    summary="Exception-ready planning expects retained booking links for the proposal packet.",
                )
            )
        return risks

    def _bundle_to_option(self, bundle: InventoryBundle) -> Option:
        total = self._estimate_bundle_total(bundle)
        return Option(
            option_id=bundle.bundle_id,
            kind="mixed",
            label=bundle.title,
            summary=bundle.summary,
            fit_signals={
                key: value
                for key, value in {
                    "quality": bundle.quality_value_fit.quality_signal,
                    "value": bundle.quality_value_fit.value_signal,
                    "fit": bundle.quality_value_fit.fit_signal,
                }.items()
                if value is not None
            },
            cost_summary=OptionCostSummary(total=total),
            quality_summary=OptionQualitySummary(
                quality_signal=bundle.quality_value_fit.quality_signal,
                value_signal=bundle.quality_value_fit.value_signal,
                fit_signal=bundle.quality_value_fit.fit_signal,
            ),
            drawbacks=list(bundle.explanation.tradeoffs)
            + list(bundle.feasibility.blocking_reasons),
            booking_links=list(bundle.provenance_summary.booking_links),
            source_refs=list(bundle.provenance_summary.source_refs),
            supporting_place_ids=list(bundle.destination_ids),
            explanation=list(bundle.explanation.strengths)
            + list(bundle.explanation.evidence),
        )

    def _estimate_bundle_total(self, bundle: InventoryBundle) -> MoneyRange | None:
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
        if not seen:
            return None
        return MoneyRange(currency=currency or "USD", typical_amount=round(total, 2))

    def _comparison_axes(self) -> list[ComparisonAxis]:
        return [
            ComparisonAxis(
                key="business_policy_fit",
                label="Business policy fit",
                direction="higher_better",
                notes="Approved channels, business approval posture, and policy-aware fit remain explicit.",
            ),
            ComparisonAxis(
                key="schedule_protection",
                label="Schedule protection",
                direction="higher_better",
                notes="Mission-critical timing protection and low-friction arrival remain visible.",
            ),
            ComparisonAxis(
                key="proposal_readiness",
                label="Proposal readiness",
                direction="higher_better",
                notes="Comparable capture and justification evidence stay attached to the ranking output.",
            ),
        ]
