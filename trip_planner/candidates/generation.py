"""Deterministic early candidate generation from normalized planning objects."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from statistics import mean

from trip_planner.business.policy_contracts import PolicyConstraintSet
from trip_planner.contracts.options import ComparisonAxis
from trip_planner.options import (
    ActivityOption,
    BundleCompositionSummary,
    BundleExplanation,
    BundleFeasibility,
    BundleProvenanceSummary,
    BundleQualityValueFitSummary,
    Destination,
    InventoryBundle,
    LodgingOption,
    TransportOption,
)

from .models import (
    CandidateExclusion,
    CandidateFilterSummary,
    CandidateSeed,
    CandidateSet,
)


def generate_candidate_set(
    *,
    trip_id: str,
    purpose: str,
    destinations: list[Destination],
    lodging_options: list[LodgingOption],
    transport_options: list[TransportOption],
    activity_options: list[ActivityOption],
    selection_limit: int = 3,
    max_source_freshness_days: int = 30,
    policy_constraints: PolicyConstraintSet | None = None,
) -> CandidateSet:
    if selection_limit <= 0:
        raise ValueError(f"selection_limit must be a positive integer; got {selection_limit!r}")
    if max_source_freshness_days < 0:
        raise ValueError(
            "max_source_freshness_days must be a non-negative integer; "
            f"got {max_source_freshness_days!r}"
        )

    destination_map = {item.destination_id: item for item in destinations}
    exclusions: list[CandidateExclusion] = []
    included_lodging: list[LodgingOption] = []
    included_transport: list[TransportOption] = []
    included_activity: list[ActivityOption] = []

    for lodging_option in lodging_options:
        exclusion = _evaluate_lodging(
            lodging_option,
            destination_map=destination_map,
            max_source_freshness_days=max_source_freshness_days,
            policy_constraints=(policy_constraints if purpose == "policy_comparison" else None),
        )
        if exclusion is None:
            included_lodging.append(lodging_option)
        else:
            exclusions.append(exclusion)

    for transport_option in transport_options:
        exclusion = _evaluate_transport(
            transport_option,
            destination_map=destination_map,
            max_source_freshness_days=max_source_freshness_days,
            policy_constraints=(policy_constraints if purpose == "policy_comparison" else None),
        )
        if exclusion is None:
            included_transport.append(transport_option)
        else:
            exclusions.append(exclusion)

    for activity_option in activity_options:
        exclusion = _evaluate_activity(
            activity_option,
            destination_map=destination_map,
            max_source_freshness_days=max_source_freshness_days,
        )
        if exclusion is None:
            included_activity.append(activity_option)
        else:
            exclusions.append(exclusion)

    seeds = _build_candidate_seeds(
        purpose=purpose,
        destinations=destinations,
        lodging_options=included_lodging,
        transport_options=included_transport,
        activity_options=included_activity,
        policy_constraints=(policy_constraints if purpose == "policy_comparison" else None),
    )
    if not seeds:
        raise ValueError("candidate generation produced no bundle seeds from the provided inputs")

    limited_seeds = seeds[:selection_limit]
    source_refs = _dedupe_strings(
        source_ref
        for seed in limited_seeds
        for source_ref in seed.bundle.provenance_summary.source_refs
    )
    comparison_axes = _comparison_axes_for_purpose(purpose)
    filter_summary = CandidateFilterSummary(
        total_destinations=len(destinations),
        total_lodging_options=len(lodging_options),
        total_transport_options=len(transport_options),
        total_activity_options=len(activity_options),
        included_bundle_count=len(limited_seeds),
        excluded_option_count=len(exclusions),
        freshness_exclusion_count=sum(
            1 for item in exclusions if item.reason_code == "stale_source"
        ),
        policy_exclusion_count=sum(
            1
            for item in exclusions
            if item.reason_code in {"policy_channel", "policy_rate_cap", "policy_approval"}
        ),
        availability_exclusion_count=sum(
            1 for item in exclusions if item.reason_code == "unavailable"
        ),
        notes=[
            "Candidate generation remains deterministic and inspectable.",
            "Excluded options preserve explicit reason codes for later review or ranking.",
        ],
    )
    return CandidateSet(
        candidate_set_id=f"candidate-set:{trip_id}:{purpose}",
        trip_id=trip_id,
        purpose=purpose,
        seeds=limited_seeds,
        exclusions=exclusions,
        filter_summary=filter_summary,
        comparison_axes=comparison_axes,
        explanation=[
            "Bundle seeds are deterministic assembly outputs from normalized inventory.",
            "Final scoring, search, and route optimization belong to later layers.",
        ],
        source_refs=source_refs,
        selection_limit=min(selection_limit, len(limited_seeds)),
    )


def _build_candidate_seeds(
    *,
    purpose: str,
    destinations: list[Destination],
    lodging_options: list[LodgingOption],
    transport_options: list[TransportOption],
    activity_options: list[ActivityOption],
    policy_constraints: PolicyConstraintSet | None,
) -> list[CandidateSeed]:
    transport_by_destination: dict[str, list[TransportOption]] = defaultdict(list)
    for option in transport_options:
        transport_by_destination[option.origin_id].append(option)
        if option.destination_id != option.origin_id:
            transport_by_destination[option.destination_id].append(option)

    lodging_by_destination: dict[str, list[LodgingOption]] = defaultdict(list)
    for lodging_option in lodging_options:
        lodging_by_destination[lodging_option.destination_id].append(lodging_option)

    activity_by_destination: dict[str, list[ActivityOption]] = defaultdict(list)
    for activity_option in activity_options:
        activity_by_destination[activity_option.destination_id].append(activity_option)

    seeds: list[CandidateSeed] = []
    for destination in destinations:
        destination_lodging = sorted(
            lodging_by_destination.get(destination.destination_id, []),
            key=lambda item: item.fit_summary.overall_signal or 0.0,
            reverse=True,
        )
        destination_transport = sorted(
            transport_by_destination.get(destination.destination_id, []),
            key=lambda item: item.fit_summary.overall_signal or 0.0,
            reverse=True,
        )
        destination_activity = sorted(
            activity_by_destination.get(destination.destination_id, []),
            key=lambda item: item.significance_summary.overall_signal or 0.0,
            reverse=True,
        )
        if not (destination_lodging or destination_transport or destination_activity):
            continue
        bundle_destinations = _bundle_destinations(
            destination,
            destination_transport=destination_transport,
            all_destinations=destinations,
        )
        included_option_ids = _dedupe_strings(
            [item.option_id for item in destination_lodging]
            + [item.option_id for item in destination_transport]
            + [item.option_id for item in destination_activity]
        )
        bundle = InventoryBundle(
            bundle_id=f"bundle:{destination.destination_id}:{purpose}",
            title=f"{destination.name} candidate seed",
            bundle_context=_bundle_context(
                destination_lodging=destination_lodging,
                destination_transport=destination_transport,
                destination_activity=destination_activity,
            ),
            destinations=bundle_destinations,
            lodging_options=destination_lodging,
            transport_options=destination_transport,
            activity_options=destination_activity,
            composition_summary=BundleCompositionSummary(
                assembly_role="candidate_seed",
                primary_destination_id=destination.destination_id,
                component_option_ids=included_option_ids,
                notes=["Generated before ranking or route search."],
            ),
            provenance_summary=BundleProvenanceSummary(
                source_refs=_aggregate_source_refs(
                    bundle_destinations,
                    destination_lodging,
                    destination_transport,
                    destination_activity,
                ),
                booking_links=_aggregate_booking_links(
                    destination_lodging,
                    destination_transport,
                    destination_activity,
                ),
                notes=["Source references remain explicit on the included normalized records."],
            ),
            quality_value_fit=BundleQualityValueFitSummary(
                quality_signal=_mean_or_none(
                    [item.quality_summary.overall_signal for item in destination_lodging]
                    + [item.quality_summary.overall_signal for item in destination_activity]
                    + [item.experience_summary.comfort_signal for item in destination_transport]
                ),
                value_signal=_mean_or_none(
                    [item.value_summary.overall_signal for item in destination_lodging]
                    + [item.value_summary.overall_signal for item in destination_activity]
                    + [item.fit_summary.policy_fit_signal for item in destination_transport]
                ),
                fit_signal=_mean_or_none(
                    [item.fit_summary.overall_signal for item in destination_lodging]
                    + [item.fit_summary.overall_signal for item in destination_activity]
                    + [item.fit_summary.overall_signal for item in destination_transport]
                ),
            ),
            feasibility=BundleFeasibility(
                available=True,
                internally_consistent=True,
                blocking_reasons=[],
                dependencies=_bundle_dependencies(
                    destination_lodging,
                    destination_transport,
                    destination_activity,
                ),
                accessibility_notes=_bundle_accessibility_notes(
                    destination_lodging,
                    destination_transport,
                    destination_activity,
                ),
            ),
            explanation=BundleExplanation(
                headline=f"Deterministic candidate seed for {destination.name}.",
                strengths=_bundle_strengths(
                    purpose=purpose,
                    lodging_options=destination_lodging,
                    transport_options=destination_transport,
                    activity_options=destination_activity,
                ),
                tradeoffs=_bundle_tradeoffs(
                    destination_lodging,
                    destination_transport,
                    destination_activity,
                ),
                evidence=[
                    "Built from normalized destination and option contracts.",
                    "Preserves explicit source references and booking links.",
                ],
            ),
            summary=(
                "Early candidate seed for downstream comparison and ranking without collapsing "
                "the normalized option layer."
            ),
            tags=_bundle_tags(destination_lodging, destination_transport, destination_activity),
            notes=["Downstream ranking can reorder or discard this seed without rebuilding input."],
        )
        seeds.append(
            CandidateSeed(
                candidate_id=f"candidate:{destination.destination_id}:{purpose}",
                bundle=bundle,
                supported_purposes=_supported_purposes(purpose),
                inclusion_reasons=_bundle_strengths(
                    purpose=purpose,
                    lodging_options=destination_lodging,
                    transport_options=destination_transport,
                    activity_options=destination_activity,
                ),
                unresolved_risks=_bundle_tradeoffs(
                    destination_lodging,
                    destination_transport,
                    destination_activity,
                ),
                policy_ready=_is_policy_ready(
                    purpose,
                    destination_lodging,
                    destination_transport,
                    policy_constraints,
                ),
            )
        )
    return sorted(
        seeds,
        key=lambda item: (
            item.policy_ready,
            item.bundle.quality_value_fit.fit_signal or 0.0,
            len(item.bundle.option_ids),
        ),
        reverse=True,
    )


def _evaluate_lodging(
    option: LodgingOption,
    *,
    destination_map: dict[str, Destination],
    max_source_freshness_days: int,
    policy_constraints: PolicyConstraintSet | None,
) -> CandidateExclusion | None:
    if option.destination_id not in destination_map:
        return CandidateExclusion(
            option_id=option.option_id,
            option_kind="lodging",
            reason_code="missing_destination",
            message="Lodging option references a destination outside the candidate destination set.",
            destination_ids=[option.destination_id],
            source_ref_ids=[item.provenance_id for item in option.source_refs],
        )
    if not option.feasibility.available or option.feasibility.inventory_status == "sold_out":
        return CandidateExclusion(
            option_id=option.option_id,
            option_kind="lodging",
            reason_code="unavailable",
            message="Lodging option is not currently available for early candidate generation.",
            destination_ids=[option.destination_id],
            source_ref_ids=[item.provenance_id for item in option.source_refs],
        )
    if _is_stale(
        [item.freshness_days_at_capture for item in option.source_refs],
        max_source_freshness_days,
    ):
        return CandidateExclusion(
            option_id=option.option_id,
            option_kind="lodging",
            reason_code="stale_source",
            message="Lodging option freshness exceeds the candidate-generation threshold.",
            destination_ids=[option.destination_id],
            source_ref_ids=[item.provenance_id for item in option.source_refs],
        )
    if policy_constraints is None:
        return None
    if not _channel_allowed(
        option.booking_terms.booking_channel,
        policy_constraints.required_booking_channels,
    ):
        return CandidateExclusion(
            option_id=option.option_id,
            option_kind="lodging",
            reason_code="policy_channel",
            message="Lodging booking channel is outside the allowed business-policy channels.",
            destination_ids=[option.destination_id],
            source_ref_ids=[item.provenance_id for item in option.source_refs],
        )
    max_nightly = policy_constraints.lodging_rules.get("max_nightly_rate_usd")
    nightly = option.cost_summary.nightly
    if (
        isinstance(max_nightly, (int, float))
        and nightly is not None
        and nightly.typical_amount is not None
    ):
        if nightly.currency != "USD":
            return CandidateExclusion(
                option_id=option.option_id,
                option_kind="lodging",
                reason_code="policy_rate_cap",
                message=(
                    "Lodging nightly estimate must be denominated in USD to compare "
                    "against the configured business-policy cap."
                ),
                destination_ids=[option.destination_id],
                source_ref_ids=[item.provenance_id for item in option.source_refs],
            )
        if nightly.typical_amount <= float(max_nightly):
            return None
        return CandidateExclusion(
            option_id=option.option_id,
            option_kind="lodging",
            reason_code="policy_rate_cap",
            message="Lodging nightly estimate exceeds the configured business-policy cap.",
            destination_ids=[option.destination_id],
            source_ref_ids=[item.provenance_id for item in option.source_refs],
        )
    if option.feasibility.business_approval_status not in {"approved", "preferred"}:
        return CandidateExclusion(
            option_id=option.option_id,
            option_kind="lodging",
            reason_code="policy_approval",
            message="Lodging business approval status is not ready for a compliant initial set.",
            destination_ids=[option.destination_id],
            source_ref_ids=[item.provenance_id for item in option.source_refs],
        )
    return None


def _evaluate_transport(
    option: TransportOption,
    *,
    destination_map: dict[str, Destination],
    max_source_freshness_days: int,
    policy_constraints: PolicyConstraintSet | None,
) -> CandidateExclusion | None:
    if option.origin_id not in destination_map or option.destination_id not in destination_map:
        return CandidateExclusion(
            option_id=option.option_id,
            option_kind=option.transport_kind,
            reason_code="missing_destination",
            message="Transport option must map to represented origin and destination records.",
            destination_ids=[option.origin_id, option.destination_id],
            source_ref_ids=[item.provenance_id for item in option.source_refs],
        )
    if not option.feasibility.available or option.feasibility.availability_status == "sold_out":
        return CandidateExclusion(
            option_id=option.option_id,
            option_kind=option.transport_kind,
            reason_code="unavailable",
            message="Transport option is not currently available for candidate generation.",
            destination_ids=[option.origin_id, option.destination_id],
            source_ref_ids=[item.provenance_id for item in option.source_refs],
        )
    if _is_stale(
        [item.freshness_days_at_capture for item in option.source_refs],
        max_source_freshness_days,
    ):
        return CandidateExclusion(
            option_id=option.option_id,
            option_kind=option.transport_kind,
            reason_code="stale_source",
            message="Transport option freshness exceeds the candidate-generation threshold.",
            destination_ids=[option.origin_id, option.destination_id],
            source_ref_ids=[item.provenance_id for item in option.source_refs],
        )
    if policy_constraints is None:
        return None
    if not _channel_allowed(
        option.booking_terms.booking_channel,
        policy_constraints.required_booking_channels,
    ):
        return CandidateExclusion(
            option_id=option.option_id,
            option_kind=option.transport_kind,
            reason_code="policy_channel",
            message="Transport booking channel is outside the allowed business-policy channels.",
            destination_ids=[option.origin_id, option.destination_id],
            source_ref_ids=[item.provenance_id for item in option.source_refs],
        )
    if option.policy_summary.business_approval_status not in {"approved", "preferred"}:
        return CandidateExclusion(
            option_id=option.option_id,
            option_kind=option.transport_kind,
            reason_code="policy_approval",
            message="Transport policy approval is not ready for a compliant initial set.",
            destination_ids=[option.origin_id, option.destination_id],
            source_ref_ids=[item.provenance_id for item in option.source_refs],
        )
    return None


def _evaluate_activity(
    option: ActivityOption,
    *,
    destination_map: dict[str, Destination],
    max_source_freshness_days: int,
) -> CandidateExclusion | None:
    if option.destination_id not in destination_map:
        return CandidateExclusion(
            option_id=option.option_id,
            option_kind="activity",
            reason_code="missing_destination",
            message="Activity option references a destination outside the candidate destination set.",
            destination_ids=[option.destination_id],
            source_ref_ids=[item.provenance_id for item in option.source_refs],
        )
    if not option.feasibility.available or option.feasibility.availability_status == "sold_out":
        return CandidateExclusion(
            option_id=option.option_id,
            option_kind="activity",
            reason_code="unavailable",
            message="Activity option is not currently available for candidate generation.",
            destination_ids=[option.destination_id],
            source_ref_ids=[item.provenance_id for item in option.source_refs],
        )
    if _is_stale(
        [item.freshness_days_at_capture for item in option.source_refs],
        max_source_freshness_days,
    ):
        return CandidateExclusion(
            option_id=option.option_id,
            option_kind="activity",
            reason_code="stale_source",
            message="Activity option freshness exceeds the candidate-generation threshold.",
            destination_ids=[option.destination_id],
            source_ref_ids=[item.provenance_id for item in option.source_refs],
        )
    return None


def _bundle_destinations(
    primary_destination: Destination,
    *,
    destination_transport: list[TransportOption],
    all_destinations: list[Destination],
) -> list[Destination]:
    destination_map = {item.destination_id: item for item in all_destinations}
    ids = [primary_destination.destination_id]
    for option in destination_transport:
        ids.extend([option.origin_id, option.destination_id])
    return [destination_map[item] for item in _dedupe_strings(ids) if item in destination_map]


def _bundle_strengths(
    *,
    purpose: str,
    lodging_options: list[LodgingOption],
    transport_options: list[TransportOption],
    activity_options: list[ActivityOption],
) -> list[str]:
    strengths: list[str] = []
    if lodging_options:
        best_lodging = lodging_options[0]
        strengths.append(
            f"Lodging seed anchored by {best_lodging.name} with fit {best_lodging.fit_summary.overall_signal or 0:.2f}."
        )
    if transport_options:
        best_transport = transport_options[0]
        strengths.append(
            f"Transport seed keeps {best_transport.transport_kind} access inspectable from normalized timing and policy metadata."
        )
    if activity_options:
        best_activity = activity_options[0]
        strengths.append(
            f"Activity seed preserves {best_activity.name} as an early anchor instead of ranking it away."
        )
    if purpose == "policy_comparison":
        strengths.append(
            "Included options already satisfy first-pass booking-channel and approval checks."
        )
    return strengths


def _bundle_tradeoffs(
    lodging_options: list[LodgingOption],
    transport_options: list[TransportOption],
    activity_options: list[ActivityOption],
) -> list[str]:
    risks: list[str] = []
    for lodging_option in lodging_options:
        risks.extend(lodging_option.feasibility.constraints)
    for transport_option in transport_options:
        risks.extend(
            transport_option.feasibility.constraints + transport_option.policy_summary.policy_notes
        )
    for activity_option in activity_options:
        risks.extend(activity_option.feasibility.constraints)
    return _dedupe_strings(risks)


def _bundle_dependencies(
    lodging_options: list[LodgingOption],
    transport_options: list[TransportOption],
    activity_options: list[ActivityOption],
) -> list[str]:
    dependencies = [
        "ingestion-complete",
        "candidate-explanations-preserved",
    ]
    if transport_options:
        dependencies.append("route-ranking-pending")
    if activity_options:
        dependencies.append("activity-scheduling-pending")
    return dependencies


def _bundle_accessibility_notes(
    lodging_options: list[LodgingOption],
    transport_options: list[TransportOption],
    activity_options: list[ActivityOption],
) -> list[str]:
    notes: list[str] = []
    for lodging_option in lodging_options:
        notes.extend(lodging_option.feasibility.accessibility_notes)
    for transport_option in transport_options:
        notes.extend(transport_option.feasibility.accessibility_notes)
    for activity_option in activity_options:
        notes.extend(activity_option.feasibility.accessibility_notes)
    return _dedupe_strings(notes)


def _bundle_tags(
    lodging_options: list[LodgingOption],
    transport_options: list[TransportOption],
    activity_options: list[ActivityOption],
) -> list[str]:
    return _dedupe_strings(
        [item for option in lodging_options for item in option.tags]
        + [item for option in transport_options for item in option.tags]
        + [item for option in activity_options for item in option.tags]
    )


def _supported_purposes(purpose: str) -> list[str]:
    if purpose == "policy_comparison":
        return ["policy_comparison", "inventory_narrowing"]
    if purpose == "profile_learning":
        return ["profile_learning", "inventory_narrowing"]
    return [purpose]


def _is_policy_ready(
    purpose: str,
    lodging_options: list[LodgingOption],
    transport_options: list[TransportOption],
    policy_constraints: PolicyConstraintSet | None,
) -> bool:
    if purpose != "policy_comparison" or policy_constraints is None:
        return False
    return bool(lodging_options or transport_options)


def _bundle_context(
    *,
    destination_lodging: list[LodgingOption],
    destination_transport: list[TransportOption],
    destination_activity: list[ActivityOption],
) -> str:
    if destination_lodging and not destination_transport and not destination_activity:
        return "lodging_only"
    if destination_transport and destination_lodging and not destination_activity:
        return "transport_lodging"
    if destination_activity and not destination_transport and not destination_lodging:
        return "activity_cluster"
    return "mixed"


def _comparison_axes_for_purpose(purpose: str) -> list[ComparisonAxis]:
    axes = [
        ComparisonAxis(key="fit", label="Fit signal", direction="higher_better"),
        ComparisonAxis(key="cost", label="Estimated total", direction="lower_better"),
    ]
    if purpose == "policy_comparison":
        axes.append(
            ComparisonAxis(
                key="policy_ready",
                label="Policy readiness",
                direction="higher_better",
            )
        )
    return axes


def _aggregate_source_refs(
    destinations: list[Destination],
    lodging_options: list[LodgingOption],
    transport_options: list[TransportOption],
    activity_options: list[ActivityOption],
) -> list[str]:
    values = [
        item.provenance_id for destination in destinations for item in destination.source_refs
    ]
    for lodging_option in lodging_options:
        values.extend(item.provenance_id for item in lodging_option.source_refs)
    for transport_option in transport_options:
        values.extend(item.provenance_id for item in transport_option.source_refs)
    for activity_option in activity_options:
        values.extend(item.provenance_id for item in activity_option.source_refs)
    return _dedupe_strings(values)


def _aggregate_booking_links(
    lodging_options: list[LodgingOption],
    transport_options: list[TransportOption],
    activity_options: list[ActivityOption],
) -> list[str]:
    values = [item for option in lodging_options for item in option.booking_links]
    values.extend(item for option in transport_options for item in option.booking_links)
    values.extend(item for option in activity_options for item in option.booking_links)
    return _dedupe_strings(values)


def _is_stale(values: list[int | None], max_source_freshness_days: int) -> bool:
    return any(value is not None and value > max_source_freshness_days for value in values)


def _channel_allowed(channel: str, required_channels: list[str]) -> bool:
    if not required_channels:
        return True
    normalized = channel.strip().lower()
    allowed = {item.strip().lower() for item in required_channels}
    return normalized in allowed


def _mean_or_none(values: list[float | None]) -> float | None:
    realized = [item for item in values if item is not None]
    if not realized:
        return None
    return round(mean(realized), 4)


def _dedupe_strings(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))
