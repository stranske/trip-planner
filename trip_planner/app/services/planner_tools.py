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
    create_planning_notebook_item,
    get_workspace_payload,
    set_planning_notebook_focus,
    submit_workspace_option_feedback,
)
from trip_planner.sources import (
    QualityValueFitSummary,
    SourceQualityScorer,
    SourceRecord,
)
from trip_planner.sources import SourceTrustSignals


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


PlannerToolHandler = Callable[
    [Session, AuthenticatedUser, str, dict[str, Any]], PlannerToolResult
]


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
        tool_name="read_source_summary",
        description="Read bounded source and provenance summaries from current workspace inventory and scenario contracts.",
    ),
    PlannerToolDefinition(
        tool_name="read_source_quality_summary",
        description="Read source quality scoring state for attached workspace source records.",
    ),
    PlannerToolDefinition(
        tool_name="read_map_provider_status",
        description="Read map/provider status and route readiness without requiring live map credentials.",
    ),
    PlannerToolDefinition(
        tool_name="read_route_geometry",
        description="Read bounded route geometry and marker readiness for the active or requested route option.",
    ),
    PlannerToolDefinition(
        tool_name="refresh_route_comparison",
        description="Refresh the deterministic route comparison payload used by the workspace.",
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
    PlannerToolDefinition(
        tool_name="capture_notebook_item",
        description="Save a trip-scoped planning notebook item for later planner turns.",
        mutates_state=True,
    ),
    PlannerToolDefinition(
        tool_name="set_notebook_focus",
        description="Switch the active planning notebook focus by category or notebook item.",
        mutates_state=True,
    ),
    PlannerToolDefinition(
        tool_name="read_planning_notebook",
        description="Read active or completed planning notebook items for the current trip.",
    ),
    PlannerToolDefinition(
        tool_name="read_notebook_context",
        description=(
            "Summarize active planning notebook context across all categories for "
            "session resumption."
        ),
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
    cache = db_session.info.setdefault("_planner_workspace_payload_cache", {})
    cache_key = (user.user_id, trip_id)
    if cache_key in cache:
        return cache[cache_key]
    payload = get_workspace_payload(db_session, user=user, trip_id=trip_id)
    if payload is None:
        raise ValueError(f"Trip '{trip_id}' was not found.")
    cache[cache_key] = payload
    return payload


def get_cached_workspace_payload(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
) -> dict[str, Any]:
    return _workspace_payload(db_session, user=user, trip_id=trip_id)


def _clear_workspace_payload_cache(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
) -> None:
    cache = db_session.info.get("_planner_workspace_payload_cache")
    if isinstance(cache, dict):
        cache.pop((user.user_id, trip_id), None)


def _ref_list(*refs: str | None) -> list[str]:
    return [ref for ref in refs if ref]


def _bounded_items(items: list[Any], limit: int) -> list[Any]:
    return items[: max(0, min(limit, 20))]


def _source_record_from_payload(payload: Any) -> SourceRecord | None:
    if isinstance(payload, SourceRecord):
        return payload
    if not isinstance(payload, dict):
        return None
    trust_payload = payload.get("trust_signals") or {}
    quality_payload = payload.get("quality_summary") or {}
    try:
        return SourceRecord(
            **{
                **payload,
                "trust_signals": SourceTrustSignals(**trust_payload),
                "quality_summary": QualityValueFitSummary(**quality_payload),
            }
        )
    except (TypeError, ValueError):
        return None


def _route_scenarios(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return list(
        (payload.get("runtime_scenario_comparison") or {}).get("scenarios") or []
    )


def _select_route_scenario(
    payload: dict[str, Any],
    arguments: dict[str, Any],
) -> dict[str, Any] | None:
    scenarios = _route_scenarios(payload)
    requested_id = str(
        arguments.get("route_option_id") or arguments.get("scenario_id") or ""
    ).strip()
    if requested_id:
        return next(
            (
                scenario
                for scenario in scenarios
                if scenario.get("route_option_id") == requested_id
                or scenario.get("scenario_id") == requested_id
            ),
            None,
        )
    lead_id = (payload.get("runtime_scenario_comparison") or {}).get("lead_scenario_id")
    return next(
        (scenario for scenario in scenarios if scenario.get("scenario_id") == lead_id),
        None,
    ) or (scenarios[0] if scenarios else None)


def _category_allocations(
    total_amount: float, categories: list[str], currency: str
) -> list[dict[str, Any]]:
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
        "option_count": len(
            (planner_panel.get("option_set") or {}).get("options") or []
        ),
        "output_titles": [item["title"] for item in planner_panel.get("outputs") or []][
            :3
        ],
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
        "scenario_titles": [
            item["title"] for item in scenario_search.get("scenarios") or []
        ],
        "lead_scenario_id": runtime_comparison["lead_scenario_id"],
    }
    return PlannerToolResult(
        tool_name="refresh_scenarios",
        status="completed",
        summary="Read the current ranked scenario and comparison outputs.",
        mutates_state=False,
        refs=_ref_list(
            payload["session"]["session_state_id"],
            runtime_comparison["lead_scenario_id"],
        ),
        output=output,
    )


def _read_source_summary(
    db_session: Session,
    user: AuthenticatedUser,
    trip_id: str,
    arguments: dict[str, Any],
) -> PlannerToolResult:
    del arguments
    payload = _workspace_payload(db_session, user=user, trip_id=trip_id)
    inventory = payload["inventory_summary"]
    scenario_search = payload["scenario_search"]
    source_refs = list(
        dict.fromkeys(
            [
                *list(scenario_search.get("source_refs") or []),
                *[
                    ref
                    for scenario in list(scenario_search.get("scenarios") or [])
                    for ref in list(scenario.get("source_refs") or [])
                ],
            ]
        )
    )
    source_metadata = inventory.get("source_metadata") or {}
    provenance_context = source_metadata.get("provenance_context") or {}
    bundles = _bounded_items(list(inventory.get("bundles") or []), 5)
    output = {
        "source_type": source_metadata.get("source_type") or "unknown",
        "adapter_name": source_metadata.get("adapter_name") or "",
        "bundle_count": inventory.get("bundle_count", 0),
        "source_refs": _bounded_items(source_refs, 10),
        "source_result_set_id": scenario_search.get("source_result_set_id"),
        "input_record_ids": _bounded_items(
            list(provenance_context.get("input_record_ids") or []),
            10,
        ),
        "issues": _bounded_items(
            list((inventory.get("runtime_state") or {}).get("issues") or []),
            5,
        ),
        "bundles": [
            {
                "bundle_id": item.get("bundle_id"),
                "title": item.get("title"),
                "destination_names": _bounded_items(
                    list(item.get("destination_names") or []), 5
                ),
                "option_count": item.get("option_count", 0),
            }
            for item in bundles
        ],
    }
    status = "completed" if source_refs or bundles else "not_available"
    return PlannerToolResult(
        tool_name="read_source_summary",
        status=status,
        summary=(
            f"Read {len(output['source_refs'])} source reference(s) and "
            f"{len(output['bundles'])} inventory bundle summary item(s)."
            if status == "completed"
            else "No source-backed workspace summary is available for this trip yet."
        ),
        mutates_state=False,
        refs=_ref_list(payload["session"]["session_state_id"], *output["source_refs"]),
        output=output,
    )


def _read_source_quality_summary(
    db_session: Session,
    user: AuthenticatedUser,
    trip_id: str,
    arguments: dict[str, Any],
) -> PlannerToolResult:
    del arguments
    payload = _workspace_payload(db_session, user=user, trip_id=trip_id)
    inventory = payload["inventory_summary"]
    runtime_state = inventory.get("runtime_state") or {}
    scorer = SourceQualityScorer()
    quality_rows = []
    for bundle in _bounded_items(list(inventory.get("bundles") or []), 5):
        source_records = [
            record
            for record in (
                _source_record_from_payload(item)
                for item in bundle.get("source_records", [])
            )
            if record is not None
        ]
        summary = scorer.summarize(
            source_records,
            subject_kind="option",
            intended_option_kind=str(bundle.get("bundle_context") or "mixed"),
        )
        row_status = (
            "completed"
            if summary.contributing_source_count
            else "missing_source_records"
        )
        quality_rows.append(
            {
                "target_id": bundle.get("bundle_id"),
                "target_title": bundle.get("title"),
                "status": row_status,
                "score": summary.confidence
                if summary.contributing_source_count
                else None,
                "confidence_label": summary.confidence_label,
                "contributing_source_count": summary.contributing_source_count,
                "category_counts": dict(summary.category_counts),
                "summary": " ".join(summary.explanation_fragments[:2]),
                "tags": list(summary.tags),
            }
        )
    completed_rows = [row for row in quality_rows if row["status"] == "completed"]
    tool_status = "completed" if completed_rows else "missing_source_records"
    return PlannerToolResult(
        tool_name="read_source_quality_summary",
        status=tool_status,
        summary=(
            f"Scored source quality for {len(completed_rows)} workspace bundle(s)."
            if completed_rows
            else "No source records are attached to the current workspace targets yet."
        ),
        mutates_state=False,
        refs=_ref_list(payload["session"]["session_state_id"]),
        output={
            "quality_state": tool_status,
            "runtime_inventory_status": runtime_state.get("status", "unknown"),
            "rows": quality_rows,
            "next_service": "source_quality_scoring",
        },
    )


def _read_map_provider_status(
    db_session: Session,
    user: AuthenticatedUser,
    trip_id: str,
    arguments: dict[str, Any],
) -> PlannerToolResult:
    payload = _workspace_payload(db_session, user=user, trip_id=trip_id)
    scenario = _select_route_scenario(payload, arguments)
    if scenario is None:
        return PlannerToolResult(
            tool_name="read_map_provider_status",
            status="not_available",
            summary="No route scenario is available for map/provider status.",
            mutates_state=False,
            refs=_ref_list(payload["session"]["session_state_id"]),
            output={
                "provider": {"kind": "fallback", "status": "sparse-route"},
                "route_state": "missing",
                "route_option_id": None,
                "map_confidence": "none",
            },
        )
    diagnostics = scenario.get("map_diagnostics") or {}
    provider = diagnostics.get("provider") or {}
    confidence = (scenario.get("map_view") or {}).get("confidence") or {}
    provider_status = str(provider.get("status") or "fallback")
    route_state = str(diagnostics.get("route_state") or "unknown")
    return PlannerToolResult(
        tool_name="read_map_provider_status",
        status="completed" if route_state == "ready" else provider_status,
        summary=(
            f"Map provider state is {provider_status}; route geometry state is {route_state}."
        ),
        mutates_state=False,
        refs=_ref_list(
            payload["session"]["session_state_id"],
            scenario.get("route_option_id"),
            diagnostics.get("source_result_id"),
        ),
        output={
            "route_option_id": scenario.get("route_option_id"),
            "scenario_id": scenario.get("scenario_id"),
            "provider": {
                "kind": provider.get("kind") or "fallback",
                "status": provider_status,
                "details": provider.get("details") or "",
            },
            "route_state": route_state,
            "route_warning": diagnostics.get("route_warning"),
            "map_confidence": confidence.get("level", "unknown"),
            "summary": confidence.get("summary") or scenario.get("summary"),
        },
    )


def _read_route_geometry(
    db_session: Session,
    user: AuthenticatedUser,
    trip_id: str,
    arguments: dict[str, Any],
) -> PlannerToolResult:
    payload = _workspace_payload(db_session, user=user, trip_id=trip_id)
    scenario = _select_route_scenario(payload, arguments)
    if scenario is None:
        return PlannerToolResult(
            tool_name="read_route_geometry",
            status="not_available",
            summary="No route scenario is available for geometry inspection.",
            mutates_state=False,
            refs=_ref_list(payload["session"]["session_state_id"]),
            output={
                "route_option_id": None,
                "place_markers": [],
                "rough_route_geometry": [],
            },
        )
    map_view = scenario.get("map_view") or {}
    markers = _bounded_items(list(map_view.get("place_markers") or []), 12)
    geometry = _bounded_items(list(map_view.get("rough_route_geometry") or []), 12)
    status = "completed" if geometry else "sparse-route"
    return PlannerToolResult(
        tool_name="read_route_geometry",
        status=status,
        summary=(
            f"Read {len(markers)} route marker(s) and {len(geometry)} route segment(s)."
            if geometry
            else "Route geometry is sparse; no route segments are available yet."
        ),
        mutates_state=False,
        refs=_ref_list(
            payload["session"]["session_state_id"], scenario.get("route_option_id")
        ),
        output={
            "route_option_id": scenario.get("route_option_id"),
            "scenario_id": scenario.get("scenario_id"),
            "active_scope": map_view.get("active_scope"),
            "selected_segment_id": map_view.get("selected_segment_id"),
            "place_markers": markers,
            "rough_route_geometry": geometry,
            "confidence": map_view.get("confidence") or {},
        },
    )


def _refresh_route_comparison(
    db_session: Session,
    user: AuthenticatedUser,
    trip_id: str,
    arguments: dict[str, Any],
) -> PlannerToolResult:
    del arguments
    payload = _workspace_payload(db_session, user=user, trip_id=trip_id)
    comparison = payload["runtime_scenario_comparison"]
    scenarios = _bounded_items(list(comparison.get("scenarios") or []), 5)
    output = {
        "title": comparison.get("title"),
        "summary": comparison.get("summary"),
        "lead_scenario_id": comparison.get("lead_scenario_id"),
        "comparison_axes": _bounded_items(
            list(comparison.get("comparison_axes") or []), 8
        ),
        "scenarios": [
            {
                "scenario_id": item.get("scenario_id"),
                "route_option_id": item.get("route_option_id"),
                "title": item.get("title"),
                "rank": item.get("rank"),
                "state": item.get("state"),
                "status": item.get("status"),
                "summary": item.get("summary"),
                "route_summary": item.get("route_summary"),
                "metrics": item.get("metrics") or {},
                "delta": item.get("delta") or {},
                "source_result_id": item.get("source_result_id"),
            }
            for item in scenarios
        ],
        "source_refs": _bounded_items(list(comparison.get("source_refs") or []), 10),
    }
    return PlannerToolResult(
        tool_name="refresh_route_comparison",
        status="completed" if scenarios else "not_available",
        summary=(
            f"Refreshed deterministic route comparison with {len(scenarios)} scenario row(s)."
            if scenarios
            else "No deterministic route comparison rows are available yet."
        ),
        mutates_state=False,
        refs=_ref_list(
            payload["session"]["session_state_id"],
            comparison.get("lead_scenario_id"),
            *output["source_refs"],
        ),
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
        refs=_ref_list(
            payload.get("budget_plan", {})
            and payload["budget_plan"].get("budget_plan_id")
        ),
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
    budget_payload = get_workspace_budget_payload(
        db_session, user=user, trip_id=trip_id
    )
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
                "saved_scenario_id": (
                    saved_scenario["saved_scenario_id"] if saved_scenario else None
                ),
                "title": scenario_title,
                "summary": "Planner-generated budget baseline.",
                "tags": ["planner-tool"],
                "notes": ["Created from the explicit planner tool boundary."],
                "allocations": _category_allocations(
                    total_amount, categories, currency
                ),
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
        refs=_ref_list(
            result["budget_plan"]["budget_plan_id"],
            result["summary"]["current_scenario_budget_id"],
        ),
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
        "status": summary.get(
            "status", "ready" if payload.get("policy_state") else "missing"
        ),
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
        refs=_ref_list(
            payload.get("policy_state", {})
            and payload["policy_state"].get("policy_state_id")
        ),
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
    follow_up_status = summary.get("follow_up_status")
    output = {
        "status": summary.get("status")
        or summary.get("evaluation_result_status")
        or "missing",
        "requires_follow_up": bool(
            summary.get("requires_follow_up")
            or follow_up_status
            in {
                "awaiting_evaluation",
                "reoptimization_required",
                "exception_required",
                "exception_requested",
            }
        ),
        "needs_exception": bool(
            summary.get("needs_exception")
            or follow_up_status in {"exception_required", "exception_requested"}
        ),
    }
    return PlannerToolResult(
        tool_name="read_proposal_state",
        status="completed",
        summary="Read the current workspace proposal state.",
        mutates_state=False,
        refs=_ref_list(
            payload.get("proposal_state", {})
            and payload["proposal_state"].get("proposal_state_id")
        ),
        output=output,
    )


def _answer_pending_decision(
    db_session: Session,
    user: AuthenticatedUser,
    trip_id: str,
    arguments: dict[str, Any],
) -> PlannerToolResult:
    workspace_payload = _workspace_payload(db_session, user=user, trip_id=trip_id)
    pending_decisions = list(
        workspace_payload["planner_panel_state"].get("pending_decisions") or []
    )
    if not pending_decisions:
        raise ValueError("No pending planner decisions are available for this trip.")
    decision_id = str(
        arguments.get("decision_id") or pending_decisions[0]["decision_id"]
    )
    matching = next(
        (item for item in pending_decisions if item["decision_id"] == decision_id), None
    )
    if matching is None:
        raise ValueError(
            f"Decision '{decision_id}' is not available in the planner panel."
        )
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
        "remaining_pending_decisions": len(
            result["planner_panel_state"].get("pending_decisions") or []
        ),
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
    options = list(
        (workspace_payload["planner_panel_state"].get("option_set") or {}).get(
            "options"
        )
        or []
    )
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
        "pending_decision_count": len(
            result["planner_panel_state"].get("pending_decisions") or []
        ),
    }
    return PlannerToolResult(
        tool_name="record_option_feedback",
        status="completed",
        summary=f"Recorded '{action_type}' feedback for planner option '{option_id}'.",
        mutates_state=True,
        refs=_ref_list(option_id, result["session"]["session_state_id"]),
        output=output,
    )


def _capture_notebook_item(
    db_session: Session,
    user: AuthenticatedUser,
    trip_id: str,
    arguments: dict[str, Any],
) -> PlannerToolResult:
    title = str(arguments.get("title") or "").strip()
    if not title:
        raise ValueError("capture_notebook_item requires title.")
    result = create_planning_notebook_item(
        db_session,
        user=user,
        trip_id=trip_id,
        title=title,
        note=str(arguments.get("note") or ""),
        category=str(arguments.get("category") or "other").strip(),
        status=str(arguments.get("status") or "active").strip(),
        priority=str(arguments.get("priority") or "normal").strip(),
        source="planner",
        source_message_ids=[
            str(item) for item in list(arguments.get("source_message_ids") or [])
        ],
        tags=[str(item) for item in list(arguments.get("tags") or [])],
    )
    return PlannerToolResult(
        tool_name="capture_notebook_item",
        status="completed",
        summary=f"Saved notebook item '{result['title']}' in {result['category']}.",
        mutates_state=True,
        refs=_ref_list(result["notebook_item_id"]),
        output={
            "notebook_item_id": result["notebook_item_id"],
            "category": result["category"],
            "status": result["status"],
            "title": result["title"],
        },
    )


def _set_notebook_focus(
    db_session: Session,
    user: AuthenticatedUser,
    trip_id: str,
    arguments: dict[str, Any],
) -> PlannerToolResult:
    category = arguments.get("category")
    notebook_item_id = arguments.get("notebook_item_id")
    result = set_planning_notebook_focus(
        db_session,
        user=user,
        trip_id=trip_id,
        category=str(category).strip() if category else None,
        notebook_item_id=str(notebook_item_id).strip() if notebook_item_id else None,
    )
    focus_label = result["notebook_item_id"] or result["category"] or "no active focus"
    return PlannerToolResult(
        tool_name="set_notebook_focus",
        status="completed",
        summary=f"Set planning notebook focus to {focus_label}.",
        mutates_state=True,
        refs=_ref_list(result["notebook_item_id"], result["category"]),
        output=result,
    )


def _read_planning_notebook(
    db_session: Session,
    user: AuthenticatedUser,
    trip_id: str,
    arguments: dict[str, Any],
) -> PlannerToolResult:
    payload = _workspace_payload(db_session, user=user, trip_id=trip_id)
    notebook = payload["planning_notebook"]
    category = arguments.get("category")
    status = arguments.get("status")
    limit = max(1, min(int(arguments.get("limit") or 5), 20))
    items = list(notebook.get("items") or [])
    if category:
        items = [item for item in items if item.get("category") == str(category)]
    if status:
        items = [item for item in items if item.get("status") == str(status)]
    items = items[:limit]
    summary = notebook.get("summary") or {}
    return PlannerToolResult(
        tool_name="read_planning_notebook",
        status="completed",
        summary=f"Read {len(items)} planning notebook item(s).",
        mutates_state=False,
        refs=_ref_list(*(str(item.get("notebook_item_id") or "") for item in items)),
        output={
            "items": items,
            "focus": notebook.get("focus") or {},
            "active_count": len(summary.get("active_items") or []),
            "completed_count": len(summary.get("completed_items") or []),
        },
    )


def _read_notebook_context(
    db_session: Session,
    user: AuthenticatedUser,
    trip_id: str,
    arguments: dict[str, Any],
) -> PlannerToolResult:
    del arguments
    payload = _workspace_payload(db_session, user=user, trip_id=trip_id)
    notebook = payload["planning_notebook"]
    active_items = [
        item for item in (notebook.get("items") or []) if item.get("status") == "active"
    ]
    active_items.sort(
        key=lambda item: (
            str(item.get("updated_at") or ""),
            str(item.get("created_at") or ""),
        ),
        reverse=True,
    )
    categories: dict[str, list[dict[str, Any]]] = {}
    for item in active_items:
        category = str(item.get("category") or "other")
        bucket = categories.setdefault(category, [])
        if len(bucket) >= 3:
            continue
        bucket.append(
            {
                "title": item.get("title") or "",
                "note": item.get("note") or "",
                "category": category,
                "priority": item.get("priority") or "normal",
                "updated_at": item.get("updated_at"),
            }
        )
    focus = notebook.get("focus") or {}
    output = {
        "context_state": "active" if active_items else "empty",
        "active_categories": list(categories.keys()),
        "open_item_count": len(active_items),
        "summarized_item_count": sum(len(bucket) for bucket in categories.values()),
        "categories": categories,
        "focus_category": focus.get("category"),
    }
    return PlannerToolResult(
        tool_name="read_notebook_context",
        status="completed",
        summary=(
            f"Summarized {output['summarized_item_count']} active notebook item(s) across "
            f"{len(categories)} category(ies) for session resumption."
            if active_items
            else "No active planning notebook context is available for this trip yet."
        ),
        mutates_state=False,
        refs=_ref_list(payload["session"]["session_state_id"]),
        output=output,
    )


_TOOL_HANDLERS: dict[str, PlannerToolHandler] = {
    "read_workspace_state": _read_workspace_state,
    "refresh_inventory": _refresh_inventory,
    "refresh_scenarios": _refresh_scenarios,
    "read_source_summary": _read_source_summary,
    "read_source_quality_summary": _read_source_quality_summary,
    "read_map_provider_status": _read_map_provider_status,
    "read_route_geometry": _read_route_geometry,
    "refresh_route_comparison": _refresh_route_comparison,
    "read_budget_state": _read_budget_state,
    "update_budget_plan": _update_budget_plan,
    "read_policy_state": _read_policy_state,
    "read_proposal_state": _read_proposal_state,
    "answer_pending_decision": _answer_pending_decision,
    "record_option_feedback": _record_option_feedback,
    "capture_notebook_item": _capture_notebook_item,
    "set_notebook_focus": _set_notebook_focus,
    "read_planning_notebook": _read_planning_notebook,
    "read_notebook_context": _read_notebook_context,
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
    if definition.mutates_state:
        _clear_workspace_payload_cache(db_session, user=user, trip_id=trip_id)
    result = handler(db_session, user, trip_id, dict(arguments or {}))
    if definition.mutates_state:
        _clear_workspace_payload_cache(db_session, user=user, trip_id=trip_id)
    return result
