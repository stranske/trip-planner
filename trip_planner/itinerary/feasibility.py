"""First-pass feasibility evaluation for candidate bundles and route moves."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, time

from trip_planner._validators import (
    require_non_empty,
    require_non_negative,
    require_probability,
    require_strings,
)
from trip_planner.options import InventoryBundle

from .move_costs import MoveCostSummary, TravelTimeEstimate, build_move_cost_summaries


def _dt(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _parse_window(value: str) -> tuple[time, time] | None:
    if not value or "-" not in value:
        return None
    start_text, end_text = [piece.strip() for piece in value.split("-", 1)]
    try:
        return time.fromisoformat(start_text), time.fromisoformat(end_text)
    except ValueError:
        return None


def _clamp_probability(value: float) -> float:
    return max(0.0, min(1.0, round(value, 4)))


@dataclass(slots=True)
class TimingConflict:
    conflict_id: str
    code: str
    severity: str
    summary: str
    blocking: bool = False
    related_option_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in ("conflict_id", "code", "severity", "summary"):
            require_non_empty(getattr(self, field_name), field_name)
        require_strings(self.related_option_ids, "related_option_ids")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class RouteContinuityWarning:
    warning_id: str
    code: str
    severity: str
    summary: str
    destination_ids: list[str] = field(default_factory=list)
    related_option_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in ("warning_id", "code", "severity", "summary"):
            require_non_empty(getattr(self, field_name), field_name)
        require_strings(self.destination_ids, "destination_ids")
        require_strings(self.related_option_ids, "related_option_ids")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class FeasibilityAssessment:
    assessment_id: str
    bundle_id: str
    feasible: bool
    recommended_for_ranking: bool
    schedule_protection_required: bool
    total_travel_minutes: int = 0
    total_transfer_count: int = 0
    friction_penalty_total: float = 0.0
    confidence_signal: float | None = None
    missing_data_fields: list[str] = field(default_factory=list)
    blocking_reasons: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    travel_time_estimates: list[TravelTimeEstimate] = field(default_factory=list)
    move_costs: list[MoveCostSummary] = field(default_factory=list)
    timing_conflicts: list[TimingConflict] = field(default_factory=list)
    route_warnings: list[RouteContinuityWarning] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.assessment_id, "assessment_id")
        require_non_empty(self.bundle_id, "bundle_id")
        require_non_negative(self.total_travel_minutes, "total_travel_minutes")
        require_non_negative(self.total_transfer_count, "total_transfer_count")
        require_non_negative(self.friction_penalty_total, "friction_penalty_total")
        if self.confidence_signal is not None:
            require_probability(self.confidence_signal, "confidence_signal")
        require_strings(self.missing_data_fields, "missing_data_fields")
        require_strings(self.blocking_reasons, "blocking_reasons")
        require_strings(self.notes, "notes")
        if any(not isinstance(item, TravelTimeEstimate) for item in self.travel_time_estimates):
            raise ValueError("travel_time_estimates must contain TravelTimeEstimate instances")
        if any(not isinstance(item, MoveCostSummary) for item in self.move_costs):
            raise ValueError("move_costs must contain MoveCostSummary instances")
        if any(not isinstance(item, TimingConflict) for item in self.timing_conflicts):
            raise ValueError("timing_conflicts must contain TimingConflict instances")
        if any(not isinstance(item, RouteContinuityWarning) for item in self.route_warnings):
            raise ValueError("route_warnings must contain RouteContinuityWarning instances")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _schedule_protection_required(bundle: InventoryBundle) -> bool:
    if any("business" in tag for tag in bundle.tags):
        return True
    if any(
        lodging.location_summary.business_access_signal
        and lodging.location_summary.business_access_signal >= 0.8
        for lodging in bundle.lodging_options
    ):
        return True
    return any(
        transport.policy_summary.business_approval_status in {"approved", "preferred"}
        for transport in bundle.transport_options
    )


def _arrival_conflicts(bundle: InventoryBundle) -> list[TimingConflict]:
    conflicts: list[TimingConflict] = []
    for transport in bundle.transport_options:
        arrival = _dt(transport.timing_summary.arrival_local)
        if arrival is None:
            continue
        matching_lodging = [
            lodging
            for lodging in bundle.lodging_options
            if lodging.destination_id == transport.destination_id
        ]
        for lodging in matching_lodging:
            window = _parse_window(lodging.booking_terms.checkin_window)
            if window is None:
                continue
            _, end_time = window
            if arrival.time() > end_time:
                conflicts.append(
                    TimingConflict(
                        conflict_id=f"timing:{transport.option_id}:{lodging.option_id}:arrival",
                        code="late_arrival_checkin_conflict",
                        severity="critical",
                        summary=(
                            f"{transport.name} arrives after the published check-in window for "
                            f"{lodging.name}."
                        ),
                        blocking=True,
                        related_option_ids=[transport.option_id, lodging.option_id],
                    )
                )
    return conflicts


def _activity_timing_conflicts(
    bundle: InventoryBundle,
    *,
    schedule_protection_required: bool,
) -> tuple[list[TimingConflict], list[str]]:
    conflicts: list[TimingConflict] = []
    missing_data_fields: list[str] = []
    arrival_by_destination: dict[str, datetime] = {}
    for transport in bundle.transport_options:
        arrival = _dt(transport.timing_summary.arrival_local)
        if arrival is not None:
            current = arrival_by_destination.get(transport.destination_id)
            if current is None or arrival < current:
                arrival_by_destination[transport.destination_id] = arrival

    for activity in bundle.activity_options:
        window = _parse_window(activity.timing_summary.typical_start_window)
        if window is None:
            missing_data_fields.append(f"activity:{activity.option_id}:typical_start_window")
            continue
        arrival = arrival_by_destination.get(activity.destination_id)
        if arrival is None:
            continue
        start_time, end_time = window
        if arrival.time() > end_time:
            conflicts.append(
                TimingConflict(
                    conflict_id=f"timing:{activity.option_id}:start-window",
                    code="activity_start_window_missed",
                    severity="critical",
                    summary=(
                        f"{activity.name} cannot be reached inside its advertised start window "
                        f"after the inbound move."
                    ),
                    blocking=True,
                    related_option_ids=[activity.option_id],
                )
            )
            continue
        available_minutes = max(
            0,
            (datetime.combine(arrival.date(), end_time, arrival.tzinfo) - arrival).seconds // 60,
        )
        if available_minutes < activity.timing_summary.duration_minutes:
            conflicts.append(
                TimingConflict(
                    conflict_id=f"timing:{activity.option_id}:duration",
                    code="same_day_duration_overflow",
                    severity="critical",
                    summary=(
                        f"{activity.name} needs {activity.timing_summary.duration_minutes} minutes, "
                        f"but only {available_minutes} remain in the same-day window."
                    ),
                    blocking=True,
                    related_option_ids=[activity.option_id],
                )
            )
        elif (
            schedule_protection_required
            and available_minutes - activity.timing_summary.duration_minutes < 90
        ):
            conflicts.append(
                TimingConflict(
                    conflict_id=f"timing:{activity.option_id}:buffer",
                    code="tight_schedule_protection",
                    severity="warning",
                    summary=(
                        f"{activity.name} leaves under 90 minutes of schedule protection after "
                        f"the inbound move."
                    ),
                    related_option_ids=[activity.option_id],
                )
            )

    return conflicts, sorted(set(missing_data_fields))


def _route_warnings(
    bundle: InventoryBundle, move_costs: list[MoveCostSummary]
) -> list[RouteContinuityWarning]:
    warnings: list[RouteContinuityWarning] = []
    destination_sequence = [item.origin_id for item in bundle.transport_options]
    destination_sequence.extend(item.destination_id for item in bundle.transport_options)
    backtracking = any(
        destination_sequence[index] == destination_sequence[index + 2]
        for index in range(len(destination_sequence) - 2)
    )
    if backtracking:
        warnings.append(
            RouteContinuityWarning(
                warning_id=f"route:{bundle.bundle_id}:backtracking",
                code="route_backtracking",
                severity="warning",
                summary="Route sequence backtracks across the same destinations.",
                destination_ids=bundle.destination_ids,
                related_option_ids=[item.transport_option_id for item in move_costs],
            )
        )
    for move_cost in move_costs:
        if "route_continuity_gap" in move_cost.warnings:
            warnings.append(
                RouteContinuityWarning(
                    warning_id=f"route:{move_cost.transport_option_id}:continuity",
                    code="route_continuity_gap",
                    severity="warning",
                    summary="A transport leg references a destination edge the bundle does not model cleanly.",
                    destination_ids=[move_cost.origin_id, move_cost.destination_id],
                    related_option_ids=[move_cost.transport_option_id],
                )
            )
    return warnings


def _representative_travel_totals(
    bundle: InventoryBundle,
    travel_estimates: list[TravelTimeEstimate],
    move_costs: list[MoveCostSummary],
) -> tuple[int, int, list[str]]:
    if not travel_estimates:
        return 0, 0, []

    if bundle.composition_summary.assembly_role == "candidate_seed":
        ranked_pairs = sorted(
            zip(move_costs, travel_estimates, strict=True),
            key=lambda pair: (
                pair[0].hard_blocking,
                pair[0].friction_penalty,
                pair[1].duration_minutes,
                pair[1].transfer_count,
            ),
        )
        _, estimate = ranked_pairs[0]
        return (
            estimate.duration_minutes,
            estimate.transfer_count,
            [
                "Aggregate travel totals reflect the lowest-friction transport option in this candidate seed."
            ],
        )

    return (
        sum(item.duration_minutes for item in travel_estimates),
        sum(item.transfer_count for item in travel_estimates),
        [],
    )


def evaluate_bundle_feasibility(bundle: InventoryBundle) -> FeasibilityAssessment:
    schedule_protection_required = _schedule_protection_required(bundle)
    travel_estimates, move_costs = build_move_cost_summaries(
        bundle,
        schedule_protection_required=schedule_protection_required,
    )

    timing_conflicts = _arrival_conflicts(bundle)
    activity_conflicts, missing_data_fields = _activity_timing_conflicts(
        bundle,
        schedule_protection_required=schedule_protection_required,
    )
    timing_conflicts.extend(activity_conflicts)

    blocking_reasons = list(bundle.feasibility.blocking_reasons)
    blocking_reasons.extend(
        reason for move_cost in move_costs for reason in move_cost.blocking_reasons
    )
    blocking_reasons.extend(conflict.code for conflict in timing_conflicts if conflict.blocking)
    if not bundle.feasibility.available:
        blocking_reasons.append("bundle_unavailable")
    if not bundle.feasibility.internally_consistent:
        blocking_reasons.append("bundle_internally_inconsistent")
    blocking_reasons = sorted(set(blocking_reasons))

    route_warnings = _route_warnings(bundle, move_costs)
    friction_penalty_total = round(sum(item.friction_penalty for item in move_costs), 4)
    total_travel_minutes, total_transfer_count, aggregate_notes = _representative_travel_totals(
        bundle,
        travel_estimates,
        move_costs,
    )
    warning_pressure = (
        len([conflict for conflict in timing_conflicts if not conflict.blocking])
        + len(route_warnings)
        + sum(len(item.warnings) for item in move_costs)
    )
    confidence_signal = _clamp_probability(
        1.0
        - (0.12 * len(missing_data_fields))
        - (0.08 * warning_pressure)
        - (0.14 * len(blocking_reasons))
    )

    notes = [
        "Feasibility output is intended to feed ranking, not replace it.",
        "Hard blockers should suppress ranking promotion, while friction penalties should remain visible.",
    ]
    if schedule_protection_required:
        notes.append("Business-style schedule protection thresholds were applied.")
    notes.extend(aggregate_notes)

    return FeasibilityAssessment(
        assessment_id=f"feasibility:{bundle.bundle_id}",
        bundle_id=bundle.bundle_id,
        feasible=not blocking_reasons,
        recommended_for_ranking=not blocking_reasons,
        schedule_protection_required=schedule_protection_required,
        total_travel_minutes=total_travel_minutes,
        total_transfer_count=total_transfer_count,
        friction_penalty_total=friction_penalty_total,
        confidence_signal=confidence_signal,
        missing_data_fields=missing_data_fields,
        blocking_reasons=blocking_reasons,
        notes=notes,
        travel_time_estimates=travel_estimates,
        move_costs=move_costs,
        timing_conflicts=timing_conflicts,
        route_warnings=route_warnings,
    )
