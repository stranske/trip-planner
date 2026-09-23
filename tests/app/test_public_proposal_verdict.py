"""The verdict must survive a reload.

The public workspace payload filters the proposal summary through an allowlist, which
dropped the outcome, the rule codes and the verdict status. Observed 2026-09-22 against a
live TPP service: after a reload the Policy tab said "Policy not yet evaluated" and the
printed packet said "Policy verdict: Not evaluated" for a trip TPP had reviewed and blocked.
"""

from trip_planner.app.services.workspace import _public_workspace_proposal_state


def _stored_blocked_state() -> dict:
    """The stored shape after a live TPP policy block."""

    return {
        "proposal": {"approval_notes": ["Submitted from the workspace Policy tab."]},
        "evaluation": {"evaluation_result": {"status": "non_compliant", "failure_reasons": []}},
        "summary": {
            "submission_status": "failed",
            "submission_outcome": "blocked_by_policy",
            "submission_blocking_codes": ["fare_comparison", "fare_evidence", "non_reimbursable"],
            "evaluation_result_status": "non_compliant",
            "submission_summary": "Proposal submission blocked by the current policy verdict.",
            "approval_ready": False,
        },
        "follow_up": {},
    }


def test_the_policy_outcome_reaches_the_public_payload() -> None:
    public = _public_workspace_proposal_state(_stored_blocked_state())
    assert public is not None
    summary = public["summary"]
    assert summary["submission_outcome"] == "blocked_by_policy"
    assert summary["submission_blocking_codes"] == [
        "fare_comparison",
        "fare_evidence",
        "non_reimbursable",
    ]
    assert summary["evaluation_result_status"] == "non_compliant"


def test_raw_transport_fields_stay_debug_only() -> None:
    """#1130 / #1152 keep transport fields out of the default payload; the outcome replaces them."""

    public = _public_workspace_proposal_state(_stored_blocked_state())
    assert public is not None
    assert "submission_status" not in public["summary"]
    assert "evaluation_transport_status" not in public["summary"]


def test_raw_evaluation_detail_stays_private() -> None:
    """The allowlist still does its original job: the raw evaluation record is not exposed."""

    public = _public_workspace_proposal_state(_stored_blocked_state())
    assert public is not None
    assert public["evaluation"] == {"evaluation_result": None}
