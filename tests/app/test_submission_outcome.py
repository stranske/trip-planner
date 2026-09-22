"""A policy refusal is a verdict, not a failure.

TPP answers a non-compliant proposal with `state: "failed"`, `queue_state:
"blocked_by_policy"`, and the rule codes that blocked it. A transport failure arrives as
`state: "failed"` too, and means the opposite: we never got an answer.

Reporting both as "failed" throws away the most useful thing this product produces — the
named reasons an employer's policy rejected the plan. Verified against a live TPP service
on 2026-09-22, which returned blocking codes `fare_comparison`, `fare_evidence` and
`non_reimbursable` for an ordinary Chicago trip.
"""

from typing import Any

from trip_planner.app.services.proposal import _build_summary

PROPOSAL: dict[str, Any] = {
    "trip_id": "trip-chicago",
    "proposal_id": "proposal:trip-chicago",
    "approval_notes": ["Submitted from the workspace Policy tab."],
    "comparables": [],
}


def _summary(submission: dict[str, Any]) -> dict[str, Any]:
    return _build_summary(
        submission_record=submission,
        evaluation_record={},
        proposal_payload=PROPOSAL,
    )


def _blocked_submission() -> dict[str, Any]:
    """The shape a live TPP service actually returned."""

    return {
        "execution_status": {
            "state": "failed",
            "terminal": True,
            "summary": "Proposal submission blocked by the current policy verdict.",
            "external_status": "409 Conflict",
        },
        "queue_state": "blocked_by_policy",
        "response_payload": {
            "execution_id": "exec-dcdb1663a9e3",
            "queue_state": "blocked_by_policy",
            "blocking_codes": ["fare_comparison", "fare_evidence", "non_reimbursable"],
        },
        "error": {
            "code": "proposal_blocked_by_policy",
            "message": "The proposal has blocking policy violations and cannot be submitted.",
            "category": "policy",
            "retryable": False,
        },
        "linkage": {"proposal_version": "v1"},
    }


def test_a_policy_block_is_not_reported_as_a_failure() -> None:
    summary = _summary(_blocked_submission())

    assert summary["submission_outcome"] == "blocked_by_policy"
    # The raw transport state is preserved; it is the interpretation that changes.
    assert summary["submission_status"] == "failed"


def test_the_blocking_rule_codes_survive_to_the_surface() -> None:
    summary = _summary(_blocked_submission())

    assert summary["submission_blocking_codes"] == [
        "fare_comparison",
        "fare_evidence",
        "non_reimbursable",
    ]


def test_the_traveller_is_told_which_rules_blocked_it() -> None:
    summary = _summary(_blocked_submission())

    # Not a generic "submission failed": the named reasons, in the highlights a traveller
    # reads first.
    assert any("fare_comparison" in highlight for highlight in summary["highlights"])
    assert any("Policy blocked" in highlight for highlight in summary["highlights"])


def test_a_transport_failure_is_still_a_failure() -> None:
    """The opposite case must not be relabelled. We never got an answer here."""

    summary = _summary(
        {
            "execution_status": {"state": "failed", "terminal": True, "summary": "timeout"},
            "queue_state": None,
            "response_payload": {},
            "error": {"code": "timeout", "category": "transport", "retryable": True},
            "linkage": {"proposal_version": "v1"},
        }
    )

    assert summary["submission_outcome"] == "failed"
    assert summary["submission_blocking_codes"] == []
    assert not any("Policy blocked" in highlight for highlight in summary["highlights"])


def test_an_accepted_submission_is_neither() -> None:
    summary = _summary(
        {
            "execution_status": {"state": "accepted", "terminal": False, "summary": "queued"},
            "queue_state": "queued",
            "response_payload": {"queue_state": "queued"},
            "error": {},
            "linkage": {"proposal_version": "v1"},
        }
    )

    assert summary["submission_outcome"] == "accepted"
    assert summary["submission_blocking_codes"] == []


def test_a_policy_block_is_recognised_from_either_signal() -> None:
    """queue_state and error.category are independent tells; either alone is enough."""

    only_queue = _blocked_submission()
    only_queue["error"] = {}
    assert _summary(only_queue)["submission_outcome"] == "blocked_by_policy"

    only_category = _blocked_submission()
    only_category["queue_state"] = "unknown"
    only_category["response_payload"]["queue_state"] = "unknown"
    assert _summary(only_category)["submission_outcome"] == "blocked_by_policy"
