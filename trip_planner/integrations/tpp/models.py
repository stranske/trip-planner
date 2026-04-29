"""TPP application model types."""

from __future__ import annotations

from enum import StrEnum


class PollingOutcome(StrEnum):
    """Application-level outcomes for TPP polling workflow state transitions."""

    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"
    PENDING = "pending"
    TIMEOUT = "timeout"
