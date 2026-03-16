"""Schema constants for source and provenance contracts."""

from __future__ import annotations

SCHEMA_VERSION = "0.1.0"

SOURCE_CATEGORIES: tuple[str, ...] = (
    "commercial_inventory",
    "ratings_reviews",
    "editorial",
    "specialist_non_commercial",
    "official_operational",
    "managed_travel_policy",
)

COVERAGE_SCOPES: tuple[str, ...] = (
    "global",
    "national",
    "regional",
    "local",
    "route",
    "property",
    "event",
)

SOURCE_OPTION_KINDS: tuple[str, ...] = (
    "route",
    "lodging",
    "flight",
    "rail",
    "car",
    "activity",
    "mixed",
    "policy",
)

BUSINESS_APPROVAL_STATUSES: tuple[str, ...] = (
    "unknown",
    "approved",
    "preferred",
    "restricted",
    "disallowed",
)

PROVENANCE_SUBJECT_KINDS: tuple[str, ...] = (
    "destination",
    "place",
    "option",
    "option_set",
    "proposal",
    "policy_evaluation",
)

CONTRIBUTION_KINDS: tuple[str, ...] = (
    "inventory",
    "pricing",
    "rating",
    "review",
    "editorial",
    "operational",
    "policy",
    "availability",
    "comparison",
)
