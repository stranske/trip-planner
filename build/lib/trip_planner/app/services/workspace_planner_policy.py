"""Planner-panel policy and proposal presentation assembly."""

from __future__ import annotations

from typing import Any


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _proposal_inputs(
    policy_context: dict[str, Any] | None,
    proposal_context: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    proposal_state = None
    if proposal_context is not None and proposal_context.get("proposal_state") is not None:
        proposal_state = dict(proposal_context["proposal_state"])
    if proposal_state is not None:
        evaluation = _dict(proposal_state.get("evaluation")).get("evaluation_result")
        proposal = proposal_state.get("proposal")
    else:
        evaluation = policy_context.get("policy_evaluation") if policy_context else None
        proposal = policy_context.get("proposal") if policy_context else None
    return (
        proposal_state,
        dict(evaluation) if isinstance(evaluation, dict) else None,
        dict(proposal) if isinstance(proposal, dict) else None,
    )


def _transport_error_code(error_record: dict[str, Any]) -> str | None:
    code = error_record.get("code") or error_record.get("error_code")
    if isinstance(code, str) and code:
        return code
    details = _dict(error_record.get("details"))
    details_code = details.get("error_code")
    return details_code if isinstance(details_code, str) and details_code else None


def _transport_fallback_output(
    trip: dict[str, Any], *, source: str, error_code: str
) -> dict[str, Any]:
    timed_out = error_code == "timeout"
    return {
        "output_id": f"output:{trip['trip_id']}:{source}-transport-fallback",
        "title": (
            "Approval service request timed out"
            if timed_out
            else "Approval service is temporarily unavailable"
        ),
        "body": (
            "The workspace is using the latest saved approval information while the live "
            "service recovers."
        ),
        "tags": [source, "transport", "stored-policy", trip["mode"]],
        "status": "caution",
        "highlights": [
            "Saved approval information is still available.",
            "Retry the live approval refresh later.",
        ],
    }


def _policy_ready_output(trip: dict[str, Any], policy_evaluation: dict[str, Any]) -> dict[str, Any]:
    status = policy_evaluation["status"]
    return {
        "output_id": f"output:{trip['trip_id']}:policy-ready",
        "title": "Approval readiness loaded",
        "body": "The workspace is using saved approval inputs instead of placeholder readiness state.",
        "tags": ["policy", "workspace", trip["mode"]],
        "status": (
            "positive"
            if status == "compliant"
            else "critical" if status == "non_compliant" else "caution"
        ),
        "highlights": list(policy_evaluation.get("notes") or [])[:3],
    }


def _policy_review_action(trip: dict[str, Any]) -> dict[str, Any]:
    return {
        "action_id": f"action:{trip['trip_id']}:review-policy",
        "action_kind": "prepare_approval",
        "label": "Review approval readiness",
        "description": "Inspect saved approval constraints and readiness before moving to submission work.",
        "emphasis": "primary",
        "target_section": "approval",
    }


def _proposal_lifecycle_output(trip: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    status = (
        "positive"
        if summary.get("approval_ready")
        else ("caution" if summary.get("evaluation_transport_status") else "neutral")
    )
    return {
        "output_id": f"output:{trip['trip_id']}:proposal-lifecycle",
        "title": "Approval packet loaded",
        "body": "The workspace now carries saved approval packet and review state.",
        "tags": ["proposal", "approval", trip["mode"]],
        "status": status,
        "highlights": list(summary.get("highlights") or [])[:3],
    }


def _proposal_transport_error(summary: dict[str, Any]) -> dict[str, Any] | None:
    submission = summary.get("submission_error")
    evaluation = summary.get("evaluation_error")
    if isinstance(submission, dict):
        return submission
    return evaluation if isinstance(evaluation, dict) else None


def _follow_up_output(trip: dict[str, Any], follow_up: dict[str, Any]) -> dict[str, Any]:
    status = str(follow_up.get("status") or "")
    presentation = (
        "positive"
        if status in {"resolved", "approval_pending"}
        else ("critical" if status == "reoptimization_required" else "caution")
    )
    return {
        "output_id": f"output:{trip['trip_id']}:proposal-follow-up",
        "title": follow_up.get("title") or "Proposal follow-up",
        "body": follow_up.get("summary")
        or "The workspace has a persisted follow-up path after policy evaluation.",
        "tags": ["proposal", "follow-up", trip["mode"]],
        "status": presentation,
        "highlights": list(follow_up.get("guidance") or [])[:2],
    }


def _follow_up_action(trip: dict[str, Any], follow_up: dict[str, Any]) -> dict[str, Any]:
    return {
        "action_id": f"action:{trip['trip_id']}:proposal-follow-up",
        "action_kind": follow_up.get("recommended_action") or "review_follow_up",
        "label": follow_up.get("recommended_label") or "Review proposal follow-up",
        "description": follow_up.get("summary")
        or "Inspect the persisted follow-up lane for the latest policy result.",
        "emphasis": "primary",
        "target_section": "approval",
    }


def build_planner_policy_proposal_block(
    *,
    trip: dict[str, Any],
    policy_context: dict[str, Any] | None,
    proposal_context: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build planner policy output without persistence or workspace wiring."""

    proposal_state, policy_evaluation, proposal = _proposal_inputs(policy_context, proposal_context)
    outputs: list[dict[str, Any]] = []
    next_actions: list[dict[str, Any]] = []
    if policy_evaluation is not None:
        outputs.append(_policy_ready_output(trip, policy_evaluation))
        next_actions.append(_policy_review_action(trip))

    policy_summary = _dict(policy_context.get("summary")) if policy_context else {}
    policy_error = _transport_error_code(_dict(policy_summary.get("transport_error")))
    if policy_summary.get("status") == "stored_policy_fallback" and policy_error in {
        "breaker_open",
        "timeout",
    }:
        outputs.append(_transport_fallback_output(trip, source="policy", error_code=policy_error))

    if proposal_state is not None:
        summary = _dict(proposal_state.get("summary"))
        follow_up = _dict(proposal_state.get("follow_up"))
        outputs.append(_proposal_lifecycle_output(trip, summary))
        transport_error = _proposal_transport_error(summary)
        error_code = _transport_error_code(transport_error) if transport_error else None
        if error_code in {"breaker_open", "timeout"}:
            outputs.append(
                _transport_fallback_output(trip, source="proposal", error_code=error_code)
            )
        if follow_up:
            outputs.append(_follow_up_output(trip, follow_up))
            next_actions.insert(0, _follow_up_action(trip, follow_up))

    return {
        "proposal": proposal,
        "policy_evaluation": policy_evaluation,
        "outputs": outputs,
        "next_step_actions": next_actions,
    }
