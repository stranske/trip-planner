"""Canonical lodging contracts for normalized option modeling."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from trip_planner._option_contracts import MoneyRange
from trip_planner._validators import (
    require_non_empty,
    require_non_negative,
    require_optional_non_empty,
    require_probability,
    require_strings,
)
from trip_planner.sources import (
    ProvenanceReference,
    QualityValueFitSummary,
    SourceTrustSignals,
)
from trip_planner.sources import schema as source_schema

SCHEMA_VERSION = "0.1.0"

LODGING_KINDS: tuple[str, ...] = (
    "hotel",
    "aparthotel",
    "apartment",
    "vacation_rental",
    "guesthouse",
    "hostel",
    "resort",
)
LOCATION_CONTEXTS: tuple[str, ...] = (
    "urban_core",
    "inner_neighborhood",
    "outer_neighborhood",
    "airport",
    "resort_area",
)
INVENTORY_STATUSES: tuple[str, ...] = (
    "available",
    "limited",
    "request_only",
    "sold_out",
)


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


def _parse_money_range(payload: dict[str, Any] | None, field_name: str) -> MoneyRange | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise ValueError(f"{field_name} must be a mapping when provided")
    return MoneyRange(**payload)


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
        quality_value_fit=(QualityValueFitSummary(**quality_payload) if quality_payload else None),
        notes=_optional_list_field(payload, "notes"),
    )


@dataclass(slots=True)
class LodgingLocationSummary:
    destination_id: str
    location_context: str
    neighborhood: str = ""
    address_hint: str = ""
    access_summary: str = ""
    walk_minutes_to_anchor: int | None = None
    transit_minutes_to_anchor: int | None = None
    quiet_signal: float | None = None
    recovery_signal: float | None = None
    business_access_signal: float | None = None
    place_context_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.destination_id, "destination_id")
        if self.location_context not in LOCATION_CONTEXTS:
            raise ValueError(f"location_context must be one of {LOCATION_CONTEXTS}")
        require_optional_non_empty(self.neighborhood or None, "neighborhood")
        require_optional_non_empty(self.address_hint or None, "address_hint")
        require_optional_non_empty(self.access_summary or None, "access_summary")
        for field_name in ("walk_minutes_to_anchor", "transit_minutes_to_anchor"):
            value = getattr(self, field_name)
            if value is not None:
                require_non_negative(value, field_name)
        for field_name in ("quiet_signal", "recovery_signal", "business_access_signal"):
            value = getattr(self, field_name)
            if value is not None:
                require_probability(value, field_name)
        _require_string_list(self.place_context_ids, "place_context_ids")
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LodgingRoomSummary:
    lodging_kind: str
    room_type: str = ""
    bed_configuration: str = ""
    workspace_signal: float | None = None
    comfort_signal: float | None = None
    cleanliness_signal: float | None = None
    privacy_signal: float | None = None
    amenities: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.lodging_kind not in LODGING_KINDS:
            raise ValueError(f"lodging_kind must be one of {LODGING_KINDS}")
        require_optional_non_empty(self.room_type or None, "room_type")
        require_optional_non_empty(self.bed_configuration or None, "bed_configuration")
        for field_name in (
            "workspace_signal",
            "comfort_signal",
            "cleanliness_signal",
            "privacy_signal",
        ):
            value = getattr(self, field_name)
            if value is not None:
                require_probability(value, field_name)
        _require_string_list(self.amenities, "amenities")
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LodgingBookingTerms:
    cancellation_summary: str = ""
    refundable: bool | None = None
    prepayment_required: bool = False
    min_stay_nights: int | None = None
    booking_channel: str = ""
    checkin_window: str = ""
    checkout_window: str = ""
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_optional_non_empty(self.cancellation_summary or None, "cancellation_summary")
        if self.min_stay_nights is not None:
            if not isinstance(self.min_stay_nights, int) or self.min_stay_nights < 1:
                raise ValueError("min_stay_nights must be a positive integer when provided")
        require_optional_non_empty(self.booking_channel or None, "booking_channel")
        require_optional_non_empty(self.checkin_window or None, "checkin_window")
        require_optional_non_empty(self.checkout_window or None, "checkout_window")
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LodgingCostSummary:
    nightly: MoneyRange | None = None
    total: MoneyRange | None = None
    taxes_and_fees: MoneyRange | None = None
    deposit: MoneyRange | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in ("nightly", "total", "taxes_and_fees", "deposit"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, MoneyRange):
                raise ValueError(f"{field_name} must be a MoneyRange when provided")
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LodgingQualitySummary:
    overall_signal: float | None = None
    sleep_quality_signal: float | None = None
    property_condition_signal: float | None = None
    service_signal: float | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in (
            "overall_signal",
            "sleep_quality_signal",
            "property_condition_signal",
            "service_signal",
        ):
            value = getattr(self, field_name)
            if value is not None:
                require_probability(value, field_name)
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LodgingValueSummary:
    overall_signal: float | None = None
    location_value_signal: float | None = None
    space_value_signal: float | None = None
    policy_value_signal: float | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in (
            "overall_signal",
            "location_value_signal",
            "space_value_signal",
            "policy_value_signal",
        ):
            value = getattr(self, field_name)
            if value is not None:
                require_probability(value, field_name)
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LodgingFitSummary:
    overall_signal: float | None = None
    quiet_recovery_signal: float | None = None
    location_fit_signal: float | None = None
    traveler_style_signal: float | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in (
            "overall_signal",
            "quiet_recovery_signal",
            "location_fit_signal",
            "traveler_style_signal",
        ):
            value = getattr(self, field_name)
            if value is not None:
                require_probability(value, field_name)
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LodgingFeasibility:
    inventory_status: str = "available"
    available: bool = True
    business_approval_status: str = "unknown"
    requires_manual_approval: bool = False
    accessibility_notes: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.inventory_status not in INVENTORY_STATUSES:
            raise ValueError(f"inventory_status must be one of {INVENTORY_STATUSES}")
        if self.business_approval_status not in source_schema.BUSINESS_APPROVAL_STATUSES:
            raise ValueError(
                "business_approval_status must be one of "
                f"{source_schema.BUSINESS_APPROVAL_STATUSES}"
            )
        _require_string_list(self.accessibility_notes, "accessibility_notes")
        _require_string_list(self.constraints, "constraints")
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LodgingOption:
    option_id: str
    name: str
    destination_id: str
    location_summary: LodgingLocationSummary
    room_summary: LodgingRoomSummary
    booking_terms: LodgingBookingTerms = field(default_factory=LodgingBookingTerms)
    cost_summary: LodgingCostSummary = field(default_factory=LodgingCostSummary)
    quality_summary: LodgingQualitySummary = field(default_factory=LodgingQualitySummary)
    value_summary: LodgingValueSummary = field(default_factory=LodgingValueSummary)
    fit_summary: LodgingFitSummary = field(default_factory=LodgingFitSummary)
    feasibility: LodgingFeasibility = field(default_factory=LodgingFeasibility)
    summary: str = ""
    booking_links: list[str] = field(default_factory=list)
    source_refs: list[ProvenanceReference] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_non_empty(self.option_id, "option_id")
        require_non_empty(self.name, "name")
        require_non_empty(self.destination_id, "destination_id")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")
        if not isinstance(self.location_summary, LodgingLocationSummary):
            raise ValueError("location_summary must be a LodgingLocationSummary")
        if self.location_summary.destination_id != self.destination_id:
            raise ValueError(
                "destination_id on LodgingOption must match " "location_summary.destination_id"
            )
        if not isinstance(self.room_summary, LodgingRoomSummary):
            raise ValueError("room_summary must be a LodgingRoomSummary")
        if not isinstance(self.booking_terms, LodgingBookingTerms):
            raise ValueError("booking_terms must be a LodgingBookingTerms")
        if not isinstance(self.cost_summary, LodgingCostSummary):
            raise ValueError("cost_summary must be a LodgingCostSummary")
        if not isinstance(self.quality_summary, LodgingQualitySummary):
            raise ValueError("quality_summary must be a LodgingQualitySummary")
        if not isinstance(self.value_summary, LodgingValueSummary):
            raise ValueError("value_summary must be a LodgingValueSummary")
        if not isinstance(self.fit_summary, LodgingFitSummary):
            raise ValueError("fit_summary must be a LodgingFitSummary")
        if not isinstance(self.feasibility, LodgingFeasibility):
            raise ValueError("feasibility must be a LodgingFeasibility")
        _require_string_list(self.booking_links, "booking_links")
        if any(not isinstance(item, ProvenanceReference) for item in self.source_refs):
            raise ValueError("source_refs must contain ProvenanceReference instances")
        _require_string_list(self.tags, "tags")
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LodgingOption":
        cost_payload = _optional_mapping_field(payload, "cost_summary")
        return cls(
            option_id=payload["option_id"],
            name=payload["name"],
            destination_id=payload["destination_id"],
            location_summary=LodgingLocationSummary(**payload["location_summary"]),
            room_summary=LodgingRoomSummary(**payload["room_summary"]),
            booking_terms=LodgingBookingTerms(**_optional_mapping_field(payload, "booking_terms")),
            cost_summary=LodgingCostSummary(
                nightly=_parse_money_range(
                    cost_payload.get("nightly"),
                    "cost_summary.nightly",
                ),
                total=_parse_money_range(
                    cost_payload.get("total"),
                    "cost_summary.total",
                ),
                taxes_and_fees=_parse_money_range(
                    cost_payload.get("taxes_and_fees"),
                    "cost_summary.taxes_and_fees",
                ),
                deposit=_parse_money_range(
                    cost_payload.get("deposit"),
                    "cost_summary.deposit",
                ),
                notes=cost_payload.get("notes", []),
            ),
            quality_summary=LodgingQualitySummary(
                **_optional_mapping_field(payload, "quality_summary")
            ),
            value_summary=LodgingValueSummary(**_optional_mapping_field(payload, "value_summary")),
            fit_summary=LodgingFitSummary(**_optional_mapping_field(payload, "fit_summary")),
            feasibility=LodgingFeasibility(**_optional_mapping_field(payload, "feasibility")),
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
