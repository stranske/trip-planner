from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy.orm import Session

from trip_planner.app.services.auth import AuthenticatedUser
from trip_planner.app.services.budget import (
    get_workspace_budget_payload,
    upsert_workspace_budget_plan,
)
from trip_planner.app.services.policy import get_workspace_policy_payload
from trip_planner.app.services.proposal import get_workspace_proposal_payload
from trip_planner.app.services.workspace import (
    answer_workspace_planner_decision,
    get_workspace_payload,
    submit_workspace_option_feedback,
)


@dataclass(frozen=True, slots=True)
class PlannerToolDefinition:
    tool_name: str
    description: str
    mutates_state: bool = False


@dataclass(frozen=True, slots=True)
class PlannerToolResult:
    tool_name: str
    status: str
    summary: str
    mutates_state: bool
    refs: list[str]
    output: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "status": self.status,
            "summary": self.summary,
            "mutates_state": self.mutates_state,
            "refs": list(self.refs),
            "output": self.output,
        }


PlannerToolHandler = Callable[[Session, AuthenticatedUser, str, dict[str, Any]], PlannerToolResult]


_TOOL_DEFINITIONS: tuple[PlannerToolDefinition, ...] = (
    PlannerToolDefinition(
        tool_name="read_workspace_state",
        description="Read the current workspace planner panel, pending decisions, and option set.",
    ),
    PlannerToolDefinition(
        tool_name="refresh_inventory",
        description="Read the current inventory bundle summary for the active trip.",
    ),
    PlannerToolDefinition(
        tool_name="refresh_scenarios",
        description="Read the current scenario ranking and comparison outputs for the active trip.",
    ),
    PlannerToolDefinition(
        tool_name="read_budget_state",
        description="Read the persisted workspace budget summary for the active trip.",
    ),
    PlannerToolDefinition(
        tool_name="update_budget_plan",
        description="Create or update a bounded budget plan using persisted workspace state.",
        mutates_state=True,
    ),
    PlannerToolDefinition(
        tool_name="read_policy_state",
        description="Read the current workspace policy state for the active trip.",
    ),
    PlannerToolDefinition(
        tool_name="read_proposal_state",
        description="Read the current workspace proposal state for the active trip.",
    ),
    PlannerToolDefinition(
        tool_name="answer_pending_decision",
        description="Answer a pending planner decision through the existing workspace service.",
        mutates_state=True,
    ),
    PlannerToolDefinition(
        tool_name="record_option_feedback",
        description="Accept, reject, revise, or save a planner option through the workspace service.",
        mutates_state=True,
    ),
)

_TOOL_BY_NAME = {item.tool_name: item for item in _TOOL_DEFINITIONS}


def list_planner_tools() -> list[dict[str, Any]]:
    return [
        {
            "tool_name": item.tool_name,
            "description": item.description,
            "mutates_state": item.mutates_state,
        }
        for item in _TOOL_DEFINITIONS
    ]


def _workspace_payload(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
) -> dict[str, Any]:
    payload = get_workspace_payload(db_session, user=user, trip_id=trip_id)
    if payload is None:
        raise ValueError(f"Trip '{trip_id}' was not found.")
    return payload


def _ref_list(*refs: str | None) -> list[str]:
    return [ref for ref in refs if ref]


def _category_allocations(total_amount: float, categories: list[str], currency: str) -> list[dict[str, Any]]:
    if total_amount <= 0:
        raise ValueError("update_budget_plan requires total_amount > 0.")
    if not categories:
        raise ValueError("No suggested budget categories are available for this trip.")

    allocations: list[dict[str, Any]] = []
    base_amount = round(total_amount / len(categories), 2)
    assigned_total = 0.0
    for index, category in enumerate(categories):
        planned_amount = base_amount
        if index == len(categories) - 1:
            planned_amount = round(total_amount - assigned_total, 2)
        assigned_total = round(assigned_total + planned_amount, 2)
        allocations.append(
            {
                "category_key": category,
                "label": category.replace("_", " ").title(),
                "planned_amount": planned_amount,
                "currency": currency,
                "flexibility": "flexible",
                "notes": ["Planner-generated budget allocation."],
            }
        )
    return allocations


