"""User-facing workspace view-model assembly.

Keeping presentation decisions here prevents persistence and mutation code from
growing the workspace integration module again.
"""

from __future__ import annotations

from typing import Any

_TRIP_MODE_LABELS = {
    "leisure": "Leisure trip",
    "business": "Business trip",
}
_DEBUG_PAYLOAD_KEYS = (
    "runtime_state",
    "inventory_summary",
    "scenario_search",
    "ranking",
    "route_comparison",
    "runtime_scenario_comparison",
    "feasibility_summary",
    "planner_panel_state",
    "policy_state",
    "proposal_state",
    "trip_record",
    "session",
    "saved_scenarios",
    "activity_log",
    "planner_memory",
)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _workspace_policy_state_is_active(*, policy_state: Any, proposal_state: Any) -> bool:
    if _dict(policy_state):
        return True
    proposal = _dict(proposal_state)
    if not proposal:
        return False
    summary = _dict(proposal.get("summary"))
    submission = str(
        summary.get("submission_status") or proposal.get("submission_status") or ""
    ).lower()
    evaluation = str(
        summary.get("evaluation_transport_status") or proposal.get("evaluation_status") or ""
    ).lower()
    explicit_state = any(
        (
            proposal.get("execution_id"),
            summary.get("approval_ready"),
            summary.get("evaluation_result_status"),
            summary.get("follow_up_status"),
        )
    )
    return explicit_state or submission not in {"", "pending"} or evaluation not in {"", "pending"}


def _workspace_approval_status(
    proposal_state: dict[str, Any], *, trip_mode: str = "leisure"
) -> tuple[str, str, list[str]]:
    summary = _dict(proposal_state.get("summary"))
    follow_up = str(summary.get("follow_up_status") or "").lower()
    evaluation = str(
        summary.get("evaluation_result_status") or summary.get("submission_status") or ""
    ).lower()
    if summary.get("approval_ready"):
        return "approved", "Your trip is ready for approval.", []
    if evaluation in {"in_review", "pending", "submitted"}:
        return "in_review", "Your trip approval is in review.", []
    if evaluation in {"failed", "rejected", "needs_attention"} or follow_up in {
        "exception_required",
        "reoptimization_required",
        "remediation_required",
    }:
        blockers = [str(item) for item in summary.get("highlights") or [] if isinstance(item, str)]
        return "needs_attention", "Approval needs your attention.", blockers
    if proposal_state:
        return "not_ready", "Approval is not ready yet.", []
    if trip_mode == "business":
        return "not_ready", "Approval is not ready yet.", []
    return "not_applicable", "Approval is not required yet.", []


def _policy_presentation(*, active: bool, proposal_state: Any) -> dict[str, Any]:
    if not active:
        return {
            "active_policy_state": False,
            "posture_label": "Not applicable",
            "approval_status_label": "Not applicable",
            "next_step_label": "No policy action needed",
            "summary": "Policy approval is not part of this workspace yet.",
        }
    proposal = _dict(proposal_state)
    if not proposal:
        return {
            "active_policy_state": True,
            "posture_label": "Approval not started",
            "approval_status_label": "Approval not started",
            "next_step_label": "Build approval packet",
            "summary": "No approval packet has been submitted yet.",
        }
    status, headline, blockers = _workspace_approval_status(proposal)
    follow_up = str(_dict(proposal.get("summary")).get("follow_up_status") or "").lower()
    labels = {
        "approved": ("Ready for approval", "Prepare approval packet"),
        "needs_attention": ("Needs follow-up", "Resolve policy follow-up"),
        "in_review": ("Waiting for policy review", "Wait for policy review"),
        "not_ready": ("Not ready for approval", "Complete approval packet"),
    }
    posture, next_step = labels.get(status, ("Policy state available", "Review policy details"))
    if follow_up == "exception_required":
        posture, next_step = "Needs exception", "Review exception request"
    return {
        "active_policy_state": True,
        "posture_label": posture,
        "approval_status_label": posture,
        "next_step_label": next_step,
        "summary": " ".join([headline, *blockers[:1]]).strip(),
    }


