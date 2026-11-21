"""App-specific adapter for trip-planner.

This is the ONLY app-specific piece the shared ``baseline_kit`` needs: a way to
turn an input (transport, lodging, or ranking fixture) into a flat dict of named
scalar metrics and runtime-observed reads. Everything else -- directional checks,
invariants, golden masters, the coverage manifest -- is generic and lives in
``baseline_kit``.

Deterministic compute surfaces exercised here (no DB, no network, no LLM):
  * ``TransportOption.from_dict`` + ``SourceQualityScorer``
  * ``LodgingOption.from_dict`` + ``SourceQualityScorer``
  * ``RankedResultSet.from_dict`` + ``LeisureRankingEngine`` / ``BusinessRankingEngine``
"""

from __future__ import annotations

import copy
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "options" / "transport"

# The metric dimensions this adapter exposes (the kit's "input parameter" space
# for coverage purposes). Keep this list aligned with the source-quality and
# ranking-adjacent symbols asserted in the coverage manifest.
METRIC_KEYS = [
    "anchor_alignment",
    "quality_floor_fit",
    "discovery_fit",
    "freshness_confidence",
    "commerciality",
    "fit_signal",
    "value_signal",
    "quality_signal",
    "input_coverage",
    "scoring_stability",
    "schedule_fit_signal",
    "friction_fit_signal",
    "policy_fit_signal",
    "overall_signal",
]

_METRIC_KEY_SET = frozenset(METRIC_KEYS)
_SIGNAL_KEYS = [k for k in METRIC_KEYS if k.endswith("_signal")]

_LODGING_SUPPORT_FIXTURES: dict[str, str] = {
    "lodg-kyoto-central": "tests/fixtures/options/lodging/central_urban_hotel.json",
    "lodg-kyoto-central-hotel": "tests/fixtures/options/lodging/central_urban_hotel.json",
    "lodg-conference-core": "tests/fixtures/options/lodging/conference_hotel.json",
    "lodg-chicago-lakeshore-conference": "tests/fixtures/options/lodging/conference_hotel.json",
    "lodg-kyoto-machiya-loft": "tests/fixtures/options/lodging/vacation_rental.json",
    "lodg-kyoto-hillside-retreat": "tests/fixtures/options/lodging/quiet_outer_area_hotel.json",
}
_ACTIVITY_SUPPORT_FIXTURES: dict[str, str] = {
    "activity-museum-pass": "tests/fixtures/options/activities/major_museum.json",
    "activity-major-museum": "tests/fixtures/options/activities/major_museum.json",
}
_TRANSPORT_SUPPORT_FIXTURES: dict[str, str] = {
    "transport-ord-direct": "tests/fixtures/options/transport/coastal_flight.json",
    "transport-flight-coastal-hop": "tests/fixtures/options/transport/coastal_flight.json",
}


@dataclass(frozen=True, slots=True)
class FixtureEvaluation:
    model_kind: str
    metrics: dict[str, float]
    observed_reads: frozenset[str]


def _fixture_path(fixture_name: str) -> Path:
    path = Path(fixture_name)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "tests":
        return REPO_ROOT / path
    return FIXTURES_DIR / fixture_name


