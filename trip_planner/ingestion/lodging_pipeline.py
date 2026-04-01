"""Lodging ingestion scaffolding from raw snapshots to normalized options."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from trip_planner._validators import require_non_empty, require_strings
from trip_planner.contracts import MoneyRange as _MoneyRange
from trip_planner.options.lodging import LodgingOption
from trip_planner.sources import (
    AttributeConflict,
    DeduplicationDecision,
    EntityResolution,
    NormalizationHandoff,
    ProvenanceReference,
    RawSnapshot,
    RawSourceRecord,
)

from ._common import (
    IngestionSummary,
    IngestionWarning,
    build_provenance_reference,
    make_handoff,
    unresolved_conflicts,
    warning_from_issue,
)

assert _MoneyRange


@dataclass(slots=True)
class LodgingIngestionResult:
    pipeline_id: str
    snapshot_id: str
    lodging_options: list[LodgingOption] = field(default_factory=list)
    unresolved_conflicts: list[AttributeConflict] = field(default_factory=list)
    warnings: list[IngestionWarning] = field(default_factory=list)
    handoff: NormalizationHandoff | None = None
    summary: IngestionSummary = field(default_factory=lambda: IngestionSummary(0, 0))
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.pipeline_id, "pipeline_id")
        require_non_empty(self.snapshot_id, "snapshot_id")
        if any(not isinstance(item, LodgingOption) for item in self.lodging_options):
            raise ValueError("lodging_options must contain LodgingOption instances")
        if any(not isinstance(item, AttributeConflict) for item in self.unresolved_conflicts):
            raise ValueError("unresolved_conflicts must contain AttributeConflict instances")
        if any(not isinstance(item, IngestionWarning) for item in self.warnings):
            raise ValueError("warnings must contain IngestionWarning instances")
        if self.handoff is not None and not isinstance(self.handoff, NormalizationHandoff):
            raise ValueError("handoff must be a NormalizationHandoff when provided")
        if not isinstance(self.summary, IngestionSummary):
            raise ValueError("summary must be an IngestionSummary")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def ingest_lodging_snapshot(
    snapshot: RawSnapshot,
    *,
    resolutions: list[EntityResolution] | None = None,
    dedup_decisions: list[DeduplicationDecision] | None = None,
) -> LodgingIngestionResult:
    if snapshot.entity_scope != "lodging":
        raise ValueError("snapshot.entity_scope must be lodging")
    if snapshot.option_kind != "lodging":
        raise ValueError("snapshot.option_kind must be lodging")

    resolutions = resolutions or []
    dedup_decisions = dedup_decisions or []
    warnings = [warning_from_issue(issue) for issue in snapshot.issues]
    resolution_map = {resolution.resolution_id: resolution for resolution in resolutions}
    emitted_ids: set[str] = set()
    filtered_record_ids: list[str] = []
    low_confidence_option_ids: list[str] = []
    lodging_options: list[LodgingOption] = []
    preserved_conflicts: list[AttributeConflict] = []
    provenance_refs: list[ProvenanceReference] = []

    for decision in dedup_decisions:
        if decision.entity_scope != "lodging" or decision.option_kind != snapshot.option_kind:
            continue
        record_ids = _record_ids_for_decision(decision, resolution_map)
        preserved_conflicts.extend(unresolved_conflicts(decision.preserved_conflicts))
        if decision.decision == "suppress":
            emitted_ids.update(record_ids)
            filtered_record_ids.extend(
                record_id
                for record_id in record_ids
                if record_id not in filtered_record_ids
            )
            continue
        if decision.decision in {"keep_separate", "needs_review"}:
            continue
        if decision.decision != "merge":
            continue
        candidate_records = _records_for_decision(snapshot.records, decision, resolution_map)
        if not candidate_records:
            warnings.append(
                IngestionWarning(
                    warning_id=f"{decision.decision_id}:missing-records",
                    severity="warning",
                    code="missing_merge_records",
                    message="Dedup decision did not map to any raw lodging records.",
                )
            )
            continue
        option = _lodging_option_from_records(candidate_records, snapshot, decision.canonical_entity_id)
        option.notes.extend([f"dedup_decision:{decision.decision_id}", *decision.notes])
        option.feasibility.constraints.extend(
            [f"{conflict.attribute_path}:{conflict.reason}" for conflict in unresolved_conflicts(decision.preserved_conflicts)]
        )
        if decision.confidence < 0.75:
            low_confidence_option_ids.append(option.option_id)
        for record in candidate_records:
            record_warnings = record.payload.get("normalization_warnings", [])
            if record_warnings:
                warnings.append(
                    IngestionWarning(
                        warning_id=f"{record.record_id}:normalization",
                        severity="warning",
                        code="normalization_warning",
                        message="; ".join(record_warnings),
                        record_ids=[record.record_id],
                    )
                )
                option.notes.extend(record_warnings)
        lodging_options.append(option)
        emitted_ids.update(record.record_id for record in candidate_records)
        filtered_record_ids.extend(
            record.record_id for record in candidate_records[1:]
        )
        provenance_refs.extend(option.source_refs)

    for record in snapshot.records:
        if record.record_id in emitted_ids:
            continue
        resolution = _resolution_for_record(record.record_id, resolutions)
        option = _lodging_option_from_records([record], snapshot, _canonical_option_id(record, resolution))
        if resolution is not None:
            option.notes.extend([f"resolution:{resolution.resolution_id}", *resolution.notes])
            unresolved = unresolved_conflicts(resolution.conflicts)
            preserved_conflicts.extend(unresolved)
            option.feasibility.constraints.extend(
                [f"{conflict.attribute_path}:{conflict.reason}" for conflict in unresolved]
            )
            if resolution.review_required or _lowest_match_confidence(resolution) < 0.75:
                low_confidence_option_ids.append(option.option_id)
        record_warnings = record.payload.get("normalization_warnings", [])
        if record_warnings:
            warnings.append(
                IngestionWarning(
                    warning_id=f"{record.record_id}:normalization",
                    severity="warning",
                    code="normalization_warning",
                    message="; ".join(record_warnings),
                    record_ids=[record.record_id],
                )
            )
            option.notes.extend(record_warnings)
        lodging_options.append(option)
        provenance_refs.extend(option.source_refs)

    preserved_conflicts = _dedupe_conflicts(preserved_conflicts)
    handoff_status = "ready"
    if warnings or preserved_conflicts:
        handoff_status = "partial"
    if not lodging_options:
        handoff_status = "blocked"

    summary = IngestionSummary(
        total_records=len(snapshot.records),
        emitted_options=len(lodging_options),
        skipped_records=max(0, len(snapshot.records) - len(lodging_options)),
        degraded_options=sum(1 for option in lodging_options if option.notes),
        unresolved_conflicts=len(preserved_conflicts),
        low_confidence_option_ids=sorted(set(low_confidence_option_ids)),
        filtered_record_ids=filtered_record_ids,
    )
    handoff = make_handoff(
        snapshot,
        target_contract="LodgingOption",
        status=handoff_status,
        input_record_ids=[record.record_id for record in snapshot.records],
        blocked_issue_ids=[warning.warning_id for warning in warnings if warning.severity == "error"],
        provenance_refs=provenance_refs,
        notes=["Lodging ingestion scaffolding emitted normalized options from raw snapshots."],
    )
    return LodgingIngestionResult(
        pipeline_id=f"lodging-ingestion:{snapshot.snapshot_id}",
        snapshot_id=snapshot.snapshot_id,
        lodging_options=lodging_options,
        unresolved_conflicts=preserved_conflicts,
        warnings=warnings,
        handoff=handoff,
        summary=summary,
    )


def _records_for_decision(
    records: list[RawSourceRecord],
    decision: DeduplicationDecision,
    resolution_map: dict[str, EntityResolution],
) -> list[RawSourceRecord]:
    ordered_ids = _record_ids_for_decision(decision, resolution_map)
    if not ordered_ids:
        return []
    by_id = {record.record_id: record for record in records}
    return [by_id[record_id] for record_id in ordered_ids if record_id in by_id]


def _record_ids_for_decision(
    decision: DeduplicationDecision,
    resolution_map: dict[str, EntityResolution],
) -> list[str]:
    record_ids: list[str] = []
    for resolution_id in decision.resolution_ids:
        resolution = resolution_map.get(resolution_id)
        if resolution is None:
            continue
        for candidate in resolution.match_candidates:
            record_ids.extend(candidate.source_record_ids)
    return list(dict.fromkeys(record_ids))


def _lodging_option_from_records(
    records: list[RawSourceRecord],
    snapshot: RawSnapshot,
    option_id: str,
) -> LodgingOption:
    primary = records[0]
    payload = dict(primary.payload)
    payload["option_id"] = option_id
    if "destination_id" not in payload:
        location_summary = payload.get("location_summary") or {}
        payload["destination_id"] = location_summary.get("destination_id")
    payload.setdefault("source_refs", [])
    payload["source_refs"] = [
        build_provenance_reference(
            snapshot,
            record,
            subject_id=option_id,
            summary=f"Normalized lodging option sourced from {record.provider_entity_id}.",
        ).to_dict()
        for record in records
    ]
    payload.setdefault("notes", [])
    payload["notes"] = [
        *payload["notes"],
        *(record.payload.get("ingestion_notes", []) for record in records),
    ]
    flattened_notes: list[str] = []
    for item in payload["notes"]:
        if isinstance(item, list):
            flattened_notes.extend(item)
        else:
            flattened_notes.append(item)
    payload["notes"] = flattened_notes
    return LodgingOption.from_dict(payload)


def _resolution_for_record(
    record_id: str,
    resolutions: list[EntityResolution],
) -> EntityResolution | None:
    for resolution in resolutions:
        for candidate in resolution.match_candidates:
            if record_id in candidate.source_record_ids:
                return resolution
    return None


def _canonical_option_id(record: RawSourceRecord, resolution: EntityResolution | None) -> str:
    if resolution is not None:
        return resolution.canonical_entity_id
    return f"lodging-{record.provider_entity_id}"


def _lowest_match_confidence(resolution: EntityResolution) -> float:
    if not resolution.match_candidates:
        return 1.0
    return min(candidate.confidence for candidate in resolution.match_candidates)


def _dedupe_conflicts(conflicts: list[AttributeConflict]) -> list[AttributeConflict]:
    deduped: dict[str, AttributeConflict] = {}
    for conflict in conflicts:
        deduped[conflict.conflict_id] = conflict
    return list(deduped.values())
