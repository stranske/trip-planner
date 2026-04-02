"""Persisted budget-plan and actual-spend contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from trip_planner.contracts._validators import (
    require_non_empty,
    require_optional_non_empty,
    require_strings,
)
from trip_planner.contracts.trip import TRIP_MODES

BUDGET_SCHEMA_VERSION = "0.1.0"
BUDGET_CATEGORY_KEYS: tuple[str, ...] = (
    "lodging",
    "transport",
    "food",
    "activities",
    "local_mobility",
    "fees",
    "contingency",
    "workspace",
    "client_hospitality",
)
BUSINESS_ONLY_BUDGET_CATEGORIES: tuple[str, ...] = (
    "workspace",
    "client_hospitality",
)
BUDGET_FLEXIBILITY_LEVELS: tuple[str, ...] = (
    "fixed",
    "protected",
    "flexible",
    "stretch",
)
ACTUAL_SPEND_SOURCE_KINDS: tuple[str, ...] = (
    "manual",
    "receipt",
    "card_import",
    "policy_export",
    "replan_adjustment",
)


def _require_currency(value: str, field_name: str) -> None:
    require_non_empty(value, field_name)
    if len(value) != 3 or not value.isalpha() or value.upper() != value:
        raise ValueError(f"{field_name} must be a 3-letter uppercase currency code")


def _require_string_list(values: list[str], field_name: str) -> None:
    if isinstance(values, str) or not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list of strings")
    require_strings(values, field_name)


def _require_unique_strings(values: list[str], field_name: str) -> None:
    _require_string_list(values, field_name)
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} cannot contain duplicates")


def _payload_list(
    payload: dict[str, Any], field_name: str, default: list[Any]
) -> list[Any]:
    value = payload.get(field_name, default)
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    return list(value)


@dataclass(slots=True)
class BudgetCategoryAllocation:
    category_key: str
    label: str
    planned_amount: float
    currency: str = "USD"
    flexibility: str = "flexible"
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.category_key not in BUDGET_CATEGORY_KEYS:
            raise ValueError(f"category_key must be one of {BUDGET_CATEGORY_KEYS}")
        require_non_empty(self.label, "label")
        _require_currency(self.currency, "currency")
        if self.planned_amount <= 0:
            raise ValueError("planned_amount must be positive")
        if self.flexibility not in BUDGET_FLEXIBILITY_LEVELS:
            raise ValueError(f"flexibility must be one of {BUDGET_FLEXIBILITY_LEVELS}")
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BudgetCategoryAllocation":
        return cls(
            category_key=payload["category_key"],
            label=payload["label"],
            planned_amount=payload["planned_amount"],
            currency=payload.get("currency", "USD"),
            flexibility=payload.get("flexibility", "flexible"),
            notes=_payload_list(payload, "notes", []),
        )


@dataclass(slots=True)
class BudgetScenario:
    scenario_budget_id: str
    trip_id: str
    title: str
    created_at: str
    allocations: list[BudgetCategoryAllocation]
    currency: str = "USD"
    saved_scenario_id: str | None = None
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.scenario_budget_id, "scenario_budget_id")
        require_non_empty(self.trip_id, "trip_id")
        require_non_empty(self.title, "title")
        require_non_empty(self.created_at, "created_at")
        _require_currency(self.currency, "currency")
        require_optional_non_empty(self.saved_scenario_id, "saved_scenario_id")
        if not self.allocations:
            raise ValueError(
                "allocations must contain at least one BudgetCategoryAllocation"
            )
        if any(
            not isinstance(item, BudgetCategoryAllocation) for item in self.allocations
        ):
            raise ValueError(
                "allocations must contain BudgetCategoryAllocation instances"
            )
        category_keys = [item.category_key for item in self.allocations]
        if len(set(category_keys)) != len(category_keys):
            raise ValueError("allocations cannot repeat category_key values")
        if any(item.currency != self.currency for item in self.allocations):
            raise ValueError("allocations must use the scenario currency")
        _require_unique_strings(self.tags, "tags")
        _require_string_list(self.notes, "notes")

    @property
    def total_planned_amount(self) -> float:
        return round(sum(item.planned_amount for item in self.allocations), 2)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["total_planned_amount"] = self.total_planned_amount
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BudgetScenario":
        return cls(
            scenario_budget_id=payload["scenario_budget_id"],
            trip_id=payload["trip_id"],
            title=payload["title"],
            created_at=payload["created_at"],
            allocations=[
                BudgetCategoryAllocation.from_dict(item)
                for item in _payload_list(payload, "allocations", [])
            ],
            currency=payload.get("currency", "USD"),
            saved_scenario_id=payload.get("saved_scenario_id"),
            summary=payload.get("summary", ""),
            tags=_payload_list(payload, "tags", []),
            notes=_payload_list(payload, "notes", []),
        )


@dataclass(slots=True)
class BudgetPlan:
    budget_plan_id: str
    trip_id: str
    owner_profile_id: str
    title: str
    mode: str
    created_at: str
    updated_at: str
    scenario_budgets: list[BudgetScenario]
    current_scenario_budget_id: str
    currency: str = "USD"
    schema_version: str = BUDGET_SCHEMA_VERSION
    tags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.budget_plan_id, "budget_plan_id")
        require_non_empty(self.trip_id, "trip_id")
        require_non_empty(self.owner_profile_id, "owner_profile_id")
        require_non_empty(self.title, "title")
        require_non_empty(self.created_at, "created_at")
        require_non_empty(self.updated_at, "updated_at")
        if self.mode not in TRIP_MODES:
            raise ValueError(f"mode must be one of {TRIP_MODES}")
        _require_currency(self.currency, "currency")
        if not self.scenario_budgets:
            raise ValueError(
                "scenario_budgets must contain at least one BudgetScenario"
            )
        if any(not isinstance(item, BudgetScenario) for item in self.scenario_budgets):
            raise ValueError("scenario_budgets must contain BudgetScenario instances")
        scenario_ids = [item.scenario_budget_id for item in self.scenario_budgets]
        if len(set(scenario_ids)) != len(scenario_ids):
            raise ValueError("scenario_budgets cannot repeat scenario_budget_id values")
        if self.current_scenario_budget_id not in scenario_ids:
            raise ValueError(
                "current_scenario_budget_id must reference a scenario budget"
            )
        if any(item.trip_id != self.trip_id for item in self.scenario_budgets):
            raise ValueError("scenario_budgets must share the budget plan trip_id")
        if any(item.currency != self.currency for item in self.scenario_budgets):
            raise ValueError("scenario_budgets must use the budget plan currency")
        if self.schema_version != BUDGET_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {BUDGET_SCHEMA_VERSION!r}")
        if self.mode == "leisure":
            business_categories = {
                allocation.category_key
                for scenario in self.scenario_budgets
                for allocation in scenario.allocations
                if allocation.category_key in BUSINESS_ONLY_BUDGET_CATEGORIES
            }
            if business_categories:
                raise ValueError(
                    "leisure budget plans cannot use business-only categories"
                )
        _require_unique_strings(self.tags, "tags")
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BudgetPlan":
        return cls(
            budget_plan_id=payload["budget_plan_id"],
            trip_id=payload["trip_id"],
            owner_profile_id=payload["owner_profile_id"],
            title=payload["title"],
            mode=payload["mode"],
            created_at=payload["created_at"],
            updated_at=payload["updated_at"],
            scenario_budgets=[
                BudgetScenario.from_dict(item)
                for item in _payload_list(payload, "scenario_budgets", [])
            ],
            current_scenario_budget_id=payload["current_scenario_budget_id"],
            currency=payload.get("currency", "USD"),
            schema_version=payload.get("schema_version", BUDGET_SCHEMA_VERSION),
            tags=_payload_list(payload, "tags", []),
            notes=_payload_list(payload, "notes", []),
        )


@dataclass(slots=True)
class ActualSpendEvent:
    spend_event_id: str
    trip_id: str
    budget_plan_id: str
    category_key: str
    amount: float
    currency: str
    occurred_at: str
    source_kind: str
    source_context: str
    scenario_budget_id: str | None = None
    saved_scenario_id: str | None = None
    merchant_name: str = ""
    source_ref: str | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.spend_event_id, "spend_event_id")
        require_non_empty(self.trip_id, "trip_id")
        require_non_empty(self.budget_plan_id, "budget_plan_id")
        if self.category_key not in BUDGET_CATEGORY_KEYS:
            raise ValueError(f"category_key must be one of {BUDGET_CATEGORY_KEYS}")
        if self.amount <= 0:
            raise ValueError("amount must be positive")
        _require_currency(self.currency, "currency")
        require_non_empty(self.occurred_at, "occurred_at")
        if self.source_kind not in ACTUAL_SPEND_SOURCE_KINDS:
            raise ValueError(f"source_kind must be one of {ACTUAL_SPEND_SOURCE_KINDS}")
        require_non_empty(self.source_context, "source_context")
        require_optional_non_empty(self.scenario_budget_id, "scenario_budget_id")
        require_optional_non_empty(self.saved_scenario_id, "saved_scenario_id")
        require_optional_non_empty(self.source_ref, "source_ref")
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ActualSpendEvent":
        return cls(
            spend_event_id=payload["spend_event_id"],
            trip_id=payload["trip_id"],
            budget_plan_id=payload["budget_plan_id"],
            category_key=payload["category_key"],
            amount=payload["amount"],
            currency=payload["currency"],
            occurred_at=payload["occurred_at"],
            source_kind=payload["source_kind"],
            source_context=payload["source_context"],
            scenario_budget_id=payload.get("scenario_budget_id"),
            saved_scenario_id=payload.get("saved_scenario_id"),
            merchant_name=payload.get("merchant_name", ""),
            source_ref=payload.get("source_ref"),
            notes=_payload_list(payload, "notes", []),
        )
