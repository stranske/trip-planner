"""Canonical source and source-signal contracts."""

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

from . import schema


@dataclass(slots=True)
class SourceTrustSignals:
    freshness_days: int | None = None
    freshness_confidence: float | None = None
    commerciality: float | None = None
    editorial_independence: float | None = None
    operational_reliability: float | None = None
    review_consistency: float | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.freshness_days is not None:
            require_non_negative(self.freshness_days, "freshness_days")
        for field_name in (
            "freshness_confidence",
            "commerciality",
            "editorial_independence",
            "operational_reliability",
            "review_consistency",
        ):
            value = getattr(self, field_name)
            if value is not None:
                require_probability(value, field_name)
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class QualityValueFitSummary:
    quality_signal: float | None = None
    value_signal: float | None = None
    fit_signal: float | None = None
    confidence: float | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in ("quality_signal", "value_signal", "fit_signal", "confidence"):
            value = getattr(self, field_name)
            if value is not None:
                require_probability(value, field_name)
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SourceRecord:
    source_id: str
    provider_name: str
    display_name: str
    category: str
    coverage_scope: str = "global"
    supported_option_kinds: list[str] = field(default_factory=list)
    coverage_regions: list[str] = field(default_factory=list)
    base_url: str = ""
    default_locale: str = ""
    trust_signals: SourceTrustSignals = field(default_factory=SourceTrustSignals)
    quality_summary: QualityValueFitSummary = field(default_factory=QualityValueFitSummary)
    business_approval_status: str = "unknown"
    business_approval_notes: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    schema_version: str = schema.SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_non_empty(self.source_id, "source_id")
        require_non_empty(self.provider_name, "provider_name")
        require_non_empty(self.display_name, "display_name")
        if self.category not in schema.SOURCE_CATEGORIES:
            raise ValueError(f"category must be one of {schema.SOURCE_CATEGORIES}")
        if self.coverage_scope not in schema.COVERAGE_SCOPES:
            raise ValueError(f"coverage_scope must be one of {schema.COVERAGE_SCOPES}")
        if self.schema_version != schema.SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {schema.SCHEMA_VERSION!r}")
        require_optional_non_empty(self.base_url or None, "base_url")
        require_optional_non_empty(self.default_locale or None, "default_locale")
        require_strings(self.coverage_regions, "coverage_regions")
        require_strings(self.business_approval_notes, "business_approval_notes")
        require_strings(self.notes, "notes")
        for kind in self.supported_option_kinds:
            if kind not in schema.SOURCE_OPTION_KINDS:
                raise ValueError(
                    "supported_option_kinds must contain only "
                    f"{schema.SOURCE_OPTION_KINDS!r} members"
                )
        if not isinstance(self.trust_signals, SourceTrustSignals):
            raise ValueError("trust_signals must be a SourceTrustSignals")
        if not isinstance(self.quality_summary, QualityValueFitSummary):
            raise ValueError("quality_summary must be a QualityValueFitSummary")
        if self.business_approval_status not in schema.BUSINESS_APPROVAL_STATUSES:
            raise ValueError(
                "business_approval_status must be one of " f"{schema.BUSINESS_APPROVAL_STATUSES}"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