def _load_payload(fixture_name: str) -> dict[str, Any]:
    payload = json.loads(_fixture_path(fixture_name).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Baseline fixture must be a JSON object: {fixture_name}")
    return payload


def _classify_payload(payload: dict[str, Any]) -> str:
    if "result_set_id" in payload or "results" in payload:
        return "ranking"
    if "transport_kind" in payload or "segments" in payload:
        return "transport"
    if "room_summary" in payload or "location_summary" in payload:
        return "lodging"
    raise ValueError("Unsupported baseline fixture payload")


def _model_class_for_kind(model_kind: str) -> Any:
    if model_kind == "transport":
        from trip_planner.options import TransportOption

        return TransportOption
    if model_kind == "lodging":
        from trip_planner.options import LodgingOption

        return LodgingOption
    if model_kind == "ranking":
        from trip_planner.ranking import RankedResultSet

        return RankedResultSet
    raise ValueError(f"Unknown model kind: {model_kind}")


def load_option(fixture_name: str):
    from trip_planner.options import TransportOption

    payload = _load_payload(fixture_name)
    return TransportOption.from_dict(payload)


def load_model(fixture_name: str):
    payload = _load_payload(fixture_name)
    model_cls = _model_class_for_kind(_classify_payload(payload))
    return model_cls.from_dict(payload)


def _amount(money: Any) -> float:
    return (
        float(getattr(money, "typical_amount", float("nan"))) if money is not None else float("nan")
    )


def _default_legacy_metrics() -> dict[str, float]:
    return {
        "cost_total": float("nan"),
        "cost_base_fare": float("nan"),
        "cost_taxes_and_fees": float("nan"),
        "transfer_count": 0.0,
        "minimum_connection_minutes": 0.0,
        "self_navigation_burden_signal": 0.0,
        "baggage_complexity_signal": 0.0,
        "schedule_protection_signal": 0.0,
        "connection_risk_signal": 0.0,
    }


def _evaluate_source_refs(
    source_refs: list[Any],
    *,
    intended_option_kind: str | None,
    raw_metrics: dict[str, float],
    observed: set[str],
) -> None:
    if not source_refs:
        return

    from trip_planner.sources import SourceQualityScorer, summarize_sources
    from trip_planner.sources import schema as source_schema

    option_kind = (
        intended_option_kind if intended_option_kind in source_schema.SOURCE_OPTION_KINDS else None
    )
    summary = summarize_sources(
        source_refs,
        subject_kind="option",
        intended_option_kind=option_kind,
    )

    if summary.per_source_scores and any(
        ref.trust_snapshot is not None and ref.trust_snapshot.freshness_confidence is not None
        for ref in source_refs
    ):
        raw_metrics["freshness_confidence"] = float(summary.per_source_scores[0].freshness_score)
        observed.add("freshness_confidence")

    if any(
        ref.trust_snapshot is not None and ref.trust_snapshot.commerciality is not None
        for ref in source_refs
    ):
        commercial_summary = SourceQualityScorer().summarize(
            source_refs,
            subject_kind="option",
            intended_option_kind=option_kind,
            commerciality_preference=1.0,
        )
        if commercial_summary.per_source_scores:
            raw_metrics["commerciality"] = float(
                commercial_summary.per_source_scores[0].provenance_strength
            )
            observed.add("commerciality")

    for attr_name in ("quality_signal", "value_signal", "fit_signal"):
        for ref in source_refs:
            qvf = ref.quality_value_fit
            val = getattr(qvf, attr_name, None) if qvf is not None else None
            if val is not None:
                raw_metrics.setdefault(attr_name, float(val))
                observed.add(attr_name)
                break


def _evaluate_transport(
    payload: dict[str, Any],
) -> tuple[dict[str, float], dict[str, float], set[str]]:
    from trip_planner.options import TransportOption

    option = TransportOption.from_dict(payload)
    c, f, t = option.cost_summary, option.fit_summary, option.transfer_burden
    legacy_metrics = {
        "cost_total": _amount(c.total),
        "cost_base_fare": _amount(c.base_fare),
        "cost_taxes_and_fees": _amount(c.taxes_and_fees),
        "transfer_count": float(t.transfer_count),
        "minimum_connection_minutes": float(t.minimum_connection_minutes or 0.0),
        "self_navigation_burden_signal": float(t.self_navigation_burden_signal or 0.0),
        "baggage_complexity_signal": float(t.baggage_complexity_signal or 0.0),
        "schedule_protection_signal": float(t.schedule_protection_signal or 0.0),
        "connection_risk_signal": float(t.connection_risk_signal or 0.0),
    }
    raw_metrics: dict[str, float] = {}
    observed: set[str] = set()
    for key in (
        "schedule_fit_signal",
        "friction_fit_signal",
        "experiential_fit_signal",
        "policy_fit_signal",
        "overall_signal",
    ):
        val = getattr(f, key)
        if val is not None:
            raw_metrics[key] = float(val)
            if key in _METRIC_KEY_SET:
                observed.add(key)

    _evaluate_source_refs(
        option.source_refs,
        intended_option_kind=option.transport_kind,
        raw_metrics=raw_metrics,
        observed=observed,
    )
    return legacy_metrics, raw_metrics, observed


def _evaluate_lodging(
    payload: dict[str, Any],
) -> tuple[dict[str, float], dict[str, float], set[str]]:
    from trip_planner.options import LodgingOption

    option = LodgingOption.from_dict(payload)
    legacy_metrics = _default_legacy_metrics()
    legacy_metrics["cost_total"] = _amount(option.cost_summary.total)
    legacy_metrics["cost_taxes_and_fees"] = _amount(option.cost_summary.taxes_and_fees)

    raw_metrics: dict[str, float] = {}
    observed: set[str] = set()
    if option.quality_summary.overall_signal is not None:
        raw_metrics["quality_signal"] = float(option.quality_summary.overall_signal)
        observed.add("quality_signal")
    if option.value_summary.overall_signal is not None:
        raw_metrics["value_signal"] = float(option.value_summary.overall_signal)
        observed.add("value_signal")
    if option.fit_summary.overall_signal is not None:
        fit_val = float(option.fit_summary.overall_signal)
        raw_metrics["fit_signal"] = fit_val
        raw_metrics["overall_signal"] = fit_val
        observed.update(("fit_signal", "overall_signal"))

    _evaluate_source_refs(
        option.source_refs,
        intended_option_kind="lodging",
        raw_metrics=raw_metrics,
        observed=observed,
    )
    return legacy_metrics, raw_metrics, observed


def _build_supporting_bundle(first: Any) -> Any | None:
    from trip_planner.options import (
        ActivityOption,
        BundleCompositionSummary,
        BundleExplanation,
        BundleProvenanceSummary,
        BundleQualityValueFitSummary,
        Destination,
        InventoryBundle,
        LodgingOption,
        TransportOption,
    )

    lodging_paths = [
        _LODGING_SUPPORT_FIXTURES[oid]
        for oid in first.supporting_option_ids
        if oid in _LODGING_SUPPORT_FIXTURES
    ]
    activity_paths = [
        _ACTIVITY_SUPPORT_FIXTURES[oid]
        for oid in first.supporting_option_ids
        if oid in _ACTIVITY_SUPPORT_FIXTURES
    ]
    transport_paths = [
        _TRANSPORT_SUPPORT_FIXTURES[oid]
        for oid in first.supporting_option_ids
        if oid in _TRANSPORT_SUPPORT_FIXTURES
    ]
    if not (lodging_paths or activity_paths or transport_paths):
        return None

    primary_dest_id = (
        first.supporting_destination_ids[0]
        if first.supporting_destination_ids
        else "dest-city-kyoto"
    )
    base_dest_payload = _load_payload("tests/fixtures/options/destinations/kyoto_city.json")
    primary_dest_payload = copy.deepcopy(base_dest_payload)
    primary_dest_payload["destination_id"] = primary_dest_id
    destinations = [Destination.from_dict(primary_dest_payload)]

    lodgings: list[LodgingOption] = []
    for rel_path in lodging_paths:
        lodg_payload = copy.deepcopy(_load_payload(rel_path))
        lodg_payload["destination_id"] = primary_dest_id
        lodg_payload["location_summary"]["destination_id"] = primary_dest_id
        lodgings.append(LodgingOption.from_dict(lodg_payload))

    activities: list[ActivityOption] = []
    for rel_path in activity_paths:
        act_payload = copy.deepcopy(_load_payload(rel_path))
        act_payload["destination_id"] = primary_dest_id
        activities.append(ActivityOption.from_dict(act_payload))

    transports: list[TransportOption] = []
    if transport_paths:
        origin_id = f"{primary_dest_id}-origin"
        origin_payload = copy.deepcopy(base_dest_payload)
        origin_payload["destination_id"] = origin_id
        destinations.insert(0, Destination.from_dict(origin_payload))
        for rel_path in transport_paths:
            tr_payload = copy.deepcopy(_load_payload(rel_path))
            tr_payload["origin_id"] = origin_id
            tr_payload["destination_id"] = primary_dest_id
            transports.append(TransportOption.from_dict(tr_payload))

    target = first.target_option
    q = target.quality_summary
    component_ids = [
        *(item.option_id for item in lodgings),
        *(item.option_id for item in transports),
        *(item.option_id for item in activities),
    ]
    return InventoryBundle(
        bundle_id=f"bundle:{target.option_id}",
        title=target.label,
        bundle_context="mixed",
        destinations=destinations,
        lodging_options=lodgings,
        transport_options=transports,
        activity_options=activities,
        composition_summary=BundleCompositionSummary(
            assembly_role="candidate_seed",
            primary_destination_id=primary_dest_id,
            component_option_ids=component_ids,
        ),
        provenance_summary=BundleProvenanceSummary(),
        quality_value_fit=BundleQualityValueFitSummary(
            quality_signal=q.quality_signal,
            value_signal=q.value_signal,
            fit_signal=q.fit_signal,
        ),
        explanation=BundleExplanation(
            strengths=list(target.explanation) or [target.summary or target.label],
            tradeoffs=list(target.drawbacks),
        ),
        summary=target.summary,
    )


def _score_leisure_bundle(result_set: Any, bundle: Any) -> list[Any]:
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
    from trip_planner.preferences.fixture_corpus import build_profile_from_overrides
    from trip_planner.ranking import LeisureRankingEngine

    scenario = _load_payload("tests/fixtures/ranking/leisure/depth_oriented_urban_trip.json")
    profile = build_profile_from_overrides(scenario["profile_overrides"])
    obj = scenario["objectives"]
    protect_open_blocks = bool(obj["protect_open_blocks"])
    recovery_priority = float(obj["recovery_priority"])
    transit_is_feature = bool(obj["transit_is_feature"])
    objectives = ItineraryObjectives(
        objective_id=f"obj:{result_set.trip_id}:{result_set.purpose}",
        trip_id=result_set.trip_id,
        route_shape=obj["route_shape"],
        target_base_count=CountRange(min_value=1, max_value=2),
        move_density=MoveDensityTarget(max_moves=3, cadence_days=3),
        recovery_expectations=RecoveryExpectations(
            buffer_days=1,
            recovery_priority=recovery_priority,
        ),
        day_structure=DayStructureObjectives(
            structure_level="moderate",
            wandering_support_level=0.85 if protect_open_blocks else 0.35,
            reservation_density=0.3 if protect_open_blocks else 0.75,
        ),
        discovery_strategy=DiscoveryStrategy(
            style=obj["discovery_style"],
            protect_open_blocks=protect_open_blocks,
        ),
        budget_protection=BudgetProtection(
            protected_categories=["lodging", "food"],
            sensitivity=0.65,
        ),
        quality_floor_protection=QualityFloorProtection(
            required_categories=list(obj["required_quality"])
        ),
        lodging_strategy=LodgingStrategy(
            base_style="single_base",
            arrival_buffer_priority=recovery_priority,
        ),
        transport_strategy=TransportStrategy(
            preferred_modes=["rail"] if transit_is_feature else ["local_ground"],
            transit_is_feature=transit_is_feature,
        ),
        explanations=["Deterministic baseline leisure objectives."],
    )
    ranked = LeisureRankingEngine().rank_bundles(
        profile,
        objectives,
        [bundle],
        trip_id=result_set.trip_id,
        purpose=result_set.purpose,
        title=result_set.title,
    )
    return list(ranked.results[0].score_breakdown.component_contributions)


def _score_business_bundle(result_set: Any, bundle: Any) -> list[Any]:
    from trip_planner.business import (
        BusinessTravelProfile,
        PolicyConstraintSet,
        derive_business_planning_objectives,
    )
    from trip_planner.ranking import BusinessRankingEngine

    profile = BusinessTravelProfile.from_dict(
        _load_payload("tests/fixtures/business/conference_profile.json")
    )
    objectives = derive_business_planning_objectives(profile, trip_id=result_set.trip_id)
    constraint_payload = _load_payload("tests/fixtures/business/policy_round_trip_compliant.json")
    constraint_set = PolicyConstraintSet(**constraint_payload["constraint_set"])
    ranked = BusinessRankingEngine().rank_bundles(
        profile,
        objectives,
        [bundle],
        trip_id=result_set.trip_id,
        purpose=result_set.purpose,
        title=result_set.title,
        constraint_set=constraint_set,
    )
    return list(ranked.results[0].score_breakdown.component_contributions)


def _canonical_ranking_contributions(result_set: Any, first: Any) -> list[Any]:
    from trip_planner.ranking import BusinessRankingEngine, LeisureRankingEngine

    engine_keys = set(LeisureRankingEngine.COMPONENT_WEIGHTS) | set(
        BusinessRankingEngine.COMPONENT_WEIGHTS
    )
    existing = first.score_breakdown.component_contributions
    if any(
        item.axis_key in engine_keys or item.contribution_id in engine_keys for item in existing
    ):
        return list(existing)
    if first.result_kind != "item" or first.target_option is None:
        return list(existing)
    bundle = _build_supporting_bundle(first)
    if bundle is None:
        return list(existing)
    if result_set.purpose == "policy_comparison":
        return _score_business_bundle(result_set, bundle)
    return _score_leisure_bundle(result_set, bundle)


def _evaluate_ranking(
    payload: dict[str, Any],
) -> tuple[dict[str, float], dict[str, float], set[str]]:
    from trip_planner.ranking import RankedResultSet

    result_set = RankedResultSet.from_dict(payload)
    first = result_set.results[0]
    legacy_metrics = _default_legacy_metrics()
    raw_metrics: dict[str, float] = {}
    observed: set[str] = set()

    if first.target_option is not None:
        legacy_metrics["cost_total"] = _amount(first.target_option.cost_summary.total)
        quality = first.target_option.quality_summary
        for attr_name in ("quality_signal", "value_signal", "fit_signal"):
            val = getattr(quality, attr_name)
            if val is not None:
                raw_metrics[attr_name] = float(val)
                observed.add(attr_name)

    for attr_name in ("input_coverage", "scoring_stability"):
        val = getattr(first.confidence_summary, attr_name)
        if val is not None:
            raw_metrics[attr_name] = float(val)
            observed.add(attr_name)

    for contribution in _canonical_ranking_contributions(result_set, first):
        if contribution.normalized_signal is None:
            continue
        for candidate_key in (contribution.axis_key, contribution.contribution_id):
            if candidate_key in _METRIC_KEY_SET:
                raw_metrics[candidate_key] = float(contribution.normalized_signal)
                observed.add(candidate_key)

    return legacy_metrics, raw_metrics, observed


def evaluate_fixture(fixture_name: str) -> FixtureEvaluation:
    payload = _load_payload(fixture_name)
    model_kind = _classify_payload(payload)
    if model_kind == "transport":
        legacy_metrics, raw_metrics, observed = _evaluate_transport(payload)
    elif model_kind == "lodging":
        legacy_metrics, raw_metrics, observed = _evaluate_lodging(payload)
    else:
        legacy_metrics, raw_metrics, observed = _evaluate_ranking(payload)

    metrics = {
        **legacy_metrics,
        **{key: raw_metrics.get(key, 0.0) for key in METRIC_KEYS},
    }
    return FixtureEvaluation(
        model_kind=model_kind,
        metrics=metrics,
        observed_reads=frozenset(observed & _METRIC_KEY_SET),
    )


def metrics_for(fixture_name: str) -> dict[str, float]:
    """Reduce one baseline fixture to a flat metrics dict through canonical models."""
    return evaluate_fixture(fixture_name).metrics


def observed_reads_for(
    fixture_names: Iterable[str],
    *,
    allowed_keys: Iterable[str] | None = None,
) -> set[str]:
    """Return the canonical metric keys observed read at runtime across fixtures."""
    allowed = set(METRIC_KEYS) if allowed_keys is None else set(allowed_keys)
    observed: set[str] = set()
    for fixture_name in fixture_names:
        observed.update(evaluate_fixture(fixture_name).observed_reads)
    return observed & allowed


def signal_keys() -> list[str]:
    return list(_SIGNAL_KEYS)


def roundtrip_is_stable(fixture_name: str) -> bool:
    """Structural integrity: canonical model ``from_dict`` / ``to_dict`` is idempotent.

    The first parse may normalize (fill defaults, canonicalize legacy keys), so
    we don't require equality with the raw fixture. We require that re-parsing
    the serialized form yields the *same* serialization -- i.e. the model has a
    stable canonical representation.
    """
    try:
        payload = _load_payload(fixture_name)
        model_cls = _model_class_for_kind(_classify_payload(payload))
        once = model_cls.from_dict(payload).to_dict()
        twice = model_cls.from_dict(once).to_dict()
    except (KeyError, TypeError, ValueError):
        return False
    return once == twice
