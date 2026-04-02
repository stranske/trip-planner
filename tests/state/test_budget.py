import json
from pathlib import Path

import pytest

from trip_planner.state import ActualSpendEvent, BudgetPlan
from trip_planner.state.budget import BudgetCategoryAllocation
from trip_planner.state.repositories import (
    BudgetPlanRepository,
    BudgetPlanVersion,
    SpendEventRepository,
)


def _fixture_path(name: str) -> Path:
    fixtures_dir = Path(__file__).resolve().parents[1] / "fixtures" / "state" / "budget"
    return fixtures_dir / name


def _load_plan(name: str) -> BudgetPlan:
    payload = json.loads(_fixture_path(name).read_text(encoding="utf-8"))
    return BudgetPlan.from_dict(payload)


def _load_events() -> list[ActualSpendEvent]:
    payload = json.loads(
        _fixture_path("actual_spend_events.json").read_text(encoding="utf-8")
    )
    return [ActualSpendEvent.from_dict(item) for item in payload["events"]]


def test_budget_plan_loads_leisure_fixture_with_scenario_variants() -> None:
    record = _load_plan("leisure_budget_plan.json")

    assert record.mode == "leisure"
    assert record.current_scenario_budget_id == "budget-scenario:kyoto-baseline"
    assert (
        record.scenario_budgets[0].saved_scenario_id == "saved-scenario:baseline-kyoto"
    )
    assert record.scenario_budgets[0].total_planned_amount == 1720.0
    assert record.scenario_budgets[1].allocations[3].category_key == "local_mobility"


def test_budget_plan_loads_business_fixture_with_policy_sensitive_categories() -> None:
    record = _load_plan("business_budget_plan.json")
    categories = {
        allocation.category_key
        for scenario in record.scenario_budgets
        for allocation in scenario.allocations
    }

    assert record.mode == "business"
    assert "workspace" in categories
    assert "client_hospitality" in categories


def test_actual_spend_event_fixture_captures_source_context() -> None:
    events = _load_events()

    assert events[0].source_kind == "receipt"
    assert "JR pass" in events[0].source_context
    assert events[1].category_key == "client_hospitality"
    assert events[1].merchant_name == "The Delegate Room"


def test_budget_plan_rejects_leisure_business_only_category() -> None:
    payload = json.loads(
        _fixture_path("leisure_budget_plan.json").read_text(encoding="utf-8")
    )
    payload["scenario_budgets"][0]["allocations"].append(
        {
            "category_key": "workspace",
            "label": "Should not exist",
            "planned_amount": 40.0,
            "currency": "USD",
        }
    )

    with pytest.raises(
        ValueError, match="leisure budget plans cannot use business-only categories"
    ):
        BudgetPlan.from_dict(payload)


def test_budget_category_allocation_rejects_invalid_currency_and_category() -> None:
    with pytest.raises(
        ValueError, match="currency must be a 3-letter uppercase currency code"
    ):
        BudgetCategoryAllocation(
            category_key="lodging",
            label="Hotel",
            planned_amount=100.0,
            currency="usd",
        )
    with pytest.raises(ValueError, match="category_key must be one of"):
        BudgetCategoryAllocation(
            category_key="souvenirs",
            label="Shops",
            planned_amount=50.0,
            currency="USD",
        )


def test_actual_spend_event_rejects_invalid_source_or_amount() -> None:
    with pytest.raises(ValueError, match="amount must be positive"):
        ActualSpendEvent(
            spend_event_id="spend:bad",
            trip_id="trip-1",
            budget_plan_id="budget-plan:1",
            category_key="food",
            amount=0,
            currency="USD",
            occurred_at="2026-04-02T07:00:00Z",
            source_kind="manual",
            source_context="Bad test",
        )
    with pytest.raises(ValueError, match="source_kind must be one of"):
        ActualSpendEvent(
            spend_event_id="spend:bad-source",
            trip_id="trip-1",
            budget_plan_id="budget-plan:1",
            category_key="food",
            amount=10.0,
            currency="USD",
            occurred_at="2026-04-02T07:00:00Z",
            source_kind="bank_feed",
            source_context="Bad test",
        )


