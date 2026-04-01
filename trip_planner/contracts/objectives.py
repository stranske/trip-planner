"""Shared itinerary-objective contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from ._validators import (
    require_non_empty,
    require_non_negative,
    require_probability,
    require_strings,
)

ROUTE_SHAPES: tuple[str, ...] = ("hub_and_spoke", "linear", "regional_cluster", "mixed")
STRUCTURE_LEVELS: tuple[str, ...] = ("high", "moderate", "elastic")
DISCOVERY_STYLES: tuple[str, ...] = ("iconic", "balanced", "discovery_forward")
LODGING_BASE_STYLES: tuple[str, ...] = (
    "single_base",
    "few_bases",
    "multi_base",
    "mixed",
)


@dataclass(slots=True)
class CountRange:
    min_value: int | None = None
    max_value: int | None = None

    def __post_init__(self) -> None:
        for field_name in ("min_value", "max_value"):
            value = getattr(self, field_name)
            if value is not None:
                require_non_negative(value, field_name)
        if (
            self.min_value is not None
            and self.max_value is not None
            and self.min_value > self.max_value
        ):
            raise ValueError("min_value cannot exceed max_value")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MoveDensityTarget:
    max_moves: int | None = None
    cadence_days: int | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.max_moves is not None:
            require_non_negative(self.max_moves, "max_moves")
        if self.cadence_days is not None:
            if self.cadence_days <= 0:
                raise ValueError("cadence_days must be positive when provided")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RecoveryExpectations:
    buffer_days: int | None = None
    recovery_priority: float = 0.0
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.buffer_days is not None:
            require_non_negative(self.buffer_days, "buffer_days")
        require_probability(self.recovery_priority, "recovery_priority")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DayStructureObjectives:
    structure_level: str = "moderate"
    wandering_support_level: float = 0.0
    reservation_density: float = 0.0

    def __post_init__(self) -> None:
        if self.structure_level not in STRUCTURE_LEVELS:
            raise ValueError(f"structure_level must be one of {STRUCTURE_LEVELS}")
        require_probability(self.wandering_support_level, "wandering_support_level")
        require_probability(self.reservation_density, "reservation_density")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DiscoveryStrategy:
    style: str = "balanced"
    protect_open_blocks: bool = False
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.style not in DISCOVERY_STYLES:
            raise ValueError(f"style must be one of {DISCOVERY_STYLES}")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BudgetProtection:
    protected_categories: list[str] = field(default_factory=list)
    sensitivity: float = 0.0
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_strings(self.protected_categories, "protected_categories")
        require_probability(self.sensitivity, "sensitivity")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class QualityFloorProtection:
    required_categories: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_strings(self.required_categories, "required_categories")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LodgingStrategy:
    base_style: str = "mixed"
    arrival_buffer_priority: float = 0.0
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.base_style not in LODGING_BASE_STYLES:
            raise ValueError(f"base_style must be one of {LODGING_BASE_STYLES}")
        require_probability(self.arrival_buffer_priority, "arrival_buffer_priority")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TransportStrategy:
    preferred_modes: list[str] = field(default_factory=list)
    avoid_modes: list[str] = field(default_factory=list)
    transit_is_feature: bool = False
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_strings(self.preferred_modes, "preferred_modes")
        require_strings(self.avoid_modes, "avoid_modes")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ItineraryObjectives:
    objective_id: str
    trip_id: str
    route_shape: str
    target_base_count: CountRange = field(default_factory=CountRange)
    move_density: MoveDensityTarget = field(default_factory=MoveDensityTarget)
    recovery_expectations: RecoveryExpectations = field(
        default_factory=RecoveryExpectations
    )
    day_structure: DayStructureObjectives = field(
        default_factory=DayStructureObjectives
    )
    discovery_strategy: DiscoveryStrategy = field(default_factory=DiscoveryStrategy)
    budget_protection: BudgetProtection = field(default_factory=BudgetProtection)
    quality_floor_protection: QualityFloorProtection = field(
        default_factory=QualityFloorProtection
    )
    lodging_strategy: LodgingStrategy = field(default_factory=LodgingStrategy)
    transport_strategy: TransportStrategy = field(default_factory=TransportStrategy)
    explanations: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.objective_id, "objective_id")
        require_non_empty(self.trip_id, "trip_id")
        if self.route_shape not in ROUTE_SHAPES:
            raise ValueError(f"route_shape must be one of {ROUTE_SHAPES}")
        if not isinstance(self.target_base_count, CountRange):
            raise ValueError("target_base_count must be a CountRange")
        if not isinstance(self.move_density, MoveDensityTarget):
            raise ValueError("move_density must be a MoveDensityTarget")
        if not isinstance(self.recovery_expectations, RecoveryExpectations):
            raise ValueError("recovery_expectations must be a RecoveryExpectations")
        if not isinstance(self.day_structure, DayStructureObjectives):
            raise ValueError("day_structure must be a DayStructureObjectives")
        if not isinstance(self.discovery_strategy, DiscoveryStrategy):
            raise ValueError("discovery_strategy must be a DiscoveryStrategy")
        if not isinstance(self.budget_protection, BudgetProtection):
            raise ValueError("budget_protection must be a BudgetProtection")
        if not isinstance(self.quality_floor_protection, QualityFloorProtection):
            raise ValueError(
                "quality_floor_protection must be a QualityFloorProtection"
            )
        if not isinstance(self.lodging_strategy, LodgingStrategy):
            raise ValueError("lodging_strategy must be a LodgingStrategy")
        if not isinstance(self.transport_strategy, TransportStrategy):
            raise ValueError("transport_strategy must be a TransportStrategy")
        require_strings(self.explanations, "explanations")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
