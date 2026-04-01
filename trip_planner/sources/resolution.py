"""Entity-resolution contracts between raw snapshots and normalized planning objects."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from trip_planner._validators import (
    require_float_mapping,
    require_non_empty,
    require_optional_non_empty,
    require_probability,
    require_string_mapping,
    require_strings,
)

from . import schema
from .provenance import ProvenanceReference


@dataclass(slots=True)
class MatchCandidate:
    candidate_id: str
    entity_scope: str
    option_kind: str
    match_strategy: str
    confidence: float
    source_record_ids: list[str] = field(default_factory=list)
    source_snapshot_ids: list[str] = field(default_factory=list)
    matched_fields: list[str] = field(default_factory=list)
    compared_entity_ids: list[str] = field(default_factory=list)
    score_breakdown: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.candidate_id, "candidate_id")
        if self.entity_scope not in schema.SOURCE_ENTITY_SCOPES:
            raise ValueError(
                f"entity_scope must be one of {schema.SOURCE_ENTITY_SCOPES}"
            )
        if self.option_kind not in schema.SOURCE_OPTION_KINDS:
            raise ValueError(f"option_kind must be one of {schema.SOURCE_OPTION_KINDS}")
        if self.match_strategy not in schema.RESOLUTION_MATCH_STRATEGIES:
            raise ValueError(
                f"match_strategy must be one of {schema.RESOLUTION_MATCH_STRATEGIES}"
            )
        require_probability(self.confidence, "confidence")
        require_strings(self.source_record_ids, "source_record_ids")
        require_strings(self.source_snapshot_ids, "source_snapshot_ids")
        require_strings(self.matched_fields, "matched_fields")
        require_strings(self.compared_entity_ids, "compared_entity_ids")
        require_float_mapping(self.score_breakdown, "score_breakdown")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AttributeConflict:
    conflict_id: str
    attribute_path: str
    reason: str
    status: str
    values_by_source: dict[str, str]
    selected_value: str = ""
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.conflict_id, "conflict_id")
        require_non_empty(self.attribute_path, "attribute_path")
        if self.reason not in schema.RESOLUTION_CONFLICT_REASONS:
            raise ValueError(
                f"reason must be one of {schema.RESOLUTION_CONFLICT_REASONS}"
            )
        if self.status not in schema.RESOLUTION_CONFLICT_STATUSES:
            raise ValueError(
                f"status must be one of {schema.RESOLUTION_CONFLICT_STATUSES}"
            )
        require_string_mapping(self.values_by_source, "values_by_source")
        for source_id, value in self.values_by_source.items():
            require_non_empty(value, f"values_by_source[{source_id}]")
        require_optional_non_empty(self.selected_value or None, "selected_value")
        require_strings(self.notes, "notes")
        if len(self.values_by_source) < 2:
            raise ValueError("values_by_source must include at least two source values")
        if self.status == "selected" and not self.selected_value:
            raise ValueError("selected_value is required when status is selected")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MergedEntityProvenance:
    canonical_entity_id: str
    entity_scope: str
    source_record_ids: list[str] = field(default_factory=list)
    source_snapshot_ids: list[str] = field(default_factory=list)
    provenance_refs: list[ProvenanceReference] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.canonical_entity_id, "canonical_entity_id")
        if self.entity_scope not in schema.SOURCE_ENTITY_SCOPES:
            raise ValueError(
                f"entity_scope must be one of {schema.SOURCE_ENTITY_SCOPES}"
            )
        require_strings(self.source_record_ids, "source_record_ids")
        require_strings(self.source_snapshot_ids, "source_snapshot_ids")
        if any(
            not isinstance(item, ProvenanceReference) for item in self.provenance_refs
        ):
            raise ValueError(
                "provenance_refs must contain ProvenanceReference instances"
            )
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EntityResolution:
    resolution_id: str
    entity_scope: str
    option_kind: str
    status: str
    canonical_entity_id: str
    summary: str
    match_candidates: list[MatchCandidate] = field(default_factory=list)
    conflicts: list[AttributeConflict] = field(default_factory=list)
    merged_provenance: MergedEntityProvenance | None = None
    review_required: bool = False
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.resolution_id, "resolution_id")
        require_non_empty(self.canonical_entity_id, "canonical_entity_id")
        require_non_empty(self.summary, "summary")
        if self.entity_scope not in schema.SOURCE_ENTITY_SCOPES:
            raise ValueError(
                f"entity_scope must be one of {schema.SOURCE_ENTITY_SCOPES}"
            )
        if self.option_kind not in schema.SOURCE_OPTION_KINDS:
            raise ValueError(f"option_kind must be one of {schema.SOURCE_OPTION_KINDS}")
        if self.status not in schema.RESOLUTION_STATUSES:
            raise ValueError(f"status must be one of {schema.RESOLUTION_STATUSES}")
        if any(not isinstance(item, MatchCandidate) for item in self.match_candidates):
            raise ValueError("match_candidates must contain MatchCandidate instances")
        if any(not isinstance(item, AttributeConflict) for item in self.conflicts):
            raise ValueError("conflicts must contain AttributeConflict instances")
        if self.merged_provenance is not None and not isinstance(
            self.merged_provenance, MergedEntityProvenance
        ):
            raise ValueError(
                "merged_provenance must be a MergedEntityProvenance when provided"
            )
        require_strings(self.notes, "notes")
        if self.status == "match" and not self.match_candidates:
            raise ValueError(
                "match resolutions must include at least one match candidate"
            )
        if self.status == "ambiguous":
            if not self.review_required:
                raise ValueError("ambiguous resolutions must set review_required")
            if not self.conflicts:
                raise ValueError(
                    "ambiguous resolutions must preserve explicit conflicts"
                )
        if self.status == "distinct" and self.merged_provenance is None:
            raise ValueError(
                "distinct resolutions still require merged_provenance context"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
