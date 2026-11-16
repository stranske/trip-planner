"""Deduplication contracts built on top of entity-resolution records."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from trip_planner._validators import (
    require_non_empty,
    require_probability,
    require_strings,
)

from . import schema
from .resolution import AttributeConflict, MergedEntityProvenance


@dataclass(slots=True)
class DeduplicationDecision:
    decision_id: str
    entity_scope: str
    option_kind: str
    decision: str
    canonical_entity_id: str
    summary: str
    duplicate_entity_ids: list[str] = field(default_factory=list)
    resolution_ids: list[str] = field(default_factory=list)
    preserved_conflicts: list[AttributeConflict] = field(default_factory=list)
    merged_provenance: MergedEntityProvenance | None = None
    confidence: float = 0.0
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.decision_id, "decision_id")
        require_non_empty(self.canonical_entity_id, "canonical_entity_id")
        require_non_empty(self.summary, "summary")
        if self.entity_scope not in schema.SOURCE_ENTITY_SCOPES:
            raise ValueError(f"entity_scope must be one of {schema.SOURCE_ENTITY_SCOPES}")
        if self.option_kind not in schema.SOURCE_OPTION_KINDS:
            raise ValueError(f"option_kind must be one of {schema.SOURCE_OPTION_KINDS}")
        if self.decision not in schema.DEDUP_DECISIONS:
            raise ValueError(f"decision must be one of {schema.DEDUP_DECISIONS}")
        require_strings(self.duplicate_entity_ids, "duplicate_entity_ids")
        require_strings(self.resolution_ids, "resolution_ids")
        if any(not isinstance(item, AttributeConflict) for item in self.preserved_conflicts):
            raise ValueError("preserved_conflicts must contain AttributeConflict instances")
        if self.merged_provenance is not None and not isinstance(
            self.merged_provenance, MergedEntityProvenance
        ):
            raise ValueError("merged_provenance must be a MergedEntityProvenance when provided")
        require_probability(self.confidence, "confidence")
        require_strings(self.notes, "notes")
        if self.decision == "merge" and not self.duplicate_entity_ids:
            raise ValueError("merge decisions must identify duplicate_entity_ids")
        if self.decision in {"keep_separate", "needs_review"} and not self.preserved_conflicts:
            raise ValueError(
                f"{self.decision} decisions must preserve explicit conflicts for later review"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
