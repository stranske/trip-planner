"""Raw snapshot and normalization-handoff contracts for source adapters."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from trip_planner._validators import (
    require_non_empty,
    require_non_negative,
    require_optional_non_empty,
    require_string_mapping,
    require_strings,
)

from . import schema
from .provenance import ProvenanceReference


@dataclass(slots=True)
class SourceQuery:
    query_id: str
    entity_scope: str
    option_kind: str
    market: str = ""
    locale: str = ""
    currency: str = ""
    traveler_segment: str = ""
    trip_phase: str = ""
    requested_at: str = ""
    origin: str = ""
    destination: str = ""
    waypoints: list[str] = field(default_factory=list)
    filters: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.query_id, "query_id")
        if self.entity_scope not in schema.SOURCE_ENTITY_SCOPES:
            raise ValueError(f"entity_scope must be one of {schema.SOURCE_ENTITY_SCOPES}")
        if self.option_kind not in schema.SOURCE_OPTION_KINDS:
            raise ValueError(f"option_kind must be one of {schema.SOURCE_OPTION_KINDS}")
        for field_name in (
            "market",
            "locale",
            "currency",
            "traveler_segment",
            "trip_phase",
            "requested_at",
            "origin",
            "destination",
        ):
            require_optional_non_empty(getattr(self, field_name) or None, field_name)
        require_strings(self.waypoints, "waypoints")
        require_string_mapping(self.filters, "filters")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AdapterIssue:
    issue_id: str
    stage: str
    severity: str
    code: str
    message: str
    observed_at: str = ""
    provider_status: str = ""
    retriable: bool = False
    affected_record_ids: list[str] = field(default_factory=list)
    details: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.issue_id, "issue_id")
        require_non_empty(self.code, "code")
        require_non_empty(self.message, "message")
        if self.stage not in schema.ADAPTER_ISSUE_STAGES:
            raise ValueError(f"stage must be one of {schema.ADAPTER_ISSUE_STAGES}")
        if self.severity not in schema.ADAPTER_ISSUE_SEVERITIES:
            raise ValueError(f"severity must be one of {schema.ADAPTER_ISSUE_SEVERITIES}")
        require_optional_non_empty(self.observed_at or None, "observed_at")
        require_optional_non_empty(self.provider_status or None, "provider_status")
        require_strings(self.affected_record_ids, "affected_record_ids")
        require_string_mapping(self.details, "details")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RawSourceRecord:
    record_id: str
    entity_scope: str
    provider_entity_id: str
    payload_type: str
    payload: dict[str, Any]
    content_language: str = ""
    captured_at: str = ""
    payload_locator: str = ""
    payload_checksum: str = ""
    provenance_hint: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.record_id, "record_id")
        require_non_empty(self.provider_entity_id, "provider_entity_id")
        require_non_empty(self.payload_type, "payload_type")
        if self.entity_scope not in schema.SOURCE_ENTITY_SCOPES:
            raise ValueError(f"entity_scope must be one of {schema.SOURCE_ENTITY_SCOPES}")
        if not isinstance(self.payload, dict):
            raise ValueError("payload must be a dict")
        for field_name in (
            "content_language",
            "captured_at",
            "payload_locator",
            "payload_checksum",
            "provenance_hint",
        ):
            require_optional_non_empty(getattr(self, field_name) or None, field_name)
        require_string_mapping(self.metadata, "metadata")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RawSnapshot:
    snapshot_id: str
    adapter_id: str
    source_id: str
    source_category: str
    entity_scope: str
    option_kind: str
    fetched_at: str
    query: SourceQuery
    records: list[RawSourceRecord] = field(default_factory=list)
    issues: list[AdapterIssue] = field(default_factory=list)
    payload_format: str = "json"
    transport: str = "api"
    snapshot_status: str = "complete"
    handoff_status: str = "not_started"
    expires_at: str = ""
    payload_metadata: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.snapshot_id, "snapshot_id")
        require_non_empty(self.adapter_id, "adapter_id")
        require_non_empty(self.source_id, "source_id")
        require_non_empty(self.fetched_at, "fetched_at")
        require_non_empty(self.payload_format, "payload_format")
        require_non_empty(self.transport, "transport")
        if self.source_category not in schema.SOURCE_CATEGORIES:
            raise ValueError(f"source_category must be one of {schema.SOURCE_CATEGORIES}")
        if self.entity_scope not in schema.SOURCE_ENTITY_SCOPES:
            raise ValueError(f"entity_scope must be one of {schema.SOURCE_ENTITY_SCOPES}")
        if self.option_kind not in schema.SOURCE_OPTION_KINDS:
            raise ValueError(f"option_kind must be one of {schema.SOURCE_OPTION_KINDS}")
        if self.snapshot_status not in schema.SNAPSHOT_STATUSES:
            raise ValueError(f"snapshot_status must be one of {schema.SNAPSHOT_STATUSES}")
        if self.handoff_status not in schema.HANDOFF_STATUSES:
            raise ValueError(f"handoff_status must be one of {schema.HANDOFF_STATUSES}")
        if not isinstance(self.query, SourceQuery):
            raise ValueError("query must be a SourceQuery")
        if any(not isinstance(item, RawSourceRecord) for item in self.records):
            raise ValueError("records must contain RawSourceRecord instances")
        if any(not isinstance(item, AdapterIssue) for item in self.issues):
            raise ValueError("issues must contain AdapterIssue instances")
        require_optional_non_empty(self.expires_at or None, "expires_at")
        require_string_mapping(self.payload_metadata, "payload_metadata")
        require_strings(self.notes, "notes")
        if self.snapshot_status == "failed" and self.records:
            raise ValueError("failed snapshots cannot contain records")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class NormalizationHandoff:
    handoff_id: str
    snapshot_id: str
    target_contract: str
    entity_scope: str
    status: str
    input_record_ids: list[str] = field(default_factory=list)
    blocked_issue_ids: list[str] = field(default_factory=list)
    provenance_refs: list[ProvenanceReference] = field(default_factory=list)
    record_count: int | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.handoff_id, "handoff_id")
        require_non_empty(self.snapshot_id, "snapshot_id")
        require_non_empty(self.target_contract, "target_contract")
        if self.entity_scope not in schema.SOURCE_ENTITY_SCOPES:
            raise ValueError(f"entity_scope must be one of {schema.SOURCE_ENTITY_SCOPES}")
        if self.status not in schema.HANDOFF_STATUSES:
            raise ValueError(f"status must be one of {schema.HANDOFF_STATUSES}")
        require_strings(self.input_record_ids, "input_record_ids")
        require_strings(self.blocked_issue_ids, "blocked_issue_ids")
        if any(not isinstance(item, ProvenanceReference) for item in self.provenance_refs):
            raise ValueError("provenance_refs must contain ProvenanceReference instances")
        if self.record_count is not None:
            require_non_negative(self.record_count, "record_count")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
