"""Business-planning objective contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from . import schema
from trip_planner.contracts._validators import (
    require_non_empty,
    require_probability,
    require_strings,
)

CHANNEL_MODES: tuple[str, ...] = ("approved_only", "approved_first", "flexible")
SCHEDULE_PROTECTION_LEVELS: tuple[str, ...] = (
    "standard",
    "protected",
    "mission_critical",
)
COST_CONTROL_POSTURES: tuple[str, ...] = ("balanced", "policy_first", "cost_first")
EXCEPTION_PATH_POSTURES: tuple[str, ...] = (
    "compliant_first",
    "policy_nearest",
    "exception_ready",
)


def _require_positive_int_mapping(mapping: dict[str, int], field_name: str) -> None:
    if any(not isinstance(key, str) or not key for key in mapping):
        raise ValueError(f"{field_name} must use non-empty string keys")
    for key, value in mapping.items():
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{field_name}[{key}] must be an int")
        if value <= 0:
            raise ValueError(f"{field_name}[{key}] must be positive")


@dataclass(slots=True)
class BookingChannelObjectives:
    required_channels: list[str] = field(default_factory=list)
    channel_mode: str = "approved_first"
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_strings(self.required_channels, "required_channels")
        if self.channel_mode not in CHANNEL_MODES:
            raise ValueError(f"channel_mode must be one of {CHANNEL_MODES}")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ScheduleProtectionObjectives:
    protection_level: str = "standard"
    arrival_buffer_preference: str = "moderate"
    same_day_return_tolerance: float = 0.0
    red_eye_tolerance: float = 0.0
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.protection_level not in SCHEDULE_PROTECTION_LEVELS:
            raise ValueError(f"protection_level must be one of {SCHEDULE_PROTECTION_LEVELS}")
        if self.arrival_buffer_preference not in schema.ARRIVAL_BUFFER_PREFERENCES:
            raise ValueError(
                "arrival_buffer_preference must be one of " f"{schema.ARRIVAL_BUFFER_PREFERENCES}"
            )
        require_probability(self.same_day_return_tolerance, "same_day_return_tolerance")
        require_probability(self.red_eye_tolerance, "red_eye_tolerance")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ComparableRequirementObjectives:
    required_categories: dict[str, int] = field(default_factory=dict)
    capture_required: bool = False
    additional_comparables_for_exception: bool = False
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_positive_int_mapping(self.required_categories, "required_categories")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class JustificationReadinessObjectives:
    required_fields: list[str] = field(default_factory=list)
    required_receipt_categories: list[str] = field(default_factory=list)
    booking_link_retention_required: bool = False
    maintain_exception_packet: bool = False
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_strings(self.required_fields, "required_fields")
        require_strings(self.required_receipt_categories, "required_receipt_categories")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CostControlObjectives:
    posture: str = "balanced"
    overall_cost_priority: float = 0.0
    policy_compliance_priority: float = 0.0
    employee_convenience_priority: float = 0.0
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.posture not in COST_CONTROL_POSTURES:
            raise ValueError(f"posture must be one of {COST_CONTROL_POSTURES}")
        require_probability(self.overall_cost_priority, "overall_cost_priority")
        require_probability(
            self.policy_compliance_priority,
            "policy_compliance_priority",
        )
        require_probability(
            self.employee_convenience_priority,
            "employee_convenience_priority",
        )
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ComfortFloorObjectives:
    required_categories: list[str] = field(default_factory=list)
    preserve_arrival_readiness: bool = False
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_strings(self.required_categories, "required_categories")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ExceptionPathObjectives:
    posture: str = "compliant_first"
    fallback_mode: str = "nearest_compliant"
    allowed_exception_types: list[str] = field(default_factory=list)
    approval_roles: list[str] = field(default_factory=list)
    preclearance_required: bool = False
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.posture not in EXCEPTION_PATH_POSTURES:
            raise ValueError(f"posture must be one of {EXCEPTION_PATH_POSTURES}")
        if self.fallback_mode not in schema.EXCEPTION_FALLBACK_MODES:
            raise ValueError(f"fallback_mode must be one of {schema.EXCEPTION_FALLBACK_MODES}")
        require_strings(self.allowed_exception_types, "allowed_exception_types")
        require_strings(self.approval_roles, "approval_roles")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BusinessPlanningObjectives:
    objective_id: str
    trip_id: str
    channel_strategy: BookingChannelObjectives = field(default_factory=BookingChannelObjectives)
    schedule_protection: ScheduleProtectionObjectives = field(
        default_factory=ScheduleProtectionObjectives
    )
    comparable_requirements: ComparableRequirementObjectives = field(
        default_factory=ComparableRequirementObjectives
    )
    justification_readiness: JustificationReadinessObjectives = field(
        default_factory=JustificationReadinessObjectives
    )
    cost_control_posture: CostControlObjectives = field(default_factory=CostControlObjectives)
    comfort_floor_protection: ComfortFloorObjectives = field(default_factory=ComfortFloorObjectives)
    exception_path_posture: ExceptionPathObjectives = field(default_factory=ExceptionPathObjectives)
    explanations: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.objective_id, "objective_id")
        require_non_empty(self.trip_id, "trip_id")
        if not isinstance(self.channel_strategy, BookingChannelObjectives):
            raise ValueError("channel_strategy must be a BookingChannelObjectives")
        if not isinstance(self.schedule_protection, ScheduleProtectionObjectives):
            raise ValueError("schedule_protection must be a ScheduleProtectionObjectives")
        if not isinstance(self.comparable_requirements, ComparableRequirementObjectives):
            raise ValueError("comparable_requirements must be a ComparableRequirementObjectives")
        if not isinstance(self.justification_readiness, JustificationReadinessObjectives):
            raise ValueError("justification_readiness must be a JustificationReadinessObjectives")
        if not isinstance(self.cost_control_posture, CostControlObjectives):
            raise ValueError("cost_control_posture must be a CostControlObjectives")
        if not isinstance(self.comfort_floor_protection, ComfortFloorObjectives):
            raise ValueError("comfort_floor_protection must be a ComfortFloorObjectives")
        if not isinstance(self.exception_path_posture, ExceptionPathObjectives):
            raise ValueError("exception_path_posture must be an ExceptionPathObjectives")
        require_strings(self.explanations, "explanations")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