def _next_step(status: str) -> tuple[str, str, str, str, bool]:
    if status == "ready":
        return (
            "Your trip plan is ready to review.",
            "Review and pick a scenario",
            "Compare the saved scenarios and choose one to keep planning around.",
            "Open scenario comparison",
            False,
        )
    if status == "partial":
        return (
            "Your trip plan is partially assembled.",
            "Continue planning",
            "Inventory is in place; resolve the open uncertainties to unlock scenario comparison.",
            "Continue planning",
            False,
        )
    return (
        "Trip planning hasn't started yet.",
        "Start planning",
        "Add the missing trip context to start assembling scenarios.",
        "Open trip setup",
        True,
    )


def build_workspace_view_model(
    payload: dict[str, Any], *, trip_mode: str | None = None, include_debug: bool = True
) -> dict[str, Any]:
    """Map internal workspace state into the stable product-facing model."""

    trip_record = _dict(payload.get("trip_record"))
    trip = _dict(trip_record.get("trip"))
    mode = str(trip_mode or trip.get("mode") or "leisure")
    mode = mode if mode in _TRIP_MODE_LABELS else "leisure"
    runtime = _dict(payload.get("runtime_state"))
    status = str(runtime.get("status") or "empty")
    status = status if status in {"ready", "partial", "empty"} else "empty"

    saved_scenarios = payload.get("saved_scenarios")
    saved_scenarios = saved_scenarios if isinstance(saved_scenarios, list) else []
    inventory = _dict(payload.get("inventory_summary"))
    feasibility = _dict(payload.get("feasibility_summary"))
    decided = []
    if saved_scenarios:
        decided.append(f"{len(saved_scenarios)} saved scenario draft(s)")
    bundle_count = int(inventory.get("bundle_count") or 0)
    if bundle_count:
        decided.append(f"{bundle_count} inventory bundle(s) assembled")
    uncertain = []
    attention_count = int(feasibility.get("attention_bundle_count") or 0)
    if attention_count:
        uncertain.append(f"{attention_count} bundle(s) need attention")
    if status == "empty":
        uncertain.append("Trip context is not complete yet.")
    elif status == "partial":
        uncertain.append("Scenario comparison is not yet ready.")

    headline, next_title, next_summary, next_action, blocked = _next_step(status)
    next_target = {"ready": "scenario-comparison", "partial": "planner"}.get(status, "trip-setup")
    proposal = payload.get("proposal_state")
    active = _workspace_policy_state_is_active(
        policy_state=payload.get("policy_state"), proposal_state=proposal
    )
    show_policy = mode == "business" or active
    business_summary = None
    if mode == "business":
        approval_status, approval_headline, blockers = _workspace_approval_status(
            _dict(proposal), trip_mode=mode
        )
        business_summary = {
            "approval_status": approval_status,
            "headline": approval_headline,
            "blockers": blockers,
        }

    debug_sections = {
        key: {"title": key.replace("_", " ").title(), "payload": payload[key]}
        for key in _DEBUG_PAYLOAD_KEYS
        if key in payload
        and payload[key] is not None
        and (include_debug or key not in {"policy_state", "proposal_state"})
    }
    return {
        "user_summary": {
            "trip_title": str(trip.get("title") or "Trip workspace"),
            "trip_mode": mode,
            "mode_label": _TRIP_MODE_LABELS[mode],
            "status": status,
            "headline": headline,
            "decided": decided,
            "uncertain": uncertain,
        },
        "next_step": {
            "title": next_title,
            "summary": next_summary,
            "action_label": next_action,
            "action_target": next_target,
            "blocked": blocked,
        },
        "panel_visibility": {
            "show_budget_panel": True,
            "show_policy_posture": show_policy,
            "show_proposal_panel": show_policy,
            "show_approval_readiness_panel": show_policy,
        },
        "policy_presentation": _policy_presentation(active=show_policy, proposal_state=proposal),
        "business_summary": business_summary,
        "debug_state": {"sections": debug_sections},
    }
