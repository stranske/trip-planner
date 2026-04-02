"""Canonical transport contracts for normalized option modeling."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from trip_planner._validators import (
    require_non_empty,
    require_non_negative,
    require_optional_non_empty,
    require_probability,
    require_strings,
)
from trip_planner._option_contracts import MoneyRange
from trip_planner.sources import (
    ProvenanceReference,
    QualityValueFitSummary,
    SourceTrustSignals,
)
from trip_planner.sources import schema as source_schema

SCHEMA_VERSION = "0.1.0"

TRANSPORT_KINDS: tuple[str, ...] = ("flight", "rail", "car", "ferry", "local_ground")
SEGMENT_MODES: tuple[str, ...] = (
    "flight",
    "rail",
    "car",
    "ferry",
    "bus",
    "transit",
    "walk",
    "shuttle",
)
AVAILABILITY_STATUSES: tuple[str, ...] = (
    "available",
    "limited",
    "request_only",
    "sold_out",
)
CLASS_OF_SERVICE: tuple[str, ...] = (
    "economy",
    "premium_economy",
    "business",
    "first",
    "standard",
    "comfort",
    "private",
)
TRANSPORT_KIND_ALIASES: dict[str, str] = {"rental_car": "car"}


def _require_string_list(values: Any, field_name: str) -> None:
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list of non-empty strings")
    require_strings(values, field_name)


def _optional_list_field(payload: dict[str, Any], field_name: str) -> list[Any]:
    value = payload.get(field_name, [])
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list when provided")
    return value


def _optional_mapping_field(payload: dict[str, Any], field_name: str) -> dict[str, Any]:
    value = payload.get(field_name, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a mapping when provided")
    return value


def _parse_money_range(
    payload: dict[str, Any] | None, field_name: str
) -> MoneyRange | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise ValueError(f"{field_name} must be a mapping when provided")
    return MoneyRange(**payload)


def _normalize_transport_kind(value: str) -> str:
    return TRANSPORT_KIND_ALIASES.get(value, value)


def _parse_provenance_reference(payload: dict[str, Any]) -> ProvenanceReference:
    trust_payload = payload.get("trust_snapshot")
    quality_payload = payload.get("quality_value_fit")
    return ProvenanceReference(
        provenance_id=payload["provenance_id"],
        source_id=payload["source_id"],
        source_category=payload["source_category"],
        subject_kind=payload["subject_kind"],
        subject_id=payload["subject_id"],
        contribution_kind=payload["contribution_kind"],
        summary=payload["summary"],
        locator=payload.get("locator", ""),
        captured_at=payload.get("captured_at", ""),
        freshness_days_at_capture=payload.get("freshness_days_at_capture"),
        trust_snapshot=SourceTrustSignals(**trust_payload) if trust_payload else None,
        quality_value_fit=(
            QualityValueFitSummary(**quality_payload) if quality_payload else None
        ),
        notes=_optional_list_field(payload, "notes"),
    )


@dataclass(slots=True)
class TransportTimingSummary:
    departure_local: str
    arrival_local: str
    duration_minutes: int
    departure_timezone: str = ""
    arrival_timezone: str = ""
    early_departure: bool = False
    late_arrival: bool = False
    overnight: bool = False
    day_rollover_count: int = 0
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.departure_local, "departure_local")
        require_non_empty(self.arrival_local, "arrival_local")
        require_non_negative(self.duration_minutes, "duration_minutes")
        require_optional_non_empty(
            self.departure_timezone or None, "departure_timezone"
        )
        require_optional_non_empty(self.arrival_timezone or None, "arrival_timezone")
        require_non_negative(self.day_rollover_count, "day_rollover_count")
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TransportSegment:
    segment_id: str
    mode: str
    origin_label: str
    destination_label: str
    departure_local: str = ""
    arrival_local: str = ""
    carrier: str = ""
    service_number: str = ""
    duration_minutes: int | None = None
    self_navigation_required: bool = False
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.segment_id, "segment_id")
        if self.mode not in SEGMENT_MODES:
            raise ValueError(f"mode must be one of {SEGMENT_MODES}")
        require_non_empty(self.origin_label, "origin_label")
        require_non_empty(self.destination_label, "destination_label")
        require_optional_non_empty(self.departure_local or None, "departure_local")
        require_optional_non_empty(self.arrival_local or None, "arrival_local")
        require_optional_non_empty(self.carrier or None, "carrier")
        require_optional_non_empty(self.service_number or None, "service_number")
        if self.duration_minutes is not None:
            require_non_negative(self.duration_minutes, "duration_minutes")
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TransportTransferBurden:
    transfer_count: int = 0
    self_navigation_burden_signal: float | None = None
    baggage_complexity_signal: float | None = None
    schedule_protection_signal: float | None = None
    connection_risk_signal: float | None = None
    minimum_connection_minutes: int | None = None
    transfer_summary: str = ""
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_negative(self.transfer_count, "transfer_count")
        for field_name in (
            "self_navigation_burden_signal",
            "baggage_complexity_signal",
            "schedule_protection_signal",
            "connection_risk_signal",
        ):
            value = getattr(self, field_name)
            if value is not None:
                require_probability(value, field_name)
        if self.minimum_connection_minutes is not None:
            require_non_negative(
                self.minimum_connection_minutes, "minimum_connection_minutes"
            )
        require_optional_non_empty(self.transfer_summary or None, "transfer_summary")
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TransportBookingTerms:
    booking_channel: str = ""
    refundable: bool | None = None
    changeability_summary: str = ""
    class_of_service: str = ""
    approved_channels: list[str] = field(default_factory=list)
    comparable_reference_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_optional_non_empty(self.booking_channel or None, "booking_channel")
        require_optional_non_empty(
            self.changeability_summary or None, "changeability_summary"
        )
        if self.class_of_service and self.class_of_service not in CLASS_OF_SERVICE:
            raise ValueError(f"class_of_service must be one of {CLASS_OF_SERVICE}")
        _require_string_list(self.approved_channels, "approved_channels")
        _require_string_list(self.comparable_reference_ids, "comparable_reference_ids")
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TransportCostSummary:
    total: MoneyRange | None = None
    base_fare: MoneyRange | None = None
    taxes_and_fees: MoneyRange | None = None
    ancillaries: MoneyRange | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in ("total", "base_fare", "taxes_and_fees", "ancillaries"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, MoneyRange):
                raise ValueError(f"{field_name} must be a MoneyRange when provided")
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TransportExperienceSummary:
    scenic_value_signal: float | None = None
    comfort_signal: float | None = None
    privacy_signal: float | None = None
    workability_signal: float | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in (
            "scenic_value_signal",
            "comfort_signal",
            "privacy_signal",
            "workability_signal",
        ):
            value = getattr(self, field_name)
            if value is not None:
                require_probability(value, field_name)
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TransportFitSummary:
    overall_signal: float | None = None
    schedule_fit_signal: float | None = None
    friction_fit_signal: float | None = None
    experiential_fit_signal: float | None = None
    policy_fit_signal: float | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in (
            "overall_signal",
            "schedule_fit_signal",
            "friction_fit_signal",
            "experiential_fit_signal",
            "policy_fit_signal",
        ):
            value = getattr(self, field_name)
            if value is not None:
                require_probability(value, field_name)
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TransportPolicySummary:
    business_approval_status: str = "unknown"
    approval_required: bool = False
    approved_booking_channel: bool | None = None
    class_of_service: str = ""
    policy_notes: list[str] = field(default_factory=list)
    comparable_reference_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if (
            self.business_approval_status
            not in source_schema.BUSINESS_APPROVAL_STATUSES
        ):
            raise ValueError(
                "business_approval_status must be one of "
                f"{source_schema.BUSINESS_APPROVAL_STATUSES}"
            )
        if self.class_of_service and self.class_of_service not in CLASS_OF_SERVICE:
            raise ValueError(f"class_of_service must be one of {CLASS_OF_SERVICE}")
        _require_string_list(self.policy_notes, "policy_notes")
        _require_string_list(self.comparable_reference_ids, "comparable_reference_ids")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TransportFeasibility:
    available: bool = True
    availability_status: str = "available"
    constraints: list[str] = field(default_factory=list)
    accessibility_notes: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.availability_status not in AVAILABILITY_STATUSES:
            raise ValueError(
                f"availability_status must be one of {AVAILABILITY_STATUSES}"
            )
        _require_string_list(self.constraints, "constraints")
        _require_string_list(self.accessibility_notes, "accessibility_notes")
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TransportOption:
    option_id: str
    name: str
    transport_kind: str
    origin_id: str
    destination_id: str
    timing_summary: TransportTimingSummary
    segments: list[TransportSegment]
    transfer_burden: TransportTransferBurden = field(
        default_factory=TransportTransferBurden
    )
    booking_terms: TransportBookingTerms = field(default_factory=TransportBookingTerms)
    cost_summary: TransportCostSummary = field(default_factory=TransportCostSummary)
    experience_summary: TransportExperienceSummary = field(
        default_factory=TransportExperienceSummary
    )
    fit_summary: TransportFitSummary = field(default_factory=TransportFitSummary)
    policy_summary: TransportPolicySummary = field(
        default_factory=TransportPolicySummary
    )
    feasibility: TransportFeasibility = field(default_factory=TransportFeasibility)
    summary: str = ""
    booking_links: list[str] = field(default_factory=list)
    source_refs: list[ProvenanceReference] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_non_empty(self.option_id, "option_id")
        require_non_empty(self.name, "name")
        require_non_empty(self.origin_id, "origin_id")
        require_non_empty(self.destination_id, "destination_id")
        object.__setattr__(
            self, "transport_kind", _normalize_transport_kind(self.transport_kind)
        )
        if self.transport_kind not in TRANSPORT_KINDS:
            raise ValueError(f"transport_kind must be one of {TRANSPORT_KINDS}")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")
        if not isinstance(self.timing_summary, TransportTimingSummary):
            raise ValueError("timing_summary must be a TransportTimingSummary")
        if not self.segments:
            raise ValueError("segments must contain at least one TransportSegment")
        if any(not isinstance(item, TransportSegment) for item in self.segments):
            raise ValueError("segments must contain TransportSegment instances")
        if not isinstance(self.transfer_burden, TransportTransferBurden):
            raise ValueError("transfer_burden must be a TransportTransferBurden")
        if not isinstance(self.booking_terms, TransportBookingTerms):
            raise ValueError("booking_terms must be a TransportBookingTerms")
        if not isinstance(self.cost_summary, TransportCostSummary):
            raise ValueError("cost_summary must be a TransportCostSummary")
        if not isinstance(self.experience_summary, TransportExperienceSummary):
            raise ValueError("experience_summary must be a TransportExperienceSummary")
        if not isinstance(self.fit_summary, TransportFitSummary):
            raise ValueError("fit_summary must be a TransportFitSummary")
        if not isinstance(self.policy_summary, TransportPolicySummary):
            raise ValueError("policy_summary must be a TransportPolicySummary")
        if not isinstance(self.feasibility, TransportFeasibility):
            raise ValueError("feasibility must be a TransportFeasibility")
        _require_string_list(self.booking_links, "booking_links")
        if any(not isinstance(item, ProvenanceReference) for item in self.source_refs):
            raise ValueError("source_refs must contain ProvenanceReference instances")
        _require_string_list(self.tags, "tags")
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TransportOption":
        cost_payload = _optional_mapping_field(payload, "cost_summary")
        return cls(
            option_id=payload["option_id"],
            name=payload["name"],
            transport_kind=_normalize_transport_kind(payload["transport_kind"]),
            origin_id=payload["origin_id"],
            destination_id=payload["destination_id"],
            timing_summary=TransportTimingSummary(**payload["timing_summary"]),
            segments=[TransportSegment(**item) for item in payload["segments"]],
            transfer_burden=TransportTransferBurden(
                **_optional_mapping_field(payload, "transfer_burden")
            ),
            booking_terms=TransportBookingTerms(
                **_optional_mapping_field(payload, "booking_terms")
            ),
            cost_summary=TransportCostSummary(
                total=_parse_money_range(
                    cost_payload.get("total"), "cost_summary.total"
                ),
                base_fare=_parse_money_range(
                    cost_payload.get("base_fare"),
                    "cost_summary.base_fare",
                ),
                taxes_and_fees=_parse_money_range(
                    cost_payload.get("taxes_and_fees"),
                    "cost_summary.taxes_and_fees",
                ),
                ancillaries=_parse_money_range(
                    cost_payload.get("ancillaries"),
                    "cost_summary.ancillaries",
                ),
                notes=cost_payload.get("notes", []),
            ),
            experience_summary=TransportExperienceSummary(
                **_optional_mapping_field(payload, "experience_summary")
            ),
            fit_summary=TransportFitSummary(
                **_optional_mapping_field(payload, "fit_summary")
            ),
            policy_summary=TransportPolicySummary(
                **_optional_mapping_field(payload, "policy_summary")
            ),
            feasibility=TransportFeasibility(
                **_optional_mapping_field(payload, "feasibility")
            ),
            summary=payload.get("summary", ""),
            booking_links=_optional_list_field(payload, "booking_links"),
            source_refs=[
                _parse_provenance_reference(item)
                for item in _optional_list_field(payload, "source_refs")
            ],
            tags=_optional_list_field(payload, "tags"),
            notes=_optional_list_field(payload, "notes"),
            schema_version=payload.get("schema_version", SCHEMA_VERSION),
        )
