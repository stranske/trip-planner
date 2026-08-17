from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from importlib.resources.abc import Traversable
from typing import Any

from trip_planner.state import (
    ActualSpendEvent,
    BudgetPlan,
    PersistedTripRecord,
    PlanningSessionState,
    SavedScenarioRecord,
    ScenarioComparison,
    User,
)


@dataclass(frozen=True, slots=True)
class WorkspaceFixture:
    trip_fixture: str
    scenarios_fixture: str
    session_fixture: str
    scenario_search_variant: str


FIXTURES: dict[str, WorkspaceFixture] = {
    "trip-leisure-kyoto-draft": WorkspaceFixture(
        trip_fixture="leisure_draft_trip.json",
        scenarios_fixture="leisure_baseline_vs_fallback.json",
        session_fixture="active_leisure_session.json",
        scenario_search_variant="leisure",
    ),
    "trip-business-client-summit": WorkspaceFixture(
        trip_fixture="business_active_trip.json",
        scenarios_fixture="business_compliant_vs_exception.json",
        session_fixture="business_review_session.json",
        scenario_search_variant="business",
    ),
}


def _state_fixture_dir(kind: str) -> Traversable:
    """Return packaged sample workspace data without relying on the source tree."""

    return files("trip_planner.resources").joinpath("state").joinpath(kind)


def _load_json(path: Traversable) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_trip_record(name: str) -> PersistedTripRecord:
    return PersistedTripRecord.from_dict(_load_json(_state_fixture_dir("trips") / name))


def load_saved_scenarios(
    name: str,
) -> tuple[list[SavedScenarioRecord], ScenarioComparison | None]:
    payload = _load_json(_state_fixture_dir("scenarios") / name)
    records = [SavedScenarioRecord.from_dict(item) for item in payload["records"]]
    comparison = payload.get("comparison")
    return records, (
        ScenarioComparison.from_dict(comparison) if comparison is not None else None
    )


def load_session(name: str) -> PlanningSessionState:
    payload = _load_json(_state_fixture_dir("sessions") / name)
    return PlanningSessionState.from_dict(payload["session"])


def load_account(name: str) -> User:
    return User.from_dict(_load_json(_state_fixture_dir("accounts") / name))


def load_budget_plan(name: str) -> BudgetPlan:
    return BudgetPlan.from_dict(_load_json(_state_fixture_dir("budget") / name))


def load_budget_events() -> list[ActualSpendEvent]:
    payload = _load_json(_state_fixture_dir("budget") / "actual_spend_events.json")
    return [ActualSpendEvent.from_dict(item) for item in payload["events"]]


def load_state_payload(kind: str, name: str) -> dict[str, Any]:
    return _load_json(_state_fixture_dir(kind) / name)


def load_fixture_policy_state(trip_id: str) -> dict[str, Any] | None:
    if trip_id != "trip-business-client-summit":
        return None
    return _load_json(_state_fixture_dir("policy") / "business_client_summit_policy.json")
