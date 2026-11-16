"""Candidate-generation contracts between ingestion and later ranking."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from trip_planner._validators import (
    require_non_empty,
    require_non_negative,
    require_strings,
)
from trip_planner.contracts.options import (
    OPTION_SET_PURPOSES,
    ComparisonAxis,
    MoneyRange,
    Option,
    OptionCostSummary,
    OptionQualitySummary,
    OptionSet,
)
from trip_planner.options import InventoryBundle
from trip_planner.options.bundles import _dedupe_strings

SCHEMA_VERSION = "0.1.0"
CANDIDATE_FILTER_REASON_CODES: tuple[str, ...] = (
    "missing_destination",
    "unavailable",
    "stale_source",
    "policy_channel",
    "policy_rate_cap",
    "policy_approval",
)


def _optional_money_range(total: MoneyRange | None) -> dict[str, Any] | None:
    return total.to_dict() if total is not None else None


@dataclass(slots=True)
class CandidateExclusion:
    option_id: str
    option_kind: str
    reason_code: str
    message: str
    destination_ids: list[str] = field(default_factory=list)
    source_ref_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.option_id, "option_id")
        require_non_empty(self.option_kind, "option_kind")
        if self.reason_code not in CANDIDATE_FILTER_REASON_CODES:
            raise ValueError(f"reason_code must be one of {CANDIDATE_FILTER_REASON_CODES}")
        require_non_empty(self.message, "message")
        require_strings(self.destination_ids, "destination_ids")
        require_strings(self.source_ref_ids, "source_ref_ids")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CandidateSeed:
    candidate_id: str
    bundle: InventoryBundle
    supported_purposes: list[str] = field(default_factory=list)
    inclusion_reasons: list[str] = field(default_factory=list)
    unresolved_risks: list[str] = field(default_factory=list)
    policy_ready: bool = False
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.candidate_id, "candidate_id")
        if not isinstance(self.bundle, InventoryBundle):
            raise ValueError("bundle must be an InventoryBundle")
        require_strings(self.supported_purposes, "supported_purposes")
        invalid = [item for item in self.supported_purposes if item not in OPTION_SET_PURPOSES]
        if invalid:
            raise ValueError(f"supported_purposes must contain only {OPTION_SET_PURPOSES}")
        require_strings(self.inclusion_reasons, "inclusion_reasons")
        require_strings(self.unresolved_risks, "unresolved_risks")
        require_strings(self.notes, "notes")

    def estimated_total(self) -> MoneyRange | None:
        currency: str | None = None
        total = 0.0
        seen = False
        for lodging_option in self.bundle.lodging_options:
            nightly = lodging_option.cost_summary.total or lodging_option.cost_summary.nightly
            if nightly is None or nightly.typical_amount is None:
                continue
            currency = currency or nightly.currency
            if nightly.currency != currency:
                return None
            total += nightly.typical_amount
            seen = True
        for transport_option in self.bundle.transport_options:
            amount = transport_option.cost_summary.total
            if amount is None or amount.typical_amount is None:
                continue
            currency = currency or amount.currency
            if amount.currency != currency:
                return None
            total += amount.typical_amount
            seen = True
        for activity_option in self.bundle.activity_options:
            amount = activity_option.cost_summary.total or activity_option.cost_summary.per_person
            if amount is None or amount.typical_amount is None:
                continue
            currency = currency or amount.currency
            if amount.currency != currency:
                return None
            total += amount.typical_amount
            seen = True
        if not seen:
            return None
        return MoneyRange(currency=currency or "USD", typical_amount=round(total, 2))

    def to_option(self) -> Option:
        explanation = _dedupe_strings(
            self.inclusion_reasons
            + self.bundle.explanation.strengths
            + self.bundle.explanation.evidence
            + self.notes
        )
        return Option(
            option_id=self.candidate_id,
            kind="mixed",
            label=self.bundle.title,
            summary=self.bundle.summary,
            fit_signals={
                key: value
                for key, value in {
                    "quality": self.bundle.quality_value_fit.quality_signal,
                    "value": self.bundle.quality_value_fit.value_signal,
                    "fit": self.bundle.quality_value_fit.fit_signal,
                }.items()
                if value is not None
            },
            cost_summary=OptionCostSummary(total=self.estimated_total()),
            quality_summary=OptionQualitySummary(
                quality_signal=self.bundle.quality_value_fit.quality_signal,
                value_signal=self.bundle.quality_value_fit.value_signal,
                fit_signal=self.bundle.quality_value_fit.fit_signal,
            ),
            drawbacks=_dedupe_strings(
                self.bundle.explanation.tradeoffs
                + self.unresolved_risks
                + self.bundle.feasibility.blocking_reasons
            ),
            booking_links=self.bundle.provenance_summary.booking_links,
            source_refs=self.bundle.provenance_summary.source_refs,
            supporting_place_ids=self.bundle.destination_ids,
            explanation=explanation,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "bundle": self.bundle.to_dict(),
            "supported_purposes": list(self.supported_purposes),
            "inclusion_reasons": list(self.inclusion_reasons),
            "unresolved_risks": list(self.unresolved_risks),
            "policy_ready": self.policy_ready,
            "notes": list(self.notes),
            "estimated_total": _optional_money_range(self.estimated_total()),
        }


@dataclass(slots=True)
class CandidateFilterSummary:
    total_destinations: int = 0
    total_lodging_options: int = 0
    total_transport_options: int = 0
    total_activity_options: int = 0
    included_bundle_count: int = 0
    excluded_option_count: int = 0
    freshness_exclusion_count: int = 0
    policy_exclusion_count: int = 0
    availability_exclusion_count: int = 0
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in (
            "total_destinations",
            "total_lodging_options",
            "total_transport_options",
            "total_activity_options",
            "included_bundle_count",
            "excluded_option_count",
            "freshness_exclusion_count",
            "policy_exclusion_count",
            "availability_exclusion_count",
        ):
            require_non_negative(getattr(self, field_name), field_name)
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CandidateSet:
    candidate_set_id: str
    trip_id: str
    purpose: str
    seeds: list[CandidateSeed]
    exclusions: list[CandidateExclusion] = field(default_factory=list)
    filter_summary: CandidateFilterSummary = field(default_factory=CandidateFilterSummary)
    comparison_axes: list[ComparisonAxis] = field(default_factory=list)
    explanation: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    selection_limit: int | None = None
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_non_empty(self.candidate_set_id, "candidate_set_id")
        require_non_empty(self.trip_id, "trip_id")
        if self.purpose not in OPTION_SET_PURPOSES:
            raise ValueError(f"purpose must be one of {OPTION_SET_PURPOSES}")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")
        if not self.seeds:
            raise ValueError("seeds must contain at least one CandidateSeed")
        if any(not isinstance(item, CandidateSeed) for item in self.seeds):
            raise ValueError("seeds must contain CandidateSeed instances")
        if any(not isinstance(item, CandidateExclusion) for item in self.exclusions):
            raise ValueError("exclusions must contain CandidateExclusion instances")
        if not isinstance(self.filter_summary, CandidateFilterSummary):
            raise ValueError("filter_summary must be a CandidateFilterSummary")
        if any(not isinstance(item, ComparisonAxis) for item in self.comparison_axes):
            raise ValueError("comparison_axes must contain ComparisonAxis instances")
        require_strings(self.explanation, "explanation")
        require_strings(self.source_refs, "source_refs")
        if self.selection_limit is not None:
            if self.selection_limit <= 0:
                raise ValueError("selection_limit must be positive when provided")
            if self.selection_limit > len(self.seeds):
                raise ValueError("selection_limit cannot exceed the number of seeds")

    def to_option_set(self) -> OptionSet:
        return OptionSet(
            option_set_id=self.candidate_set_id,
            trip_id=self.trip_id,
            purpose=self.purpose,
            scope="mixed",
            title="Early candidate set",
            options=[seed.to_option() for seed in self.seeds],
            comparison_axes=self.comparison_axes,
            explanation=self.explanation,
            source_refs=self.source_refs,
            selection_limit=self.selection_limit,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_set_id": self.candidate_set_id,
            "trip_id": self.trip_id,
            "purpose": self.purpose,
            "seeds": [item.to_dict() for item in self.seeds],
            "exclusions": [item.to_dict() for item in self.exclusions],
            "filter_summary": self.filter_summary.to_dict(),
            "comparison_axes": [item.to_dict() for item in self.comparison_axes],
            "explanation": list(self.explanation),
            "source_refs": list(self.source_refs),
            "selection_limit": self.selection_limit,
            "schema_version": self.schema_version,
        }
