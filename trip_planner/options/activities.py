"""Canonical activity contracts for normalized option modeling."""

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

SCHEMA_VERSION = "0.1.0"

ACTIVITY_KINDS: tuple[str, ...] = (
    "museum",
    "landscape",
    "district",
    "event",
    "tour",
    "dining",
    "wellness",
    "mixed",
)
ACTIVITY_FORMATS: tuple[str, ...] = (
    "open_ended",
    "ticketed",
    "reservation_required",
    "timed_entry",
    "drop_in",
)
EFFORT_LEVELS: tuple[str, ...] = ("low", "moderate", "high")
AVAILABILITY_STATUSES: tuple[str, ...] = (
    "available",
    "limited",
    "request_only",
    "sold_out",
    "seasonal",
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


def _parse_money_range(
    payload: dict[str, Any] | None, field_name: str
) -> MoneyRange | None:
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
        quality_value_fit=QualityValueFitSummary(**quality_payload)
        if quality_payload
        else None,
        notes=_optional_list_field(payload, "notes"),
    )


@dataclass(slots=True)
class ActivityCategory:
    primary: str
    secondary: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    open_ended: bool = False

    def __post_init__(self) -> None:
        require_non_empty(self.primary, "primary")
        _require_string_list(self.secondary, "secondary")
        _require_string_list(self.tags, "tags")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ActivityTimingSummary:
    duration_minutes: int
    typical_start_window: str = ""
    timing_sensitivity_signal: float | None = None
    closure_risk_signal: float | None = None
    crowd_pressure_signal: float | None = None
    weather_dependency_signal: float | None = None
    daylight_dependency: bool = False
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_negative(self.duration_minutes, "duration_minutes")
        require_optional_non_empty(
            self.typical_start_window or None, "typical_start_window"
        )
        for field_name in (
            "timing_sensitivity_signal",
            "closure_risk_signal",
            "crowd_pressure_signal",
            "weather_dependency_signal",
        ):
            value = getattr(self, field_name)
            if value is not None:
                require_probability(value, field_name)
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ActivitySignificanceSummary:
    overall_signal: float | None = None
    local_icon_signal: float | None = None
    cultural_signal: float | None = None
    scenic_signal: float | None = None
    anchor_worthy: bool = False
    optional: bool = False
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in (
            "overall_signal",
            "local_icon_signal",
            "cultural_signal",
            "scenic_signal",
        ):
            value = getattr(self, field_name)
            if value is not None:
                require_probability(value, field_name)
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ActivityEffortSummary:
    effort_level: str = "low"
    walking_minutes: int | None = None
    standing_minutes: int | None = None
    intensity_signal: float | None = None
    sensory_load_signal: float | None = None
    family_flexibility_signal: float | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.effort_level not in EFFORT_LEVELS:
            raise ValueError(f"effort_level must be one of {EFFORT_LEVELS}")
        for field_name in ("walking_minutes", "standing_minutes"):
            value = getattr(self, field_name)
            if value is not None:
                require_non_negative(value, field_name)
        for field_name in (
            "intensity_signal",
            "sensory_load_signal",
            "family_flexibility_signal",
        ):
            value = getattr(self, field_name)
            if value is not None:
                require_probability(value, field_name)
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ActivityBookingTerms:
    activity_format: str = "drop_in"
    booking_required: bool = False
    ticketed: bool = False
    cancellation_summary: str = ""
    booking_channel: str = ""
    reservation_cutoff: str = ""
    approved_channels: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.activity_format not in ACTIVITY_FORMATS:
            raise ValueError(f"activity_format must be one of {ACTIVITY_FORMATS}")
        require_optional_non_empty(
            self.cancellation_summary or None, "cancellation_summary"
        )
        require_optional_non_empty(self.booking_channel or None, "booking_channel")
        require_optional_non_empty(
            self.reservation_cutoff or None, "reservation_cutoff"
        )
        _require_string_list(self.approved_channels, "approved_channels")
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ActivityCostSummary:
    total: MoneyRange | None = None
    per_person: MoneyRange | None = None
    extras: MoneyRange | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in ("total", "per_person", "extras"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, MoneyRange):
                raise ValueError(f"{field_name} must be a MoneyRange when provided")
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ActivityQualitySummary:
    overall_signal: float | None = None
    content_quality_signal: float | None = None
    hospitality_signal: float | None = None
    maintenance_signal: float | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in (
            "overall_signal",
            "content_quality_signal",
            "hospitality_signal",
            "maintenance_signal",
        ):
            value = getattr(self, field_name)
            if value is not None:
                require_probability(value, field_name)
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ActivityValueSummary:
    overall_signal: float | None = None
    uniqueness_signal: float | None = None
    time_value_signal: float | None = None
    cost_value_signal: float | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in (
            "overall_signal",
            "uniqueness_signal",
            "time_value_signal",
            "cost_value_signal",
        ):
            value = getattr(self, field_name)
            if value is not None:
                require_probability(value, field_name)
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ActivityFitSummary:
    overall_signal: float | None = None
    traveler_fit_signal: float | None = None
    pacing_fit_signal: float | None = None
    weather_fit_signal: float | None = None
    group_fit_signal: float | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in (
            "overall_signal",
            "traveler_fit_signal",
            "pacing_fit_signal",
            "weather_fit_signal",
            "group_fit_signal",
        ):
            value = getattr(self, field_name)
            if value is not None:
                require_probability(value, field_name)
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ActivityFeasibility:
    available: bool = True
    availability_status: str = "available"
    seasonality_summary: str = ""
    requires_daylight: bool = False
    indoor_outdoor: str = ""
    constraints: list[str] = field(default_factory=list)
    accessibility_notes: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.availability_status not in AVAILABILITY_STATUSES:
            raise ValueError(
                f"availability_status must be one of {AVAILABILITY_STATUSES}"
            )
        require_optional_non_empty(
            self.seasonality_summary or None, "seasonality_summary"
        )
        require_optional_non_empty(self.indoor_outdoor or None, "indoor_outdoor")
        _require_string_list(self.constraints, "constraints")
        _require_string_list(self.accessibility_notes, "accessibility_notes")
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ActivityOption:
    option_id: str
    name: str
    activity_kind: str
    destination_id: str
    place_id: str
    category: ActivityCategory
    timing_summary: ActivityTimingSummary
    significance_summary: ActivitySignificanceSummary = field(
        default_factory=ActivitySignificanceSummary
    )
    effort_summary: ActivityEffortSummary = field(default_factory=ActivityEffortSummary)
    booking_terms: ActivityBookingTerms = field(default_factory=ActivityBookingTerms)
    cost_summary: ActivityCostSummary = field(default_factory=ActivityCostSummary)
    quality_summary: ActivityQualitySummary = field(
        default_factory=ActivityQualitySummary
    )
    value_summary: ActivityValueSummary = field(default_factory=ActivityValueSummary)
    fit_summary: ActivityFitSummary = field(default_factory=ActivityFitSummary)
    feasibility: ActivityFeasibility = field(default_factory=ActivityFeasibility)
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
        require_non_empty(self.place_id, "place_id")
        if self.activity_kind not in ACTIVITY_KINDS:
            raise ValueError(f"activity_kind must be one of {ACTIVITY_KINDS}")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")
        if not isinstance(self.category, ActivityCategory):
            raise ValueError("category must be an ActivityCategory")
        if not isinstance(self.timing_summary, ActivityTimingSummary):
            raise ValueError("timing_summary must be an ActivityTimingSummary")
        if not isinstance(self.significance_summary, ActivitySignificanceSummary):
            raise ValueError(
                "significance_summary must be an ActivitySignificanceSummary"
            )
        if not isinstance(self.effort_summary, ActivityEffortSummary):
            raise ValueError("effort_summary must be an ActivityEffortSummary")
        if not isinstance(self.booking_terms, ActivityBookingTerms):
            raise ValueError("booking_terms must be an ActivityBookingTerms")
        if not isinstance(self.cost_summary, ActivityCostSummary):
            raise ValueError("cost_summary must be an ActivityCostSummary")
        if not isinstance(self.quality_summary, ActivityQualitySummary):
            raise ValueError("quality_summary must be an ActivityQualitySummary")
        if not isinstance(self.value_summary, ActivityValueSummary):
            raise ValueError("value_summary must be an ActivityValueSummary")
        if not isinstance(self.fit_summary, ActivityFitSummary):
            raise ValueError("fit_summary must be an ActivityFitSummary")
        if not isinstance(self.feasibility, ActivityFeasibility):
            raise ValueError("feasibility must be an ActivityFeasibility")
        _require_string_list(self.booking_links, "booking_links")
        if any(not isinstance(item, ProvenanceReference) for item in self.source_refs):
            raise ValueError("source_refs must contain ProvenanceReference instances")
        _require_string_list(self.tags, "tags")
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ActivityOption":
        cost_payload = _optional_mapping_field(payload, "cost_summary")
        return cls(
            option_id=payload["option_id"],
            name=payload["name"],
            activity_kind=payload["activity_kind"],
            destination_id=payload["destination_id"],
            place_id=payload["place_id"],
            category=ActivityCategory(**payload["category"]),
            timing_summary=ActivityTimingSummary(**payload["timing_summary"]),
            significance_summary=ActivitySignificanceSummary(
                **_optional_mapping_field(payload, "significance_summary")
            ),
            effort_summary=ActivityEffortSummary(
                **_optional_mapping_field(payload, "effort_summary")
            ),
            booking_terms=ActivityBookingTerms(
                **_optional_mapping_field(payload, "booking_terms")
            ),
            cost_summary=ActivityCostSummary(
                total=_parse_money_range(
                    cost_payload.get("total"), "cost_summary.total"
                ),
                per_person=_parse_money_range(
                    cost_payload.get("per_person"),
                    "cost_summary.per_person",
                ),
                extras=_parse_money_range(
                    cost_payload.get("extras"), "cost_summary.extras"
                ),
                notes=cost_payload.get("notes", []),
            ),
            quality_summary=ActivityQualitySummary(
                **_optional_mapping_field(payload, "quality_summary")
            ),
            value_summary=ActivityValueSummary(
                **_optional_mapping_field(payload, "value_summary")
            ),
            fit_summary=ActivityFitSummary(
                **_optional_mapping_field(payload, "fit_summary")
            ),
            feasibility=ActivityFeasibility(
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
