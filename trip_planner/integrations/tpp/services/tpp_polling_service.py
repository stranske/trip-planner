"""Workspace-level polling service for TPP proposal execution state."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import time
from typing import Any

from trip_planner.integrations.tpp.client import TPPContractError
from trip_planner.integrations.tpp.contracts import (
    TPPExecutionStatus,
    TPPRequestEnvelope,
    TPPResponseEnvelope,
)


def _next_wait(attempt: int) -> float:
    """Return exponential backoff wait in seconds with a 30s cap."""
    if attempt < 1:
        raise ValueError("attempt must be >= 1")
    return min(2 ** (attempt - 1), 30)


class TPPPollingService:
    """Drive polling to terminal state or timeout and return a response envelope."""

    def __init__(
        self,
        poll_response_provider: Callable[
            [TPPRequestEnvelope], TPPResponseEnvelope | Mapping[str, Any]
        ],
        *,
        timeout_seconds: float,
        sleeper: Callable[[float], None] = time.sleep,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        self._poll_response_provider = poll_response_provider
        self._timeout_seconds = timeout_seconds
        self._sleeper = sleeper
        self._now = now

    def poll(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        if not isinstance(request, TPPRequestEnvelope):
            raise ValueError("request must be a TPPRequestEnvelope")

        started_at = self._now()
        deadline = started_at + self._timeout_seconds
        attempt = 1

        while True:
            envelope = self._normalize_poll_response(self._poll_response_provider(request))
            if self._is_terminal(envelope):
                return envelope

            remaining = deadline - self._now()
            if remaining <= 0:
                return self._timeout_response(request)

            wait_seconds = min(_next_wait(attempt), remaining)
            self._sleeper(wait_seconds)
            attempt += 1

            if self._now() >= deadline:
                return self._timeout_response(request)

    def _normalize_poll_response(
        self, response: TPPResponseEnvelope | Mapping[str, Any]
    ) -> TPPResponseEnvelope:
        if isinstance(response, TPPResponseEnvelope):
            return response
        if isinstance(response, Mapping):
            try:
                return TPPResponseEnvelope.from_dict(dict(response))
            except (KeyError, TypeError, ValueError) as exc:
                raise TPPContractError("Malformed TPP poll response envelope.") from exc
        raise TPPContractError("TPP poll response contract requires an object payload.")

    @staticmethod
    def _is_terminal(envelope: TPPResponseEnvelope) -> bool:
        if envelope.execution_status.terminal:
            return True
        return envelope.execution_status.state in {"succeeded", "failed", "cancelled"}

    @staticmethod
    def _timeout_response(request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        return TPPResponseEnvelope(
            operation=request.operation,
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            transport_pattern=request.transport_pattern,
            execution_status=TPPExecutionStatus(
                state="timeout",
                terminal=True,
                summary="timeout",
                external_status="timeout",
            ),
            result_payload={},
        )
