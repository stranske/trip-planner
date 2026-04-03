"""Persistence architecture boundary markers for saved trips and planning state."""

from __future__ import annotations

PERSISTENCE_BOUNDED_CONTEXTS: tuple[str, ...] = (
    "profiles",
    "trips",
    "scenarios",
    "budgets",
    "sessions",
)

PERSISTENCE_CHILD_ISSUES: dict[str, int] = {
    "profiles": 538,
    "trips": 539,
    "scenarios": 540,
    "budgets": 541,
    "sessions": 542,
}

__all__ = [
    "PERSISTENCE_BOUNDED_CONTEXTS",
    "PERSISTENCE_CHILD_ISSUES",
]
