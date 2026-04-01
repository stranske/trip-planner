"""Shared ingestion result contracts and helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from trip_planner._validators import require_non_empty, require_non_negative, require_strings
from trip_planner.sources import (
    AdapterIssue,
    AttributeConflict,
    NormalizationHandoff,
    ProvenanceReference,
    QualityValueFitSummary,
    RawSnapshot,
    RawSourceRecord,
    SourceTrustSignals,
)


@dataclass(slots=True)
class IngestionWarning:
    warning_id: str
    severity: str
    code: str
    message: str
    record_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.warning_id, "warning_id")
        require_non_empty(self.severity, "severity")
        require_non_empty(self.code, "code")
        require_non_empty(self.message, "message")
        require_strings(self.record_ids, "record_ids")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class IngestionSummary:
    total_records: int
    emitted_options: int
    skipped_records: int = 0
    degraded_options: int = 0
    unresolved_conflicts: int = 0
    low_confidence_option_ids: list[str] = field(default_factory=list)
    filtered_record_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in (
            "total_records",
            "emitted_options",
            "skipped_records",
            "degraded_options",
            "unresolved_conflicts",
        ):
            require_non_negative(getattr(self, field_name), field_name)
        require_strings(self.low_confidence_option_ids, "low_confidence_option_ids")
        require_strings(self.filtered_record_ids, "filtered_record_ids")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_provenance_reference(
    snapshot: RawSnapshot,
    record: RawSourceRecord,
    *,
    subject_id: str,
    summary: str,
    contribution_kind: str = "inventory",
) -> ProvenanceReference:
    payload = record.payload
    trust_payload = payload.get("trust_signals", {})
    quality_payload = payload.get("quality_value_fit", {})
    return ProvenanceReference(
        provenance_id=f"{snapshot.snapshot_id}:{record.record_id}",
        source_id=snapshot.source_id,
        source_category=snapshot.source_category,
        subject_kind="option",
        subject_id=subject_id,
        contribution_kind=contribution_kind,
        summary=summary,
        locator=record.payload_locator or payload.get("booking_url", ""),
        captured_at=record.captured_at or snapshot.fetched_at,
        freshness_days_at_capture=trust_payload.get("freshness_days", payload.get("freshness_days")),
        trust_snapshot=SourceTrustSignals(**trust_payload) if trust_payload else None,
        quality_value_fit=QualityValueFitSummary(**quality_payload) if quality_payload else None,
        notes=payload.get("provenance_notes", []),
    )


def warning_from_issue(issue: AdapterIssue) -> IngestionWarning:
    return IngestionWarning(
        warning_id=issue.issue_id,
        severity=issue.severity,
        code=issue.code,
        message=issue.message,
        record_ids=issue.affected_record_ids,
    )


def unresolved_conflicts(conflicts: list[AttributeConflict]) -> list[AttributeConflict]:
    return [conflict for conflict in conflicts if conflict.status != "selected"]


def make_handoff(
    snapshot: RawSnapshot,
    *,
    target_contract: str,
    status: str,
    input_record_ids: list[str],
    blocked_issue_ids: list[str],
    provenance_refs: list[ProvenanceReference],
    notes: list[str],
) -> NormalizationHandoff:
    return NormalizationHandoff(
        handoff_id=f"{snapshot.snapshot_id}:{target_contract.lower()}",
        snapshot_id=snapshot.snapshot_id,
        target_contract=target_contract,
        entity_scope=snapshot.entity_scope,
        status=status,
        input_record_ids=input_record_ids,
        blocked_issue_ids=blocked_issue_ids,
        provenance_refs=provenance_refs,
        record_count=len(input_record_ids),
        notes=notes,
    )
