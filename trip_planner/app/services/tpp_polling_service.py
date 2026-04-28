"""Workspace-level polling service for TPP proposal execution state."""

from __future__ import annotations

from collections.abc import Callable
from time import monotonic
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

    def __init__(
        self,
        poll_response_provider: Callable[[str], Mapping[str, Any]] | None = None,
        *,
        timeout_seconds: float = 30.0,
        now: Callable[[], float] | None = None,
    ) -> None:
        self._poll_response_provider = poll_response_provider
        self._timeout_seconds = timeout_seconds
        self._now = now or monotonic
        self._poll_started_at: float | None = None

    def map_poll_response_to_outcome(
        self,
        poll_response_payload: Mapping[str, Any],
    ) -> PollingOutcome:
        state = poll_response_payload.get("state")
        if not isinstance(state, str) or not state.strip():
            raise TPPContractError("TPP poll response contract requires non-empty 'state'.")
        return map_poll_response_state_to_outcome(state)

    def poll(self, proposal_id: str) -> PollingOutcome:
        if self._poll_response_provider is None:
            raise ValueError("poll_response_provider is required to poll proposal status.")
        if not proposal_id.strip():
            raise ValueError("proposal_id must be a non-empty string")

        now = self._now()
        if self._poll_started_at is None:
            self._poll_started_at = now

        payload = self._poll_response_provider(proposal_id)
        outcome = self.map_poll_response_to_outcome(payload)
        if outcome is PollingOutcome.PENDING:
            if now - self._poll_started_at > self._timeout_seconds:
                self._poll_started_at = None
                return PollingOutcome.TIMEOUT
            return PollingOutcome.PENDING

        self._poll_started_at = None
        return outcome
