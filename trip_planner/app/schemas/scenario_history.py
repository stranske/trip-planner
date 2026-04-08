"""Schemas for persisted saved-scenario and planning-history routes."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CreateSavedScenarioRequest(BaseModel):
    saved_scenario_id: str | None = Field(default=None, max_length=96)
    version_id: str | None = Field(default=None, max_length=96)
    title: str = Field(min_length=1, max_length=160)
    label: str = Field(min_length=1, max_length=64)
    summary: str = Field(default="", max_length=600)
    created_at: str | None = Field(default=None, max_length=64)
    created_by: str = Field(default="system", min_length=1, max_length=64)
    scope: str = Field(default="route", min_length=1, max_length=64)
    based_on_version_id: str | None = Field(default=None, max_length=96)
    snapshot_refs: dict[str, Any] = Field(default_factory=dict)
    comparisons: list[dict[str, Any]] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class CreatePlanningHistoryRequest(BaseModel):
    activity_event_id: str | None = Field(default=None, max_length=96)
    session_state_id: str | None = Field(default=None, max_length=96)
    occurred_at: str | None = Field(default=None, max_length=64)
    event_kind: str = Field(min_length=1, max_length=64)
    summary: str = Field(min_length=1, max_length=600)
    actor: str = Field(default="system", min_length=1, max_length=64)
    related_decision_id: str | None = Field(default=None, max_length=96)
    related_option_set_id: str | None = Field(default=None, max_length=96)
    saved_scenario_id: str | None = Field(default=None, max_length=96)
    budget_plan_id: str | None = Field(default=None, max_length=96)
    scenario_budget_id: str | None = Field(default=None, max_length=96)
    checkpoint_id: str | None = Field(default=None, max_length=96)
    metadata: dict[str, str] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SavedScenarioResponse(BaseModel):
    saved_scenario: dict[str, Any]


class PlanningHistoryResponse(BaseModel):
    planning_history_entry: dict[str, Any]


class TripScenarioHistoryResponse(BaseModel):
    saved_scenarios: list[dict[str, Any]]
    planning_history: list[dict[str, Any]]