def test_budget_repository_protocol_can_store_plans_and_spend_events() -> None:
    class InMemoryBudgetPlanRepository(BudgetPlanRepository):
        def __init__(self) -> None:
            self._plans: dict[str, BudgetPlan] = {}
            self._versions: dict[str, list[BudgetPlanVersion]] = {}

        def get_budget_plan(self, budget_plan_id: str) -> BudgetPlan | None:
            return self._plans.get(budget_plan_id)

        def save_budget_plan(
            self,
            budget_plan: BudgetPlan,
            *,
            summary: str = "",
        ) -> BudgetPlanVersion:
            self._plans[budget_plan.budget_plan_id] = budget_plan
            version = BudgetPlanVersion(
                version_id=(
                    f"{budget_plan.budget_plan_id}-v"
                    f"{len(self._versions.get(budget_plan.budget_plan_id, [])) + 1}"
                ),
                budget_plan_id=budget_plan.budget_plan_id,
                recorded_at=budget_plan.updated_at,
                summary=summary,
            )
            self._versions.setdefault(budget_plan.budget_plan_id, []).append(version)
            return version

        def list_budget_plans(
            self,
            *,
            trip_id: str | None = None,
            mode: str | None = None,
            saved_scenario_id: str | None = None,
        ) -> list[BudgetPlan]:
            plans = list(self._plans.values())
            if trip_id is not None:
                plans = [plan for plan in plans if plan.trip_id == trip_id]
            if mode is not None:
                plans = [plan for plan in plans if plan.mode == mode]
            if saved_scenario_id is not None:
                plans = [
                    plan
                    for plan in plans
                    if any(
                        scenario.saved_scenario_id == saved_scenario_id
                        for scenario in plan.scenario_budgets
                    )
                ]
            return plans

        def list_versions(self, budget_plan_id: str) -> list[BudgetPlanVersion]:
            return list(self._versions.get(budget_plan_id, []))

    class InMemorySpendEventRepository(SpendEventRepository):
        def __init__(self) -> None:
            self._events: dict[str, ActualSpendEvent] = {}

        def get_spend_event(self, spend_event_id: str) -> ActualSpendEvent | None:
            return self._events.get(spend_event_id)

        def record_spend_event(self, spend_event: ActualSpendEvent) -> ActualSpendEvent:
            self._events[spend_event.spend_event_id] = spend_event
            return spend_event

        def update_spend_event(self, spend_event: ActualSpendEvent) -> ActualSpendEvent:
            self._events[spend_event.spend_event_id] = spend_event
            return spend_event

        def list_spend_events(
            self,
            *,
            trip_id: str | None = None,
            budget_plan_id: str | None = None,
            saved_scenario_id: str | None = None,
            category_key: str | None = None,
            source_kind: str | None = None,
        ) -> list[ActualSpendEvent]:
            events = list(self._events.values())
            if trip_id is not None:
                events = [event for event in events if event.trip_id == trip_id]
            if budget_plan_id is not None:
                events = [
                    event for event in events if event.budget_plan_id == budget_plan_id
                ]
            if saved_scenario_id is not None:
                events = [
                    event
                    for event in events
                    if event.saved_scenario_id == saved_scenario_id
                ]
            if category_key is not None:
                events = [
                    event for event in events if event.category_key == category_key
                ]
            if source_kind is not None:
                events = [event for event in events if event.source_kind == source_kind]
            return events

    plan_repo = InMemoryBudgetPlanRepository()
    spend_repo = InMemorySpendEventRepository()
    plan = _load_plan("leisure_budget_plan.json")
    events = _load_events()

    first = plan_repo.save_budget_plan(plan, summary="initial baseline import")
    updated_plan = BudgetPlan.from_dict(plan.to_dict())
    updated_plan.current_scenario_budget_id = "budget-scenario:kyoto-rainy-day"
    updated_plan.updated_at = "2026-04-02T06:10:00Z"
    second = plan_repo.save_budget_plan(updated_plan, summary="switch to fallback")

    for event in events:
        spend_repo.record_spend_event(event)

    stored = plan_repo.get_budget_plan(plan.budget_plan_id)

    assert stored is not None
    assert stored.current_scenario_budget_id == "budget-scenario:kyoto-rainy-day"
    assert [
        version.version_id for version in plan_repo.list_versions(plan.budget_plan_id)
    ] == [
        first.version_id,
        second.version_id,
    ]
    assert (
        len(
            spend_repo.list_spend_events(
                trip_id="trip-leisure-kyoto-draft",
                saved_scenario_id="saved-scenario:baseline-kyoto",
            )
        )
        == 1
    )
    assert spend_repo.list_spend_events(category_key="client_hospitality")[
        0
    ].trip_id == ("trip-business-client-summit")
