"""Deterministic first-pass route assembly over ranked itinerary candidates."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from trip_planner.business import BusinessPlanningObjectives
from trip_planner.candidates import CandidateSet
from trip_planner.contracts import ItineraryObjectives, MoneyRange
from trip_planner.itinerary.feasibility import (
    FeasibilityAssessment,
    evaluate_bundle_feasibility,
)
from trip_planner.options import InventoryBundle
from trip_planner.ranking import RankedResult, RankedResultSet, RiskFlag

from .scenarios import (
    ItineraryScenario,
    ScenarioSearchResult,
    ScenarioSummary,
    ScenarioTradeoff,
)


def _bundle_total(bundle: InventoryBundle) -> MoneyRange | None:
    currency: str | None = None
    total = 0.0
    seen = False

    for lodging_option in bundle.lodging_options:
        amount = lodging_option.cost_summary.total or lodging_option.cost_summary.nightly
        if amount is None or amount.typical_amount is None:
            continue
        currency = currency or amount.currency
        if amount.currency != currency:
            return None
        total += amount.typical_amount
        seen = True

    for transport_option in bundle.transport_options:
        amount = transport_option.cost_summary.total
        if amount is None or amount.typical_amount is None:
            continue
        currency = currency or amount.currency
        if amount.currency != currency:
            return None
        total += amount.typical_amount
        seen = True

    for activity_option in bundle.activity_options:
        amount = activity_option.cost_summary.total or activity_option.cost_summary.per_person
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


def _bundle_map(
    candidate_set: CandidateSet | None,
    bundles: Sequence[InventoryBundle] | None,
) -> dict[str, InventoryBundle]:
    mapped: dict[str, InventoryBundle] = {}
    if candidate_set is not None:
        mapped.update({seed.bundle.bundle_id: seed.bundle for seed in candidate_set.seeds})
    if bundles is not None:
        mapped.update({bundle.bundle_id: bundle for bundle in bundles})
    if not mapped:
        raise ValueError("candidate_set or bundles must provide at least one InventoryBundle")
    return mapped


def _normalize_feasibility_outputs(
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
            "feasibility_outputs must be a mapping, sequence of FeasibilityAssessment values, or None"
        )
    if any(not isinstance(item, FeasibilityAssessment) for item in values.values()):
        raise ValueError("feasibility_outputs must contain FeasibilityAssessment instances")
    return values


def _objective_mode(objectives: object | None) -> str:
    if isinstance(objectives, BusinessPlanningObjectives):
        return "business"
    if isinstance(objectives, ItineraryObjectives):
        return "leisure"
    return "generic"


def _objective_refs(objectives: object | None) -> list[str]:
    if objectives is None:
        return []
    objective_id = getattr(objectives, "objective_id", None)
    trip_id = getattr(objectives, "trip_id", None)
    refs: list[str] = []
    if isinstance(objective_id, str) and objective_id:
        refs.append(objective_id)
    if isinstance(trip_id, str) and trip_id:
        refs.append(trip_id)
    return refs


def _route_sequence(result: RankedResult, bundle: InventoryBundle) -> list[str]:
    if result.route_sequence:
        return list(result.route_sequence)
    if result.supporting_destination_ids:
        return list(result.supporting_destination_ids)
    return bundle.destination_ids


def _tradeoff_from_risk_flag(risk: RiskFlag) -> ScenarioTradeoff:
    return ScenarioTradeoff(
        tradeoff_id=risk.risk_id,
        code=risk.code,
        summary=risk.summary,
        severity=risk.severity,
        blocking=risk.blocking,
        notes=list(risk.notes),
    )


def _build_tradeoffs(
    result: RankedResult,
    assessment: FeasibilityAssessment,
) -> list[ScenarioTradeoff]:
    tradeoffs = [_tradeoff_from_risk_flag(risk) for risk in result.unresolved_risks]

    for index, reason in enumerate(assessment.blocking_reasons, start=1):
        tradeoffs.append(
            ScenarioTradeoff(
                tradeoff_id=f"blocking:{assessment.bundle_id}:{index}",
                code="blocking_reason",
                summary=reason,
                severity="critical",
                blocking=True,
                related_ids=[assessment.bundle_id],
            )
        )

    for conflict in assessment.timing_conflicts:
        tradeoffs.append(
            ScenarioTradeoff(
                tradeoff_id=conflict.conflict_id,
                code=conflict.code,
                summary=conflict.summary,
                severity=conflict.severity,
                blocking=conflict.blocking,
                related_ids=list(conflict.related_option_ids),
                notes=list(conflict.notes),
            )
        )

    for warning in assessment.route_warnings:
        tradeoffs.append(
            ScenarioTradeoff(
                tradeoff_id=warning.warning_id,
                code=warning.code,
                summary=warning.summary,
                severity=warning.severity,
                related_ids=list(warning.related_option_ids) + list(warning.destination_ids),
                notes=list(warning.notes),
            )
        )

    if not assessment.recommended_for_ranking and not any(
        item.code == "ranking_not_recommended" for item in tradeoffs
    ):
        tradeoffs.append(
            ScenarioTradeoff(
                tradeoff_id=f"ranking:{assessment.bundle_id}:not-recommended",
                code="ranking_not_recommended",
                summary="Scenario is retained as a fallback even though it is not recommended for ranking.",
                severity="warning",
                related_ids=[assessment.bundle_id],
            )
        )

    return tradeoffs


def _scenario_kind(
    *,
    rank: int,
    objective_mode: str,
    assessment: FeasibilityAssessment,
    tradeoffs: Sequence[ScenarioTradeoff],
) -> str:
    has_blocking_tradeoff = any(item.blocking for item in tradeoffs)

    if rank == 1 and assessment.recommended_for_ranking and not has_blocking_tradeoff:
        return "primary"

    if objective_mode == "business" and (
        not assessment.recommended_for_ranking or has_blocking_tradeoff
    ):
        return "fallback"

    if not assessment.feasible or has_blocking_tradeoff:
        return "fallback"

    return "alternative"


def assemble_itinerary_scenarios(
    ranked_results: RankedResultSet,
    *,
    candidate_set: CandidateSet | None = None,
    bundles: Sequence[InventoryBundle] | None = None,
    objectives: object | None = None,
    feasibility_outputs: (
        Mapping[str, FeasibilityAssessment] | Sequence[FeasibilityAssessment] | None
    ) = None,
    max_scenarios: int = 3,
    title: str | None = None,
) -> ScenarioSearchResult:
    """Assemble explainable itinerary scenarios from ranked bundle candidates."""

    if max_scenarios <= 0:
        raise ValueError("max_scenarios must be positive")

    bundle_map = _bundle_map(candidate_set, bundles)
    assessments = _normalize_feasibility_outputs(feasibility_outputs)
    objective_mode = _objective_mode(objectives)
    objective_refs = _objective_refs(objectives)

    scenarios: list[ItineraryScenario] = []
    for result in sorted(ranked_results.results, key=lambda item: item.rank)[:max_scenarios]:
        bundle_id = result.target_bundle_id
        if not bundle_id and result.target_option is not None:
            bundle_id = result.target_option.option_id
        if not bundle_id:
            raise ValueError(
                "route assembly requires ranked results with target_bundle_id or target_option.option_id"
            )
        bundle = bundle_map.get(bundle_id)
        if bundle is None:
            raise ValueError(f"missing bundle for ranked result target {bundle_id!r}")

        assessment = assessments.get(bundle.bundle_id) or evaluate_bundle_feasibility(bundle)
        tradeoffs = _build_tradeoffs(result, assessment)
        scenario_kind = _scenario_kind(
            rank=result.rank,
            objective_mode=objective_mode,
            assessment=assessment,
            tradeoffs=tradeoffs,
        )
        route_sequence = _route_sequence(result, bundle)
        coherence_passed = (
            assessment.feasible
            and bundle.feasibility.internally_consistent
            and not any(item.blocking for item in tradeoffs)
        )

        summary_notes = list(bundle.explanation.tradeoffs)
        if assessment.schedule_protection_required:
            summary_notes.append("schedule_protection_required")
        if assessment.missing_data_fields:
            summary_notes.append(
                f"missing_data:{','.join(sorted(set(assessment.missing_data_fields)))}"
            )

        scenario_summary = ScenarioSummary(
            headline=bundle.explanation.headline or result.explanation_records[0].headline,
            scenario_kind=scenario_kind,
            feasible=assessment.feasible,
            recommended_for_selection=assessment.recommended_for_ranking,
            coherence_passed=coherence_passed,
            estimated_total=_bundle_total(bundle),
            total_travel_minutes=assessment.total_travel_minutes,
            total_transfer_count=assessment.total_transfer_count,
            route_sequence=route_sequence,
            notes=summary_notes,
        )

        scenarios.append(
            ItineraryScenario(
                scenario_id=f"scenario:{ranked_results.trip_id}:{result.rank}",
                title=bundle.title,
                rank=result.rank,
                bundle_id=bundle.bundle_id,
                source_result_id=result.result_id,
                score=result.score,
                scenario_summary=scenario_summary,
                supporting_option_ids=(
                    list(result.supporting_option_ids)
                    if result.supporting_option_ids
                    else bundle.option_ids
                ),
                objective_refs=objective_refs,
                explanation_records=list(result.explanation_records),
                unresolved_tradeoffs=tradeoffs,
                notes=list(bundle.notes) + list(result.notes),
            )
        )

    if not scenarios:
        raise ValueError("ranked_results must contain at least one scenario-ready result")

    explanation = [
        f"objective_mode:{objective_mode}",
        f"scenario_count:{len(scenarios)}",
        f"assembled_from:{ranked_results.result_set_id}",
    ]
    if objective_mode == "business":
        explanation.append(
            "Business scenario assembly preserves a compliant-first primary path and explicit fallback routes."
        )
    elif objective_mode == "leisure":
        explanation.append(
            "Leisure scenario assembly keeps multiple route alternatives instead of collapsing to one opaque plan."
        )
    else:
        explanation.append(
            "Scenario assembly preserves ranking explanations and feasibility tradeoffs."
        )

    search_title = title or f"{objective_mode.title()} itinerary scenarios"
    source_refs = list(dict.fromkeys([*ranked_results.source_refs, ranked_results.result_set_id]))

    return ScenarioSearchResult(
        search_id=f"scenario-search:{ranked_results.trip_id}:{objective_mode}",
        trip_id=ranked_results.trip_id,
        purpose=ranked_results.purpose,
        title=search_title,
        source_result_set_id=ranked_results.result_set_id,
        scenarios=scenarios,
        explanation=explanation,
        source_refs=source_refs,
    )
