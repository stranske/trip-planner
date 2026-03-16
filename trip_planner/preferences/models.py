"""Canonical leisure preference contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from . import schema


def _require_probability(value: float, field_name: str) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0")


def _require_axis(value: float, field_name: str) -> None:
    if not -1.0 <= value <= 1.0:
        raise ValueError(f"{field_name} must be between -1.0 and 1.0")


def _require_strings(values: list[str], field_name: str) -> None:
    if any(not isinstance(item, str) or not item for item in values):
        raise ValueError(f"{field_name} must contain only non-empty strings")


def _require_string_key_mapping(mapping: dict[str, Any], field_name: str) -> None:
    if any(not isinstance(key, str) or not key for key in mapping):
        raise ValueError(f"{field_name} must use non-empty string keys")


def _default_stage_sensitivity() -> dict[str, float]:
    return {stage: 0.0 for stage in schema.PLANNING_STAGES}


def _default_anchor_groups() -> dict[str, list["Anchor"]]:
    return {group: [] for group in schema.ANCHOR_GROUPS}


@dataclass(slots=True)
class TripFrame:
    duration_days: int | None = None
    traveler_party: str | None = None
    season_window: list[str] = field(default_factory=list)
    trip_stage: str | None = None
    regions_in_scope: list[str] = field(default_factory=list)
    special_themes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.duration_days is not None and self.duration_days <= 0:
            raise ValueError("duration_days must be positive when provided")
        if self.traveler_party and self.traveler_party not in schema.TRAVELER_PARTIES:
            raise ValueError(f"traveler_party must be one of {schema.TRAVELER_PARTIES}")
        if self.trip_stage and self.trip_stage not in schema.TRIP_STAGES:
            raise ValueError(f"trip_stage must be one of {schema.TRIP_STAGES}")
        _require_strings(self.season_window, "season_window")
        _require_strings(self.regions_in_scope, "regions_in_scope")
        _require_strings(self.special_themes, "special_themes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DateWindow:
    start: str | None = None
    end: str | None = None

    def __post_init__(self) -> None:
        if self.start is not None and not self.start:
            raise ValueError("start must be non-empty when provided")
        if self.end is not None and not self.end:
            raise ValueError("end must be non-empty when provided")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DurationBounds:
    min_days: int | None = None
    max_days: int | None = None

    def __post_init__(self) -> None:
        if self.min_days is not None and self.min_days <= 0:
            raise ValueError("min_days must be positive when provided")
        if self.max_days is not None and self.max_days <= 0:
            raise ValueError("max_days must be positive when provided")
        if (
            self.min_days is not None
            and self.max_days is not None
            and self.min_days > self.max_days
        ):
            raise ValueError("min_days cannot exceed max_days")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class HardConstraints:
    date_window: DateWindow = field(default_factory=DateWindow)
    duration_bounds: DurationBounds = field(default_factory=DurationBounds)
    budget_ceiling: float | None = None
    must_include_places: list[str] = field(default_factory=list)
    must_protect_experiences: list[str] = field(default_factory=list)
    mobility_constraints: list[str] = field(default_factory=list)
    lodging_constraints: list[str] = field(default_factory=list)
    visa_border_constraints: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.budget_ceiling is not None and self.budget_ceiling < 0:
            raise ValueError("budget_ceiling cannot be negative")
        _require_strings(self.must_include_places, "must_include_places")
        _require_strings(self.must_protect_experiences, "must_protect_experiences")
        _require_strings(self.mobility_constraints, "mobility_constraints")
        _require_strings(self.lodging_constraints, "lodging_constraints")
        _require_strings(self.visa_border_constraints, "visa_border_constraints")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Anchor:
    type: str
    label: str
    strength: float
    flexibility: float
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.type:
            raise ValueError("type is required")
        if not self.label:
            raise ValueError("label is required")
        _require_probability(self.strength, "strength")
        _require_probability(self.flexibility, "flexibility")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BudgetModel:
    total_budget_sensitivity: float = 0.0
    spending_priorities: dict[str, float] = field(default_factory=dict)
    quality_floors: dict[str, str | None] = field(default_factory=dict)
    splurge_allowed: bool = False
    splurge_style: str | None = None

    def __post_init__(self) -> None:
        _require_probability(self.total_budget_sensitivity, "total_budget_sensitivity")
        _require_string_key_mapping(self.spending_priorities, "spending_priorities")
        for key, value in self.spending_priorities.items():
            _require_probability(value, f"spending_priorities[{key}]")
        _require_string_key_mapping(self.quality_floors, "quality_floors")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TradeoffDimension:
    value: float = 0.0
    confidence: float = 0.0
    salience: float = 0.0
    stability: float = 0.0
    trip_stage_sensitivity: dict[str, float] = field(default_factory=_default_stage_sensitivity)
    scope: str = "global"
    notes: str = ""

    def __post_init__(self) -> None:
        _require_axis(self.value, "value")
        _require_probability(self.confidence, "confidence")
        _require_probability(self.salience, "salience")
        _require_probability(self.stability, "stability")
        if self.scope not in schema.DIMENSION_SCOPES:
            raise ValueError(f"scope must be one of {schema.DIMENSION_SCOPES}")
        _require_string_key_mapping(
            self.trip_stage_sensitivity,
            "trip_stage_sensitivity",
        )
        invalid_stages = set(self.trip_stage_sensitivity) - set(schema.PLANNING_STAGES)
        if invalid_stages:
            raise ValueError(f"unsupported trip stages: {sorted(invalid_stages)}")
        for key, stage_value in self.trip_stage_sensitivity.items():
            _require_probability(stage_value, f"trip_stage_sensitivity[{key}]")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class HybridFactor:
    mode: str
    salience: float = 0.0
    anchor_strength: float = 0.0
    tradeoff_role: str = "none"
    notes: str = ""
    preferences: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.mode not in schema.HYBRID_FACTOR_MODES:
            raise ValueError(f"mode must be one of {schema.HYBRID_FACTOR_MODES}")
        if self.tradeoff_role not in schema.HYBRID_FACTOR_ROLES:
            raise ValueError(f"tradeoff_role must be one of {schema.HYBRID_FACTOR_ROLES}")
        _require_probability(self.salience, "salience")
        _require_probability(self.anchor_strength, "anchor_strength")
        _require_string_key_mapping(self.preferences, "preferences")
        for key, value in self.preferences.items():
            _require_probability(value, f"preferences[{key}]")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class InteractionRule:
    id: str
    dimensions: list[str]
    activation: dict[str, Any] = field(default_factory=dict)
    effect: dict[str, Any] = field(default_factory=dict)
    strength: float = 0.0
    priority: float = 0.0

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("id is required")
        _require_strings(self.dimensions, "dimensions")
        _require_probability(self.strength, "strength")
        _require_probability(self.priority, "priority")
        _require_string_key_mapping(self.activation, "activation")
        _require_string_key_mapping(self.effect, "effect")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TensionFlag:
    id: str
    severity: float
    description: str

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("id is required")
        if not self.description:
            raise ValueError("description is required")
        _require_probability(self.severity, "severity")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EvidenceSummary:
    sources: dict[str, list[str]] = field(default_factory=dict)
    confidence_notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_string_key_mapping(self.sources, "sources")
        for key, values in self.sources.items():
            _require_strings(values, f"sources[{key}]")
        _require_strings(self.confidence_notes, "confidence_notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LeisurePreferenceProfile:
    trip_frame: TripFrame
    hard_constraints: HardConstraints
    budget_model: BudgetModel
    tradeoff_dimensions: dict[str, TradeoffDimension]
    hybrid_factors: dict[str, HybridFactor]
    anchors: dict[str, list[Anchor]] = field(default_factory=_default_anchor_groups)
    conditional_overrides: list[dict[str, Any]] = field(default_factory=list)
    interaction_rules: list[InteractionRule] = field(default_factory=list)
    tension_flags: list[TensionFlag] = field(default_factory=list)
    evidence_summary: EvidenceSummary = field(default_factory=EvidenceSummary)
    schema_version: str = schema.SCHEMA_VERSION
    profile_kind: str = schema.PROFILE_KIND

    def __post_init__(self) -> None:
        if self.schema_version != schema.SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be {schema.SCHEMA_VERSION!r} for the current contract"
            )
        if self.profile_kind != schema.PROFILE_KIND:
            raise ValueError(f"profile_kind must be {schema.PROFILE_KIND!r}")
        if set(self.anchors) != set(schema.ANCHOR_GROUPS):
            raise ValueError(f"anchors must use exactly {schema.ANCHOR_GROUPS}")
        for group_name, anchors in self.anchors.items():
            if any(not isinstance(anchor, Anchor) for anchor in anchors):
                raise ValueError(f"{group_name} must contain Anchor instances")
        expected_dimensions = set(schema.TRADEOFF_DIMENSION_KEYS)
        if set(self.tradeoff_dimensions) != expected_dimensions:
            raise ValueError("tradeoff_dimensions must define every first-tier leisure dimension")
        if any(
            not isinstance(dimension, TradeoffDimension)
            for dimension in self.tradeoff_dimensions.values()
        ):
            raise ValueError("tradeoff_dimensions must contain TradeoffDimension instances")
        expected_hybrid = set(schema.HYBRID_FACTOR_KEYS)
        if set(self.hybrid_factors) != expected_hybrid:
            raise ValueError("hybrid_factors must define every canonical hybrid factor")
        if any(not isinstance(factor, HybridFactor) for factor in self.hybrid_factors.values()):
            raise ValueError("hybrid_factors must contain HybridFactor instances")
        if any(not isinstance(rule, InteractionRule) for rule in self.interaction_rules):
            raise ValueError("interaction_rules must contain InteractionRule instances")
        if any(not isinstance(flag, TensionFlag) for flag in self.tension_flags):
            raise ValueError("tension_flags must contain TensionFlag instances")
        if any(not isinstance(item, dict) for item in self.conditional_overrides):
            raise ValueError("conditional_overrides must contain dictionaries")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
