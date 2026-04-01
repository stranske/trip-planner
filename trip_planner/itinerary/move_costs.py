"""Route-move cost contracts for first-pass itinerary feasibility checks."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime

from trip_planner._validators import (
    require_non_empty,
    require_non_negative,
    require_probability,
    require_strings,
)
from trip_planner.options import InventoryBundle, TransportOption


def _dt(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _mean(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return round(sum(present) / len(present), 4)


@dataclass(slots=True)
class TravelTimeEstimate:
    estimate_id: str
    source_option_id: str
    origin_id: str
    destination_id: str
    mode: str
    departure_local: str = ""
    arrival_local: str = ""
    duration_minutes: int = 0
    transfer_count: int = 0
    confidence_signal: float | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in (
            "estimate_id",
            "source_option_id",
            "origin_id",
            "destination_id",
            "mode",
        ):
            require_non_empty(getattr(self, field_name), field_name)
        require_non_negative(self.duration_minutes, "duration_minutes")
        require_non_negative(self.transfer_count, "transfer_count")
        if self.confidence_signal is not None:
            require_probability(self.confidence_signal, "confidence_signal")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class MoveCostSummary:
    move_id: str
    origin_id: str
    destination_id: str
    transport_option_id: str
    travel_minutes: int = 0
    transfer_count: int = 0
    burden_signal: float | None = None
    schedule_pressure_signal: float | None = None
    continuity_signal: float | None = None
    friction_penalty: float = 0.0
    hard_blocking: bool = False
    blocking_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in ("move_id", "origin_id", "destination_id", "transport_option_id"):
            require_non_empty(getattr(self, field_name), field_name)
        require_non_negative(self.travel_minutes, "travel_minutes")
        require_non_negative(self.transfer_count, "transfer_count")
        require_non_negative(self.friction_penalty, "friction_penalty")
        for field_name in (
            "burden_signal",
            "schedule_pressure_signal",
            "continuity_signal",
        ):
            value = getattr(self, field_name)
            if value is not None:
                require_probability(value, field_name)
        require_strings(self.blocking_reasons, "blocking_reasons")
        require_strings(self.warnings, "warnings")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _estimate_from_transport(option: TransportOption) -> TravelTimeEstimate:
    timing = option.timing_summary
    confidence = _mean(
        [
            option.fit_summary.schedule_fit_signal,
            option.transfer_burden.schedule_protection_signal,
            1.0 - option.transfer_burden.connection_risk_signal
            if option.transfer_burden.connection_risk_signal is not None
            else None,
        ]
    )
    return TravelTimeEstimate(
        estimate_id=f"travel-estimate:{option.option_id}",
        source_option_id=option.option_id,
        origin_id=option.origin_id,
        destination_id=option.destination_id,
        mode=option.transport_kind,
        departure_local=timing.departure_local,
        arrival_local=timing.arrival_local,
        duration_minutes=timing.duration_minutes,
        transfer_count=option.transfer_burden.transfer_count,
        confidence_signal=confidence,
        notes=list(option.transfer_burden.notes),
    )


def _continuity_signal(bundle: InventoryBundle, option: TransportOption) -> float:
    destination_ids = set(bundle.destination_ids)
    if option.origin_id not in destination_ids or option.destination_id not in destination_ids:
        return 0.0
    if option.origin_id == option.destination_id:
        return 0.35
    return 0.85


def build_move_cost_summaries(
    bundle: InventoryBundle,
    *,
    schedule_protection_required: bool = False,
) -> tuple[list[TravelTimeEstimate], list[MoveCostSummary]]:
    estimates: list[TravelTimeEstimate] = []
    summaries: list[MoveCostSummary] = []

    for option in bundle.transport_options:
        estimate = _estimate_from_transport(option)
        estimates.append(estimate)

        burden_signal = _mean(
            [
                option.transfer_burden.self_navigation_burden_signal,
                option.transfer_burden.baggage_complexity_signal,
                option.transfer_burden.connection_risk_signal,
            ]
        )
        schedule_pressure = None
        if option.transfer_burden.schedule_protection_signal is not None:
            schedule_pressure = round(
                1.0 - option.transfer_burden.schedule_protection_signal, 4
            )
        continuity = _continuity_signal(bundle, option)
        friction_penalty = round(
            (estimate.duration_minutes / 600.0)
            + (estimate.transfer_count * 0.12)
            + ((burden_signal or 0.0) * 0.45)
            + ((schedule_pressure or 0.0) * (0.35 if schedule_protection_required else 0.2)),
            4,
        )

        blocking_reasons: list[str] = []
        warnings: list[str] = []
        if not option.feasibility.available:
            blocking_reasons.append("transport_unavailable")
        if estimate.transfer_count >= 4:
            blocking_reasons.append("excessive_transfer_burden")
        elif estimate.transfer_count >= 2:
            warnings.append("high_transfer_burden")
        if estimate.duration_minutes >= 720:
            blocking_reasons.append("unrealistic_same_day_move")
        elif estimate.duration_minutes >= 300:
            warnings.append("long_intercity_move")
        if continuity < 0.5:
            warnings.append("route_continuity_gap")
        if schedule_protection_required and (schedule_pressure or 0.0) >= 0.55:
            warnings.append("schedule_protection_gap")

        departure = _dt(option.timing_summary.departure_local)
        arrival = _dt(option.timing_summary.arrival_local)
        if departure and arrival and departure.date() == arrival.date():
            if arrival.hour >= 22:
                warnings.append("late_arrival_move")
            if departure.hour <= 6:
                warnings.append("early_departure_move")

        summaries.append(
            MoveCostSummary(
                move_id=f"move-cost:{option.option_id}",
                origin_id=option.origin_id,
                destination_id=option.destination_id,
                transport_option_id=option.option_id,
                travel_minutes=estimate.duration_minutes,
                transfer_count=estimate.transfer_count,
                burden_signal=burden_signal,
                schedule_pressure_signal=schedule_pressure,
                continuity_signal=continuity,
                friction_penalty=friction_penalty,
                hard_blocking=bool(blocking_reasons),
                blocking_reasons=blocking_reasons,
                warnings=warnings,
                notes=list(option.notes),
            )
        )

    return estimates, summaries
