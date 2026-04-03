"""Client interfaces for Travel-Plan-Permission execution workflows."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from .contracts import TPPRequestEnvelope, TPPResponseEnvelope


class TPPIntegrationClient(Protocol):
    """Transport-neutral operations for the Travel-Plan-Permission boundary."""

    def fetch_policy_constraints(
        self, request: TPPRequestEnvelope
    ) -> TPPResponseEnvelope: ...

    def submit_proposal(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope: ...

    def fetch_evaluation_result(
        self, request: TPPRequestEnvelope
    ) -> TPPResponseEnvelope: ...

    def poll_execution_status(
        self, request: TPPRequestEnvelope
    ) -> TPPResponseEnvelope: ...


class BaseTPPIntegrationClient(ABC):
    """Validates operation routing while leaving transport details to subclasses."""

    def fetch_policy_constraints(
        self, request: TPPRequestEnvelope
    ) -> TPPResponseEnvelope:
        return self._dispatch("fetch_policy_constraints", request)

    def submit_proposal(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        return self._dispatch("submit_proposal", request)

    def fetch_evaluation_result(
        self, request: TPPRequestEnvelope
    ) -> TPPResponseEnvelope:
        return self._dispatch("fetch_evaluation_result", request)

    def poll_execution_status(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        return self._dispatch("poll_execution_status", request)

    def _dispatch(
        self, expected_operation: str, request: TPPRequestEnvelope
    ) -> TPPResponseEnvelope:
        if request.operation != expected_operation:
            raise ValueError(
                f"request.operation must be {expected_operation!r}, got {request.operation!r}"
            )
        return self.execute(request)

    @abstractmethod
    def execute(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        """Execute a validated TPP request through the concrete transport."""