def _read_workspace_state(
    db_session: Session,
    user: AuthenticatedUser,
    trip_id: str,
    arguments: dict[str, Any],
) -> PlannerToolResult:
    del arguments
    payload = _workspace_payload(db_session, user=user, trip_id=trip_id)
    planner_panel = payload["planner_panel_state"]
    output = {
        "trip_title": planner_panel["trip"]["title"],
        "pending_decision_count": len(planner_panel.get("pending_decisions") or []),
        "option_count": len((planner_panel.get("option_set") or {}).get("options") or []),
        "output_titles": [item["title"] for item in planner_panel.get("outputs") or []][:3],
    }
    return PlannerToolResult(
        tool_name="read_workspace_state",
        status="completed",
        summary="Read the current planner panel workspace state.",
        mutates_state=False,
        refs=_ref_list(payload["session"]["session_state_id"]),
        output=output,
    )


def _refresh_inventory(
    db_session: Session,
    user: AuthenticatedUser,
    trip_id: str,
    arguments: dict[str, Any],
) -> PlannerToolResult:
    del arguments
    payload = _workspace_payload(db_session, user=user, trip_id=trip_id)
    inventory = payload["inventory_summary"]
    output = {
        "bundle_count": inventory["bundle_count"],
        "bundle_titles": [item["title"] for item in inventory.get("bundles") or []],
        "notes": list(inventory.get("notes") or []),
    }
    return PlannerToolResult(
        tool_name="refresh_inventory",
        status="completed",
        summary=f"Read {inventory['bundle_count']} inventory bundle(s) for the current trip.",
        mutates_state=False,
        refs=_ref_list(payload["session"]["session_state_id"]),
        output=output,
    )


def _refresh_scenarios(
    db_session: Session,
    user: AuthenticatedUser,
    trip_id: str,
    arguments: dict[str, Any],
) -> PlannerToolResult:
    del arguments
    payload = _workspace_payload(db_session, user=user, trip_id=trip_id)
    scenario_search = payload["scenario_search"]
    runtime_comparison = payload["runtime_scenario_comparison"]
    output = {
        "search_title": scenario_search["title"],
        "scenario_titles": [item["title"] for item in scenario_search.get("scenarios") or []],
        "lead_scenario_id": runtime_comparison["lead_scenario_id"],
    }
    return PlannerToolResult(
        tool_name="refresh_scenarios",
        status="completed",
        summary="Read the current ranked scenario and comparison outputs.",
        mutates_state=False,
        refs=_ref_list(payload["session"]["session_state_id"], runtime_comparison["lead_scenario_id"]),
        output=output,
    )


def _read_budget_state(
    db_session: Session,
    user: AuthenticatedUser,
    trip_id: str,
    arguments: dict[str, Any],
) -> PlannerToolResult:
    del arguments
    payload = get_workspace_budget_payload(db_session, user=user, trip_id=trip_id)
    summary = payload["summary"]
    output = {
        "currency": summary["currency"],
        "has_budget_plan": summary["has_budget_plan"],
        "planned_total": summary["planned_total"],
        "actual_total": summary["actual_total"],
        "suggested_categories": list(summary.get("suggested_categories") or []),
    }
    return PlannerToolResult(
        tool_name="read_budget_state",
        status="completed",
        summary="Read the current workspace budget summary.",
        mutates_state=False,
        refs=_ref_list(payload.get("budget_plan", {}) and payload["budget_plan"].get("budget_plan_id")),
        output=output,
    )


