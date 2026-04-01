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

SOURCE_ENTITY_SCOPES: tuple[str, ...] = (
    "lodging",
    "transport",
    "activity",
    "destination",
    "managed_travel",
    "mixed",
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

ADAPTER_CAPABILITIES: tuple[str, ...] = (
    "fetch_live",
    "read_fixture",
    "read_file",
    "supports_incremental",
    "supports_normalization_handoff",
)

SNAPSHOT_STATUSES: tuple[str, ...] = (
    "complete",
    "partial",
    "failed",
    "stale",
)

HANDOFF_STATUSES: tuple[str, ...] = (
    "not_started",
    "ready",
    "partial",
    "blocked",
)

ADAPTER_ISSUE_STAGES: tuple[str, ...] = (
    "availability",
    "request",
    "fetch",
    "decode",
    "validation",
    "freshness",
    "handoff",
)

ADAPTER_ISSUE_SEVERITIES: tuple[str, ...] = (
    "info",
    "warning",
    "error",
)

RESOLUTION_STATUSES: tuple[str, ...] = (
    "match",
    "ambiguous",
    "distinct",
    "blocked",
)

RESOLUTION_MATCH_STRATEGIES: tuple[str, ...] = (
    "provider_id",
    "geo_text",
    "route_signature",
    "policy_scope",
    "manual_review",
)

RESOLUTION_CONFLICT_REASONS: tuple[str, ...] = (
    "low_confidence",
    "source_disagreement",
    "incomplete_data",
    "freshness_gap",
    "policy_conflict",
)

RESOLUTION_CONFLICT_STATUSES: tuple[str, ...] = (
    "preserved",
    "selected",
    "needs_review",
)

DEDUP_DECISIONS: tuple[str, ...] = (
    "merge",
    "keep_separate",
    "needs_review",
    "suppress",
)
