from typing import Any

from pydantic import BaseModel, Field


class BudgetCategoryAllocationRequest(BaseModel):
    category_key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=80)
    planned_amount: float = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    flexibility: str = Field(default="flexible", min_length=1, max_length=32)
    notes: list[str] = Field(default_factory=list)


class BudgetScenarioRequest(BaseModel):
    scenario_budget_id: str | None = Field(default=None, max_length=96)
    saved_scenario_id: str | None = Field(default=None, max_length=96)
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(default="", max_length=240)
    tags: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    allocations: list[BudgetCategoryAllocationRequest] = Field(min_length=1)


class BudgetPlanUpsertRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    current_scenario_budget_id: str | None = Field(default=None, max_length=96)
    tags: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    scenario_budgets: list[BudgetScenarioRequest] = Field(min_length=1)
    summary: str = Field(default="", max_length=240)


class ActualSpendEventUpsertRequest(BaseModel):
    category_key: str = Field(min_length=1, max_length=64)
    amount: float = Field(gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    occurred_at: str | None = Field(default=None, max_length=64)
    source_kind: str = Field(default="manual", min_length=1, max_length=32)
    source_context: str = Field(min_length=1, max_length=240)
    scenario_budget_id: str | None = Field(default=None, max_length=96)
    saved_scenario_id: str | None = Field(default=None, max_length=96)
    merchant_name: str = Field(default="", max_length=160)
    source_ref: str | None = Field(default=None, max_length=160)
    notes: list[str] = Field(default_factory=list)


class BudgetWorkspaceResponse(BaseModel):
    budget_plan: dict[str, Any] | None = None
    versions: list[dict[str, Any]] = Field(default_factory=list)
    spend_events: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
