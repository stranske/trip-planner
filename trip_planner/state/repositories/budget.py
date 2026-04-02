"""Backend-neutral repository interfaces for persisted budget state."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol

from trip_planner.contracts._validators import require_non_empty
from trip_planner.state.budget import ActualSpendEvent, BudgetPlan


@dataclass(slots=True)
class BudgetPlanVersion:
    version_id: str
    budget_plan_id: str
    recorded_at: str
    summary: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.version_id, "version_id")
        require_non_empty(self.budget_plan_id, "budget_plan_id")
        require_non_empty(self.recorded_at, "recorded_at")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BudgetPlanRepository(Protocol):
    def get_budget_plan(self, budget_plan_id: str) -> BudgetPlan | None:
        """Load one persisted budget plan."""

    def save_budget_plan(
        self,
        budget_plan: BudgetPlan,
        *,
        summary: str = "",
    ) -> BudgetPlanVersion:
        """Persist one budget plan and return version metadata."""

    def list_budget_plans(
        self,
        *,
        trip_id: str | None = None,
        mode: str | None = None,
        saved_scenario_id: str | None = None,
    ) -> list[BudgetPlan]:
        """List budget plans using backend-neutral filters."""

    def list_versions(self, budget_plan_id: str) -> list[BudgetPlanVersion]:
        """List saved versions for one persisted budget plan."""


class SpendEventRepository(Protocol):
    def get_spend_event(self, spend_event_id: str) -> ActualSpendEvent | None:
        """Load one persisted spend event."""

    def record_spend_event(self, spend_event: ActualSpendEvent) -> ActualSpendEvent:
        """Persist a new actual-spend event."""

    def update_spend_event(self, spend_event: ActualSpendEvent) -> ActualSpendEvent:
        """Persist an updated actual-spend event."""

    def list_spend_events(
        self,
        *,
        trip_id: str | None = None,
        budget_plan_id: str | None = None,
        saved_scenario_id: str | None = None,
        scenario_budget_id: str | None = None,
        category_key: str | None = None,
        source_kind: str | None = None,
    ) -> list[ActualSpendEvent]:
        """List actual-spend events using backend-neutral filters.

        Use ``saved_scenario_id`` to filter by the logical saved scenario and
        ``scenario_budget_id`` to target a specific scenario-budget variant.
        """