def _update_budget_plan(
    db_session: Session,
    user: AuthenticatedUser,
    trip_id: str,
    arguments: dict[str, Any],
) -> PlannerToolResult:
    total_amount = float(arguments.get("total_amount", 0))
    title = str(arguments.get("title") or "Planner-generated budget plan")
    budget_payload = get_workspace_budget_payload(db_session, user=user, trip_id=trip_id)
    workspace_payload = _workspace_payload(db_session, user=user, trip_id=trip_id)
    summary = budget_payload["summary"]
    categories = list(summary.get("suggested_categories") or [])[:4]
    raw_currency = arguments.get("currency") or summary["currency"] or "USD"
    currency = str(raw_currency).strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise ValueError("currency must be a 3-letter alphabetic currency code")
    saved_scenario = (workspace_payload.get("saved_scenarios") or [None])[0]
    scenario_budget_id = f"scenario-budget:{trip_id}:planner"
    scenario_title = (
        saved_scenario["versions"][0]["title"]
        if saved_scenario is not None
        else workspace_payload["trip_record"]["trip"]["title"]
    )
    result = upsert_workspace_budget_plan(
        db_session,
        user=user,
        trip_id=trip_id,
        title=title,
        currency=currency,
        current_scenario_budget_id=scenario_budget_id,
        tags=["planner-tool"],
        notes=["Updated by the planner tool runtime."],
        scenario_budgets=[
            {
                "scenario_budget_id": scenario_budget_id,
                "saved_scenario_id": saved_scenario["saved_scenario_id"] if saved_scenario else None,
                "title": scenario_title,
                "summary": "Planner-generated budget baseline.",
                "tags": ["planner-tool"],
                "notes": ["Created from the explicit planner tool boundary."],
                "allocations": _category_allocations(total_amount, categories, currency),
            }
        ],
        summary=f"Planner set the working budget to {currency} {total_amount:.2f}.",
    )
    output = {
        "budget_plan_id": result["budget_plan"]["budget_plan_id"],
        "planned_total": result["summary"]["planned_total"],
        "category_count": len(result["summary"]["category_summaries"]),
    }
    return PlannerToolResult(
        tool_name="update_budget_plan",
        status="completed",
        summary=f"Updated the workspace budget plan to {currency} {total_amount:.2f}.",
        mutates_state=True,
        refs=_ref_list(result["budget_plan"]["budget_plan_id"], result["summary"]["current_scenario_budget_id"]),
        output=output,
    )


def _read_policy_state(
    db_session: Session,
    user: AuthenticatedUser,
    trip_id: str,
    arguments: dict[str, Any],
) -> PlannerToolResult:
    del arguments
    payload = get_workspace_policy_payload(db_session, user=user, trip_id=trip_id)
    summary = payload["summary"]
    output = {
        "status": summary["status"],
        "ready_for_submission": bool(
            summary.get("ready_for_submission") or summary.get("approval_ready")
        ),
        "issue_count": int(
            summary.get("issue_count")
            or summary.get("blocking_failure_count")
            or summary.get("approval_requirement_count")
            or 0
        ),
    }
    return PlannerToolResult(
        tool_name="read_policy_state",
        status="completed",
        summary="Read the current workspace policy state.",
        mutates_state=False,
        refs=_ref_list(payload.get("policy_state", {}) and payload["policy_state"].get("policy_state_id")),
        output=output,
    )


def _read_proposal_state(
    db_session: Session,
    user: AuthenticatedUser,
    trip_id: str,
    arguments: dict[str, Any],
) -> PlannerToolResult:
    del arguments
    payload = get_workspace_proposal_payload(db_session, user=user, trip_id=trip_id)
    summary = payload["summary"]
    output = {
        "status": summary["status"],
        "requires_follow_up": bool(
            summary.get("requires_follow_up")
            or summary.get("follow_up_status")
            in {"reoptimization_required", "exception_required", "exception_requested"}
        ),
        "needs_exception": bool(
            summary.get("needs_exception")
            or summary.get("follow_up_status") in {"exception_required", "exception_requested"}
        ),
    }
    return PlannerToolResult(
        tool_name="read_proposal_state",
        status="completed",
        summary="Read the current workspace proposal state.",
        mutates_state=False,
        refs=_ref_list(payload.get("proposal_state", {}) and payload["proposal_state"].get("proposal_state_id")),
        output=output,
    )


