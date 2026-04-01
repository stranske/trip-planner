"""Schema constants for the canonical business travel profile."""

from __future__ import annotations

from typing import Final

SCHEMA_VERSION: Final[str] = "0.1.0"
PROFILE_KIND: Final[str] = "business"

EMPLOYEE_TYPES: Final[tuple[str, ...]] = ("employee", "contractor", "guest")
TRAVELER_EXPERIENCE_LEVELS: Final[tuple[str, ...]] = ("frequent", "occasional")
PURPOSE_TYPES: Final[tuple[str, ...]] = (
    "client_meeting",
    "conference",
    "internal_meeting",
    "site_visit",
    "training",
    "other",
)
TRIP_CRITICALITY_LEVELS: Final[tuple[str, ...]] = ("low", "medium", "high")
ARRIVAL_BUFFER_PREFERENCES: Final[tuple[str, ...]] = (
    "tight",
    "moderate",
    "conservative",
)
EXCEPTION_FALLBACK_MODES: Final[tuple[str, ...]] = (
    "nearest_compliant",
    "document_exception_candidate",
    "manual_review",
)
