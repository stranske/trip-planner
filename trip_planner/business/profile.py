"""Canonical business travel profile contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from trip_planner._validators import (
    require_non_empty,
    require_probability,
    require_string_mapping,
    require_strings,
)

from . import schema


@dataclass(slots=True)
class RequiredPresenceWindow:
    start: str
    end: str
    label: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.start, "start")
        require_non_empty(self.end, "end")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TravelerContext:
    employee_type: str
    traveler_experience: str
    home_airport: str
    loyalty_programs: list[str] = field(default_factory=list)
    mobility_or_access_needs: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.employee_type not in schema.EMPLOYEE_TYPES:
            raise ValueError(f"employee_type must be one of {schema.EMPLOYEE_TYPES}")
        if self.traveler_experience not in schema.TRAVELER_EXPERIENCE_LEVELS:
            raise ValueError(
                "traveler_experience must be one of " f"{schema.TRAVELER_EXPERIENCE_LEVELS}"
            )
        require_non_empty(self.home_airport, "home_airport")
        require_strings(self.loyalty_programs, "loyalty_programs")
        require_strings(self.mobility_or_access_needs, "mobility_or_access_needs")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TripPurpose:
    purpose_type: str
    business_justification: str
    required_presence_windows: list[RequiredPresenceWindow] = field(default_factory=list)
    trip_criticality: str = "medium"

    def __post_init__(self) -> None:
        if self.purpose_type not in schema.PURPOSE_TYPES:
            raise ValueError(f"purpose_type must be one of {schema.PURPOSE_TYPES}")
        require_non_empty(self.business_justification, "business_justification")
        if self.trip_criticality not in schema.TRIP_CRITICALITY_LEVELS:
            raise ValueError(f"trip_criticality must be one of {schema.TRIP_CRITICALITY_LEVELS}")
        if any(
            not isinstance(window, RequiredPresenceWindow)
            for window in self.required_presence_windows
        ):
            raise ValueError(
                "required_presence_windows must contain RequiredPresenceWindow instances"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PolicyConstraints:
    required_booking_channels: list[str] = field(default_factory=list)
    airfare_rules: dict[str, Any] = field(default_factory=dict)
    lodging_rules: dict[str, Any] = field(default_factory=dict)
    ground_transport_rules: dict[str, Any] = field(default_factory=dict)
    per_diem_or_meal_rules: dict[str, Any] = field(default_factory=dict)
    approval_triggers: list[str] = field(default_factory=list)
    documentation_rules: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_strings(self.required_booking_channels, "required_booking_channels")
        require_string_mapping(self.airfare_rules, "airfare_rules")
        require_string_mapping(self.lodging_rules, "lodging_rules")
        require_string_mapping(self.ground_transport_rules, "ground_transport_rules")
        require_string_mapping(self.per_diem_or_meal_rules, "per_diem_or_meal_rules")
        require_strings(self.approval_triggers, "approval_triggers")
        require_strings(self.documentation_rules, "documentation_rules")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class VendorConstraints:
    preferred_vendors: list[str] = field(default_factory=list)
    approved_vendors: list[str] = field(default_factory=list)
    disallowed_vendors: list[str] = field(default_factory=list)
    comparison_requirements: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_strings(self.preferred_vendors, "preferred_vendors")
        require_strings(self.approved_vendors, "approved_vendors")
        require_strings(self.disallowed_vendors, "disallowed_vendors")
        if any(not isinstance(key, str) or not key for key in self.comparison_requirements):
            raise ValueError("comparison_requirements must use non-empty string keys")
        for key, value in self.comparison_requirements.items():
            if value <= 0:
                raise ValueError(f"comparison_requirements[{key}] must be positive")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ScheduleRequirements:
    arrival_buffer_preference: str = "moderate"
    meeting_protection_priority: float = 0.0
    same_day_return_tolerance: float = 0.0
    red_eye_tolerance: float = 0.0

    def __post_init__(self) -> None:
        if self.arrival_buffer_preference not in schema.ARRIVAL_BUFFER_PREFERENCES:
            raise ValueError(
                "arrival_buffer_preference must be one of " f"{schema.ARRIVAL_BUFFER_PREFERENCES}"
            )
        require_probability(self.meeting_protection_priority, "meeting_protection_priority")
        require_probability(self.same_day_return_tolerance, "same_day_return_tolerance")
        require_probability(self.red_eye_tolerance, "red_eye_tolerance")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CostControls:
    overall_cost_priority: float = 0.0
    policy_compliance_priority: float = 0.0
    employee_convenience_priority: float = 0.0
    splurge_requires_justification: bool = True

    def __post_init__(self) -> None:
        require_probability(self.overall_cost_priority, "overall_cost_priority")
        require_probability(self.policy_compliance_priority, "policy_compliance_priority")
        require_probability(self.employee_convenience_priority, "employee_convenience_priority")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ComfortFloors:
    lodging_needs: list[str] = field(default_factory=list)
    transport_needs: list[str] = field(default_factory=list)
    arrival_readiness_needs: list[str] = field(default_factory=list)
    work_enablers: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_strings(self.lodging_needs, "lodging_needs")
        require_strings(self.transport_needs, "transport_needs")
        require_strings(self.arrival_readiness_needs, "arrival_readiness_needs")
        require_strings(self.work_enablers, "work_enablers")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DocumentationRequirements:
    required_receipt_categories: list[str] = field(default_factory=list)
    justification_fields: list[str] = field(default_factory=list)
    comparable_capture_required: bool = False
    booking_link_retention_required: bool = False

    def __post_init__(self) -> None:
        require_strings(self.required_receipt_categories, "required_receipt_categories")
        require_strings(self.justification_fields, "justification_fields")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ApprovalTargets:
    needs_manager_approval: bool = False
    needs_finance_review: bool = False
    needs_exception_preclearance: bool = False
    approval_roles: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_strings(self.approval_roles, "approval_roles")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ExceptionStrategy:
    fallback_mode: str = "nearest_compliant"
    require_additional_comparables: bool = False
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.fallback_mode not in schema.EXCEPTION_FALLBACK_MODES:
            raise ValueError(f"fallback_mode must be one of {schema.EXCEPTION_FALLBACK_MODES}")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BusinessTravelProfile:
    traveler_context: TravelerContext
    trip_purpose: TripPurpose
    policy_constraints: PolicyConstraints
    vendor_constraints: VendorConstraints
    schedule_requirements: ScheduleRequirements
    cost_controls: CostControls
    comfort_floors: ComfortFloors
    documentation_requirements: DocumentationRequirements
    approval_targets: ApprovalTargets
    exception_strategy: ExceptionStrategy
    schema_version: str = schema.SCHEMA_VERSION
    profile_kind: str = schema.PROFILE_KIND

    def __post_init__(self) -> None:
        if self.schema_version != schema.SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {schema.SCHEMA_VERSION!r}")
        if self.profile_kind != schema.PROFILE_KIND:
            raise ValueError(f"profile_kind must be {schema.PROFILE_KIND!r}")
        for field_name in (
            "traveler_context",
            "trip_purpose",
            "policy_constraints",
            "vendor_constraints",
            "schedule_requirements",
            "cost_controls",
            "comfort_floors",
            "documentation_requirements",
            "approval_targets",
            "exception_strategy",
        ):
            value = getattr(self, field_name)
            expected_type = {
                "traveler_context": TravelerContext,
                "trip_purpose": TripPurpose,
                "policy_constraints": PolicyConstraints,
                "vendor_constraints": VendorConstraints,
                "schedule_requirements": ScheduleRequirements,
                "cost_controls": CostControls,
                "comfort_floors": ComfortFloors,
                "documentation_requirements": DocumentationRequirements,
                "approval_targets": ApprovalTargets,
                "exception_strategy": ExceptionStrategy,
            }[field_name]
            if not isinstance(value, expected_type):
                raise ValueError(f"{field_name} must be a {expected_type.__name__}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BusinessTravelProfile":
        return cls(
            traveler_context=TravelerContext(**payload["traveler_context"]),
            trip_purpose=TripPurpose(
                purpose_type=payload["trip_purpose"]["purpose_type"],
                business_justification=payload["trip_purpose"]["business_justification"],
                required_presence_windows=[
                    RequiredPresenceWindow(**item)
                    for item in payload["trip_purpose"].get("required_presence_windows", [])
                ],
                trip_criticality=payload["trip_purpose"].get("trip_criticality", "medium"),
            ),
            policy_constraints=PolicyConstraints(**payload["policy_constraints"]),
            vendor_constraints=VendorConstraints(**payload["vendor_constraints"]),
            schedule_requirements=ScheduleRequirements(**payload["schedule_requirements"]),
            cost_controls=CostControls(**payload["cost_controls"]),
            comfort_floors=ComfortFloors(**payload["comfort_floors"]),
            documentation_requirements=DocumentationRequirements(
                **payload["documentation_requirements"]
            ),
            approval_targets=ApprovalTargets(**payload["approval_targets"]),
            exception_strategy=ExceptionStrategy(**payload["exception_strategy"]),
            schema_version=payload.get("schema_version", schema.SCHEMA_VERSION),
            profile_kind=payload.get("profile_kind", schema.PROFILE_KIND),
        )
