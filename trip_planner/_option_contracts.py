"""Shared option primitives used by contracts and normalized option models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from trip_planner._validators import (
    require_float_mapping,
    require_non_empty,
    require_non_negative,
    require_probability,
    require_strings,
)

OPTION_SET_PURPOSES: tuple[str, ...] = (
    "profile_learning",
    "inventory_narrowing",
    "final_selection",
    "policy_comparison",
)
OPTION_SET_SCOPES: tuple[str, ...] = (
    "route",
    "lodging",
    "transport",
    "activity",
    "mixed",
)
OPTION_KINDS: tuple[str, ...] = (
    "route",
    "lodging",
    "flight",
    "rail",
    "car",
    "activity",
    "mixed",
)
COMPARISON_DIRECTIONS: tuple[str, ...] = ("higher_better", "lower_better", "contextual")


@dataclass(slots=True)
class MoneyRange:
    currency: str = "USD"
    typical_amount: float | None = None
    min_amount: float | None = None
    max_amount: float | None = None

    def __post_init__(self) -> None:
        require_non_empty(self.currency, "currency")
        for field_name in ("typical_amount", "min_amount", "max_amount"):
            value = getattr(self, field_name)
            if value is not None:
                require_non_negative(value, field_name)
        if (
            self.min_amount is not None
            and self.max_amount is not None
            and self.min_amount > self.max_amount
        ):
            raise ValueError("min_amount cannot exceed max_amount")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class OptionCostSummary:
    total: MoneyRange | None = None
    per_unit: MoneyRange | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.total is not None and not isinstance(self.total, MoneyRange):
            raise ValueError("total must be a MoneyRange when provided")
        if self.per_unit is not None and not isinstance(self.per_unit, MoneyRange):
            raise ValueError("per_unit must be a MoneyRange when provided")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class OptionQualitySummary:
    quality_signal: float | None = None
    value_signal: float | None = None
    fit_signal: float | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in ("quality_signal", "value_signal", "fit_signal"):
            value = getattr(self, field_name)
            if value is not None:
                require_probability(value, field_name)
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ComparisonAxis:
    key: str
    label: str
    direction: str = "contextual"
    notes: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.key, "key")
        require_non_empty(self.label, "label")
        if self.direction not in COMPARISON_DIRECTIONS:
            raise ValueError(f"direction must be one of {COMPARISON_DIRECTIONS}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Option:
    option_id: str
    kind: str
    label: str
    summary: str = ""
    fit_signals: dict[str, float] = field(default_factory=dict)
    cost_summary: OptionCostSummary = field(default_factory=OptionCostSummary)
    quality_summary: OptionQualitySummary = field(default_factory=OptionQualitySummary)
    drawbacks: list[str] = field(default_factory=list)
    booking_links: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    supporting_place_ids: list[str] = field(default_factory=list)
    explanation: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.option_id, "option_id")
        require_non_empty(self.label, "label")
        if self.kind not in OPTION_KINDS:
            raise ValueError(f"kind must be one of {OPTION_KINDS}")
        if not isinstance(self.cost_summary, OptionCostSummary):
            raise ValueError("cost_summary must be an OptionCostSummary")
        if not isinstance(self.quality_summary, OptionQualitySummary):
            raise ValueError("quality_summary must be an OptionQualitySummary")
        require_float_mapping(self.fit_signals, "fit_signals")
        require_strings(self.drawbacks, "drawbacks")
        require_strings(self.booking_links, "booking_links")
        require_strings(self.source_refs, "source_refs")
        require_strings(self.supporting_place_ids, "supporting_place_ids")
        require_strings(self.explanation, "explanation")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class OptionSet:
    option_set_id: str
    trip_id: str
    purpose: str
    scope: str
    title: str
    options: list[Option]
    comparison_axes: list[ComparisonAxis] = field(default_factory=list)
    explanation: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    selection_limit: int | None = None

    def __post_init__(self) -> None:
        require_non_empty(self.option_set_id, "option_set_id")
        require_non_empty(self.trip_id, "trip_id")
        require_non_empty(self.title, "title")
        if self.purpose not in OPTION_SET_PURPOSES:
            raise ValueError(f"purpose must be one of {OPTION_SET_PURPOSES}")
        if self.scope not in OPTION_SET_SCOPES:
            raise ValueError(f"scope must be one of {OPTION_SET_SCOPES}")
        if not self.options:
            raise ValueError("options must contain at least one Option")
        if any(not isinstance(option, Option) for option in self.options):
            raise ValueError("options must contain Option instances")
        if any(not isinstance(axis, ComparisonAxis) for axis in self.comparison_axes):
            raise ValueError("comparison_axes must contain ComparisonAxis instances")
        require_strings(self.explanation, "explanation")
        require_strings(self.source_refs, "source_refs")
        if self.selection_limit is not None:
            if self.selection_limit <= 0:
                raise ValueError("selection_limit must be positive when provided")
            if self.selection_limit > len(self.options):
                raise ValueError("selection_limit cannot exceed the number of options")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
