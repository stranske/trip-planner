"""What each Travel-Plan-Permission rule code means for the traveller, server side.

Mirrors `frontend/src/lib/policyCodes.ts` (tests/app/test_policy_code_parity.py fails if
the two lists of codes drift). The meaning is TPP's own failure message; the second
sentence says what the traveller can do about it in this product. A code not listed is
shown as-is: an unexplained code is better than a guessed explanation.
"""

from __future__ import annotations

from typing import Any

EXPLANATIONS: dict[str, tuple[str, str]] = {
    "fare_comparison": (
        "Fare comparison requires selected and lowest fare data.",
        "Enter the lowest fare you found for the same journey next to your flight price on "
        "the Budget tab, then submit again.",
    ),
    "fare_evidence": (
        "Screenshot or fare evidence must be attached to the request.",
        "Tick the fare-evidence box on the Budget tab once you hold a screenshot or quote, and "
        "give it to your approver with the packet.",
    ),
    "non_reimbursable": (
        "Expense details are required to check non-reimbursable items.",
        "List each expense on the Budget tab so it can be checked line by line.",
    ),
    "BUD-001": (
        "The trip total is over the travel policy's spending limit.",
        "Reduce the costs on the Budget tab, or ask your approver for an exception.",
    ),
}


def explain(code: str, tpp_message: str | None = None) -> str:
    """One sentence per code: TPP's words when it gave them, then what to do here."""

    known = EXPLANATIONS.get(code)
    meaning = (tpp_message or "").strip() or (known[0] if known else code)
    return f"{meaning} {known[1]} (rule {code})" if known else f"{meaning} (rule {code})"


def saved_verdict(proposal_state: Any) -> dict[str, Any] | None:
    """The saved submission outcome, from the public or the debug proposal shape."""

    if not isinstance(proposal_state, dict) or not proposal_state:
        return None
    summary = proposal_state.get("summary")
    summary = summary if isinstance(summary, dict) else {}
    evaluation = proposal_state.get("evaluation")
    result = evaluation.get("evaluation_result") if isinstance(evaluation, dict) else None
    result = result if isinstance(result, dict) else {}
    messages: dict[str, str] = {}
    follow_up = summary.get("follow_up")
    reasons = (follow_up.get("failure_reasons") if isinstance(follow_up, dict) else None) or []
    for reason in [*reasons, *(result.get("failure_reasons") or [])]:
        if isinstance(reason, dict) and reason.get("code") and reason.get("message"):
            messages[str(reason["code"])] = str(reason["message"])
    codes = [str(code) for code in summary.get("submission_blocking_codes") or []] or list(messages)
    return {
        "outcome": str(summary.get("submission_outcome") or ""),
        "verdict": str(result.get("status") or summary.get("evaluation_result_status") or ""),
        "codes": codes,
        "messages": messages,
    }