def _answer_pending_decision(
    db_session: Session,
    user: AuthenticatedUser,
    trip_id: str,
    arguments: dict[str, Any],
) -> PlannerToolResult:
    workspace_payload = _workspace_payload(db_session, user=user, trip_id=trip_id)
    pending_decisions = list(workspace_payload["planner_panel_state"].get("pending_decisions") or [])
    if not pending_decisions:
        raise ValueError("No pending planner decisions are available for this trip.")
    decision_id = str(arguments.get("decision_id") or pending_decisions[0]["decision_id"])
    matching = next((item for item in pending_decisions if item["decision_id"] == decision_id), None)
    if matching is None:
        raise ValueError(f"Decision '{decision_id}' is not available in the planner panel.")
    choice = str(arguments.get("choice") or "").strip()
    if not choice:
        raise ValueError("answer_pending_decision requires a non-empty choice.")
    result = answer_workspace_planner_decision(
        db_session,
        user=user,
        trip_id=trip_id,
        decision_id=decision_id,
        choice=choice,
    )
    output = {
        "decision_id": decision_id,
        "remaining_pending_decisions": len(result["planner_panel_state"].get("pending_decisions") or []),
    }
    return PlannerToolResult(
        tool_name="answer_pending_decision",
        status="completed",
        summary=f"Answered planner decision '{decision_id}' with '{choice}'.",
        mutates_state=True,
        refs=_ref_list(decision_id, result["session"]["session_state_id"]),
        output=output,
    )


def _record_option_feedback(
    db_session: Session,
    user: AuthenticatedUser,
    trip_id: str,
    arguments: dict[str, Any],
) -> PlannerToolResult:
    action_type = str(arguments.get("action_type") or "").strip()
    if not action_type:
        raise ValueError("record_option_feedback requires action_type.")
    workspace_payload = _workspace_payload(db_session, user=user, trip_id=trip_id)
    options = list((workspace_payload["planner_panel_state"].get("option_set") or {}).get("options") or [])
    if not options:
        raise ValueError("No planner options are available for this trip.")
    option_id = str(arguments.get("option_id") or options[0]["option_id"])
    decision_id = arguments.get("decision_id")
    result = submit_workspace_option_feedback(
        db_session,
        user=user,
        trip_id=trip_id,
        option_id=option_id,
        action_type=action_type,
        decision_id=str(decision_id) if decision_id else None,
    )
    output = {
        "option_id": option_id,
        "action_type": action_type,
        "pending_decision_count": len(result["planner_panel_state"].get("pending_decisions") or []),
    }
    return PlannerToolResult(
        tool_name="record_option_feedback",
        status="completed",
        summary=f"Recorded '{action_type}' feedback for planner option '{option_id}'.",
        mutates_state=True,
        refs=_ref_list(option_id, result["session"]["session_state_id"]),
        output=output,
    )


_TOOL_HANDLERS: dict[str, PlannerToolHandler] = {
    "read_workspace_state": _read_workspace_state,
    "refresh_inventory": _refresh_inventory,
    "refresh_scenarios": _refresh_scenarios,
    "read_budget_state": _read_budget_state,
    "update_budget_plan": _update_budget_plan,
    "read_policy_state": _read_policy_state,
    "read_proposal_state": _read_proposal_state,
    "answer_pending_decision": _answer_pending_decision,
    "record_option_feedback": _record_option_feedback,
}


def execute_planner_tool_call(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
) -> PlannerToolResult:
    definition = _TOOL_BY_NAME.get(tool_name)
    handler = _TOOL_HANDLERS.get(tool_name)
    if definition is None or handler is None:
        raise ValueError(f"Planner tool '{tool_name}' is not supported.")
    return handler(db_session, user, trip_id, dict(arguments or {}))
