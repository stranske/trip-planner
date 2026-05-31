"""Route-search and scenario-output contracts for itinerary assembly."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from trip_planner._option_contracts import OPTION_SET_PURPOSES
from trip_planner._validators import (
    require_non_empty,
    require_non_negative,
    require_strings,
)
from trip_planner.contracts import MoneyRange
from trip_planner.ranking import ExplanationRecord

SCHEMA_VERSION = "0.1.0"
SCENARIO_KINDS: tuple[str, ...] = ("primary", "alternative", "fallback")
TRADEOFF_SEVERITIES: tuple[str, ...] = ("info", "warning", "critical")


@dataclass(slots=True)
class ScenarioTradeoff:
    tradeoff_id: str
    code: str
    summary: str
    severity: str = "warning"
    blocking: bool = False
    related_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.tradeoff_id, "tradeoff_id")
        require_non_empty(self.code, "code")
        require_non_empty(self.summary, "summary")
        if self.severity not in TRADEOFF_SEVERITIES:
            raise ValueError(f"severity must be one of {TRADEOFF_SEVERITIES}")
        require_strings(self.related_ids, "related_ids")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ScenarioSummary:
    headline: str
    scenario_kind: str
    feasible: bool
    recommended_for_selection: bool
    coherence_passed: bool
    estimated_total: MoneyRange | None = None
    total_travel_minutes: int = 0
    total_transfer_count: int = 0
    route_sequence: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.headline, "headline")
        if self.scenario_kind not in SCENARIO_KINDS:
            raise ValueError(f"scenario_kind must be one of {SCENARIO_KINDS}")
        if self.estimated_total is not None and not isinstance(self.estimated_total, MoneyRange):
            raise ValueError("estimated_total must be a MoneyRange when provided")
        require_non_negative(self.total_travel_minutes, "total_travel_minutes")
        require_non_negative(self.total_transfer_count, "total_transfer_count")
        require_strings(self.route_sequence, "route_sequence")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ItineraryScenario:
    scenario_id: str
    title: str
    rank: int
    bundle_id: str
    source_result_id: str
    score: float
    scenario_summary: ScenarioSummary
    supporting_option_ids: list[str] = field(default_factory=list)
    objective_refs: list[str] = field(default_factory=list)
    explanation_records: list[ExplanationRecord] = field(default_factory=list)
    unresolved_tradeoffs: list[ScenarioTradeoff] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.scenario_id, "scenario_id")
        require_non_empty(self.title, "title")
        require_non_empty(self.bundle_id, "bundle_id")
        require_non_empty(self.source_result_id, "source_result_id")
        if self.rank <= 0:
            raise ValueError("rank must be positive")
        if not isinstance(self.scenario_summary, ScenarioSummary):
            raise ValueError("scenario_summary must be a ScenarioSummary")
        if any(not isinstance(item, ExplanationRecord) for item in self.explanation_records):
            raise ValueError("explanation_records must contain ExplanationRecord instances")
        if any(not isinstance(item, ScenarioTradeoff) for item in self.unresolved_tradeoffs):
            raise ValueError("unresolved_tradeoffs must contain ScenarioTradeoff instances")
        require_strings(self.supporting_option_ids, "supporting_option_ids")
        require_strings(self.objective_refs, "objective_refs")
        require_strings(self.notes, "notes")
        if not self.explanation_records:
            raise ValueError("explanation_records must contain at least one ExplanationRecord")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ScenarioSearchResult:
    search_id: str
    trip_id: str
    purpose: str
    title: str
    source_result_set_id: str
    scenarios: list[ItineraryScenario]
    scope: str = "route"
    explanation: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_non_empty(self.search_id, "search_id")
        require_non_empty(self.trip_id, "trip_id")
        if self.purpose not in OPTION_SET_PURPOSES:
            raise ValueError(f"purpose must be one of {OPTION_SET_PURPOSES}")
        require_non_empty(self.title, "title")
        require_non_empty(self.source_result_set_id, "source_result_set_id")
        if self.scope != "route":
            raise ValueError("scope must be 'route'")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")
        if not self.scenarios:
            raise ValueError("scenarios must contain at least one ItineraryScenario")
        if any(not isinstance(item, ItineraryScenario) for item in self.scenarios):
            raise ValueError("scenarios must contain ItineraryScenario instances")
        require_strings(self.explanation, "explanation")
        require_strings(self.source_refs, "source_refs")

        ranks = [item.rank for item in self.scenarios]
        if len(set(ranks)) != len(ranks):
            raise ValueError("scenarios must use unique ranks")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
