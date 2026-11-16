"""User-facing workspace view-model assembly.

Keeping presentation decisions here prevents persistence and mutation code from
growing the workspace integration module again.
"""

from __future__ import annotations

from datetime import date
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
    if summary.get("approval_ready") or evaluation == "compliant":
        return "approved", "Your trip is ready for approval.", []
    # The public payload carries the outcome, not the raw transport status (#1130 / #1152).
    if str(summary.get("submission_outcome") or "") == "blocked_by_policy":
        return "needs_attention", "The travel policy blocked this trip.", _blocking_reasons(summary)
    if evaluation in {"in_review", "pending", "submitted"}:
        return "in_review", "Your trip approval is in review.", []
    if evaluation in {"failed", "rejected", "needs_attention", "non_compliant"} or follow_up in {
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


#: Trip-frame fields the traveller must supply before generated options mean anything.
def _missing_trip_context(trip: dict[str, Any], *, mode: str) -> list[str]:
    """Name the traveller-supplied inputs the planner still needs.

    Generated inventory and scenarios exist for every trip, including one created with
    nothing but a title, so they cannot be used to decide whether a plan is worth
    reviewing. Readiness is derived from what the traveller actually provided.
    """

    frame = _dict(trip.get("trip_frame"))
    missing: list[str] = []

    regions = frame.get("primary_regions")
    if not (isinstance(regions, list) and any(str(region).strip() for region in regions)):
        missing.append("a destination")

    try:
        start_date = date.fromisoformat(str(frame.get("start_date") or ""))
        end_date = date.fromisoformat(str(frame.get("end_date") or ""))
        dates_valid = end_date >= start_date
    except ValueError:
        dates_valid = False
    if not dates_valid:
        missing.append("travel dates")

    if mode == "business" and not str(trip.get("summary") or "").strip():
        missing.append("a business purpose for the approver")

    return missing


def _humanise(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} and {items[-1]}"


_Step = tuple[str, str, str, str, bool, str]


def _priced_count(entered_prices: Any) -> int:
    try:
        return int(_dict(entered_prices).get("priced_component_count") or 0)
    except (TypeError, ValueError):
        return 0


def _proposal_summary(proposal_state: Any) -> dict[str, Any]:
    return _dict(_dict(proposal_state).get("summary"))


def _blocking_reasons(summary: dict[str, Any]) -> list[str]:
    """TPP's own words for each blocking rule, falling back to the rule code."""

    messages: dict[str, str] = {}
    for reason in _dict(summary.get("follow_up")).get("failure_reasons") or []:
        reason = _dict(reason)
        if reason.get("code") and reason.get("message"):
            messages[str(reason["code"])] = str(reason["message"])
    codes = [str(code) for code in summary.get("submission_blocking_codes") or []] or list(messages)
    return [f"{messages[code]} (rule {code})" if code in messages else code for code in codes]


def _submitted_step(summary: dict[str, Any]) -> _Step | None:
    """Where a trip stands once it has been sent to the travel policy service."""

    verdict = str(summary.get("evaluation_result_status") or "").lower()
    outcome = str(summary.get("submission_outcome") or "").lower()
    if verdict == "compliant":
        return (
            "This trip passed the travel policy check.",
            "Print the approval packet",
            "Hand the packet to your approver. It carries the costs you entered, who entered "
            "them, and the policy result.",
            "Open the approval packet",
            False,
            "approval",
        )
    if outcome == "blocked_by_policy" or verdict == "non_compliant":
        reasons = _blocking_reasons(summary)
        detail = "; ".join(reasons) if reasons else "the policy service did not say which rules"
        return (
            "The travel policy blocked this trip.",
            "Fix what the policy flagged",
            f"Flagged: {detail}. Change the trip or its prices, then submit again.",
            "Open the policy check",
            False,
            "approval",
        )
    if outcome == "failed":
        return (
            "The travel policy check could not be reached.",
            "Submit again",
            "Nothing was reviewed: the request did not reach the policy service.",
            "Open the policy check",
            False,
            "approval",
        )
    if outcome not in {"", "not_submitted"}:
        return (
            "Submitted to the travel policy check.",
            "Check the policy result",
            "The policy service has the request. Refresh the policy check to read its result.",
            "Open the policy check",
            False,
            "approval",
        )
    return None


def _journey_step(*, mode: str, priced: int, proposal_state: Any) -> _Step:
    """The next step once trip setup is complete, advancing with what the traveller did."""

    if priced == 0:
        return (
            "Trip setup is saved. No prices have been entered yet.",
            "Enter the prices you have",
            "The planner measures routes and travel time but does not quote prices. Enter the "
            "fares and rates you hold on the Budget tab; each is recorded as entered by you.",
            "Open Budget",
            False,
            "budget",
        )
    if mode == "business":
        submitted = _submitted_step(_proposal_summary(proposal_state))
        if submitted is not None:
            return submitted
        return (
            f"Prices entered for {priced} item(s). Not yet checked against travel policy.",
            "Submit for approval",
            "Send the trip and the prices you entered to the travel policy check.",
            "Open the policy check",
            False,
            "approval",
        )
    return (
        f"Prices entered for {priced} item(s).",
        "Compare the route options",
        "Compare shows the measured routes with the total you entered.",
        "Open scenario comparison",
        False,
        "scenario-comparison",
    )


def _next_step(
    missing: list[str],
    *,
    mode: str = "leisure",
    entered_prices: Any = None,
    proposal_state: Any = None,
) -> _Step:
    if missing:
        return (
            f"This trip still needs {_humanise(missing)}.",
            "Finish trip setup",
            (
                "The planner cannot measure routes or check policy until it knows "
                f"{_humanise(missing)}."
            ),
            "Open trip setup",
            True,
            "trip-setup",
        )
    # Once setup is complete the journey is the same whether or not a route could be
    # measured: prices come from the traveller, and so does the approval request. A trip
    # to a place the planner cannot locate used to be told "Trip planning hasn't started
    # yet" here (issue 1827).
    return _journey_step(
        mode=mode, priced=_priced_count(entered_prices), proposal_state=proposal_state
    )


def _not_ready_reason(*, missing: list[str], priced: int, proposal_state: Any) -> str:
    """Why approval is not ready: the first step the traveller has not done."""

    if missing:
        return f"Approval is not ready yet: this trip still needs {_humanise(missing)}."
    if priced == 0:
        return "Approval is not ready yet: no prices have been entered."
    if (
        not _proposal_summary(proposal_state).get("submission_outcome")
        or _proposal_summary(proposal_state).get("submission_outcome") == "not_submitted"
    ):
        return "Approval is not ready yet: the trip has not been submitted to the policy check."
    return "Approval is not ready yet: the policy check has not returned a result."


def build_workspace_view_model(
    payload: dict[str, Any],
    *,
    trip_mode: str | None = None,
    include_debug: bool = True,
    entered_prices: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Map internal workspace state into the stable product-facing model.

    `entered_prices` is the traveller's price record (`build_trip_prices_payload`). Without
    it the header cannot tell an unpriced trip from a priced one, which is how it said
    "Nothing has been planned yet" after a trip had been priced and submitted (issue 1840).
    """

    trip_record = _dict(payload.get("trip_record"))
    trip = _dict(trip_record.get("trip"))
    mode = str(trip_mode or trip.get("mode") or "leisure")
    mode = mode if mode in _TRIP_MODE_LABELS else "leisure"
    runtime = _dict(payload.get("runtime_state"))
    status = str(runtime.get("status") or "empty")
    status = status if status in {"ready", "partial", "empty"} else "empty"

    saved_scenarios = payload.get("saved_scenarios")
    saved_scenarios = saved_scenarios if isinstance(saved_scenarios, list) else []
    feasibility = _dict(payload.get("feasibility_summary"))
    # "Decided" means the traveller decided it. Route options and inventory bundles are
    # generated automatically for every trip from flat constants, so they are never
    # progress the traveller made and must not be reported as such.
    decided: list[str] = []
    missing_context = _missing_trip_context(trip, mode=mode)
    if missing_context:
        # Generated bundles must never present an unstarted trip as reviewable.
        status = "empty"

    uncertain = []
    attention_count = int(feasibility.get("attention_bundle_count") or 0)
    if attention_count:
        uncertain.append(f"{attention_count} bundle(s) need attention")
    for item in missing_context:
        uncertain.append(f"Trip setup is missing {item}.")
    if status == "empty" and not missing_context:
        # Setup is complete but nothing could be measured; say what stopped it.
        uncertain.append(str(runtime.get("title") or "No route could be measured for this trip."))
    elif status == "partial":
        uncertain.append("Scenario comparison is not yet ready.")

    proposal = payload.get("proposal_state")
    headline, next_title, next_summary, next_action, blocked, next_target = _next_step(
        missing_context,
        mode=mode,
        entered_prices=entered_prices,
        proposal_state=proposal,
    )
    active = _workspace_policy_state_is_active(
        policy_state=payload.get("policy_state"), proposal_state=proposal
    )
    show_policy = mode == "business" or active
    business_summary = None
    if mode == "business":
        approval_status, approval_headline, blockers = _workspace_approval_status(
            _dict(proposal), trip_mode=mode
        )
        if approval_status == "not_ready":
            approval_headline = _not_ready_reason(
                missing=missing_context,
                priced=_priced_count(entered_prices),
                proposal_state=proposal,
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
