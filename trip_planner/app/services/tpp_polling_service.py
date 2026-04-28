"""Workspace-level polling service for TPP proposal execution state."""

from __future__ import annotations

from typing import Any, Mapping

from trip_planner.app.models.tpp import PollingOutcome
from trip_planner.integrations.tpp.client import TPPContractError

_STATE_TO_OUTCOME: dict[str, PollingOutcome] = {
    "approved": PollingOutcome.APPROVED,
    "rejected": PollingOutcome.REJECTED,
    "failed": PollingOutcome.FAILED,
    "pending": PollingOutcome.PENDING,
}


def map_poll_response_state_to_outcome(state: str) -> PollingOutcome:
    """Map a normalized TPP poll-response state string to an application outcome."""
    normalized = state.strip().lower()
    outcome = _STATE_TO_OUTCOME.get(normalized)
    if outcome is None:
        raise TPPContractError(f"Unsupported TPP poll state {state!r}.")
    return outcome


class TPPPollingService:
    """Map poll response payload states to application outcomes."""

    def map_poll_response_to_outcome(
        self,
        poll_response_payload: Mapping[str, Any],
    ) -> PollingOutcome:
        state = poll_response_payload.get("state")
        if not isinstance(state, str) or not state.strip():
            raise TPPContractError("TPP poll response contract requires non-empty 'state'.")
        return map_poll_response_state_to_outcome(state)
