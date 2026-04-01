"""Destination ingestion scaffolding from raw snapshots to normalized places."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from trip_planner._validators import require_non_empty, require_strings
from trip_planner.options.destinations import Destination, DestinationSourceRef
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


@dataclass(slots=True)
class DestinationIngestionResult:
    pipeline_id: str
    snapshot_id: str
    destinations: list[Destination] = field(default_factory=list)
    unresolved_conflicts: list[AttributeConflict] = field(default_factory=list)
    warnings: list[IngestionWarning] = field(default_factory=list)
    handoff: NormalizationHandoff | None = None
    summary: IngestionSummary = field(default_factory=lambda: IngestionSummary(0, 0))
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.pipeline_id, "pipeline_id")
        require_non_empty(self.snapshot_id, "snapshot_id")
        if any(not isinstance(item, Destination) for item in self.destinations):
            raise ValueError("destinations must contain Destination instances")
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


def ingest_destination_snapshot(
    snapshot: RawSnapshot,
    *,
    resolutions: list[EntityResolution] | None = None,
    dedup_decisions: list[DeduplicationDecision] | None = None,
) -> DestinationIngestionResult:
    if snapshot.entity_scope != "destination":
        raise ValueError("snapshot.entity_scope must be destination")
    if snapshot.option_kind != "mixed":
        raise ValueError("snapshot.option_kind must be mixed")

    resolutions = resolutions or []
    dedup_decisions = dedup_decisions or []
    warnings = [warning_from_issue(issue) for issue in snapshot.issues]
    resolution_map = {resolution.resolution_id: resolution for resolution in resolutions}
    emitted_ids: set[str] = set()
    filtered_record_ids: list[str] = []
    low_confidence_destination_ids: list[str] = []
    destinations: list[Destination] = []
    preserved_conflicts: list[AttributeConflict] = []
    provenance_refs: list[ProvenanceReference] = []

    for decision in dedup_decisions:
        if decision.entity_scope != "destination" or decision.option_kind != snapshot.option_kind:
            continue
        record_ids = _record_ids_for_decision(decision, resolution_map)
        preserved_conflicts.extend(unresolved_conflicts(decision.preserved_conflicts))
        if decision.decision == "suppress":
            emitted_ids.update(record_ids)
            filtered_record_ids.extend(
                record_id for record_id in record_ids if record_id not in filtered_record_ids
            )
            continue
        if decision.decision in {"keep_separate", "needs_review"}:
            continue
        if decision.decision != "merge":
            continue
        records = _records_for_decision(snapshot.records, decision, resolution_map)
        if not records:
            warnings.append(
                IngestionWarning(
                    warning_id=f"{decision.decision_id}:missing-records",
                    severity="warning",
                    code="missing_merge_records",
                    message="Dedup decision did not map to any raw destination records.",
                )
            )
            continue
        destination, refs = _destination_from_records(records, snapshot, decision.canonical_entity_id)
        _append_record_warnings(destination, records, warnings)
        if decision.confidence < 0.75:
            low_confidence_destination_ids.append(destination.destination_id)
        destinations.append(destination)
        emitted_ids.update(record.record_id for record in records)
        filtered_record_ids.extend(record.record_id for record in records[1:])
        provenance_refs.extend(refs)

    for record in snapshot.records:
        if record.record_id in emitted_ids:
            continue
        resolution = _resolution_for_record(record.record_id, resolutions)
        destination_id = _canonical_destination_id(record, resolution)
        destination, refs = _destination_from_records([record], snapshot, destination_id)
        if resolution is not None:
            destination.source_refs.extend(
                _resolution_source_ref(snapshot, resolution, destination_id)
            )
            unresolved = unresolved_conflicts(resolution.conflicts)
            preserved_conflicts.extend(unresolved)
            if resolution.review_required or _lowest_match_confidence(resolution) < 0.75:
                low_confidence_destination_ids.append(destination.destination_id)
        _append_record_warnings(destination, [record], warnings)
        destinations.append(destination)
        provenance_refs.extend(refs)

    preserved_conflicts = _dedupe_conflicts(preserved_conflicts)
    handoff_status = "ready"
    if warnings or preserved_conflicts:
        handoff_status = "partial"
    if not destinations:
        handoff_status = "blocked"

    summary = IngestionSummary(
        total_records=len(snapshot.records),
        emitted_options=len(destinations),
        skipped_records=max(0, len(snapshot.records) - len(destinations)),
        degraded_options=sum(
            1
            for destination in destinations
            if destination.operational_notes
            or any(ref.notes for ref in destination.source_refs)
        ),
        unresolved_conflicts=len(preserved_conflicts),
        low_confidence_option_ids=sorted(set(low_confidence_destination_ids)),
        filtered_record_ids=filtered_record_ids,
    )
    handoff = make_handoff(
        snapshot,
        target_contract="Destination",
        status=handoff_status,
        input_record_ids=[record.record_id for record in snapshot.records],
        blocked_issue_ids=[warning.warning_id for warning in warnings if warning.severity == "error"],
        provenance_refs=provenance_refs,
        notes=[
            "Destination ingestion scaffolding emitted normalized place entities from raw snapshots."
        ],
    )
    return DestinationIngestionResult(
        pipeline_id=f"destination-ingestion:{snapshot.snapshot_id}",
        snapshot_id=snapshot.snapshot_id,
        destinations=destinations,
        unresolved_conflicts=preserved_conflicts,
        warnings=warnings,
        handoff=handoff,
        summary=summary,
    )


def _destination_from_records(
    records: list[RawSourceRecord],
    snapshot: RawSnapshot,
    destination_id: str,
) -> tuple[Destination, list[ProvenanceReference]]:
    primary = dict(records[0].payload)
    payload = _merge_destination_payload(records, primary)
    payload["destination_id"] = destination_id
    source_refs: list[DestinationSourceRef] = []
    provenance_refs: list[ProvenanceReference] = []
    for record in records:
        ref = build_provenance_reference(
            snapshot,
            record,
            subject_id=destination_id,
            subject_kind="destination",
            contribution_kind=_contribution_kind(snapshot.source_category),
            summary=f"Normalized destination sourced from {record.provider_entity_id}.",
        )
        source_refs.append(
            DestinationSourceRef(
                provenance_id=ref.provenance_id,
                role=_destination_role(snapshot.source_category),
                source_id=ref.source_id,
                source_category=ref.source_category,
                contribution_kind=ref.contribution_kind,
                summary=ref.summary,
                freshness_days_at_capture=ref.freshness_days_at_capture,
                notes=_merge_scalar_list(ref.notes, record.payload.get("ingestion_notes", [])),
            )
        )
        provenance_refs.append(ref)
    payload["source_refs"] = [ref.to_dict() for ref in source_refs]
    destination = Destination.from_dict(payload)
    return destination, provenance_refs


def _merge_destination_payload(
    records: list[RawSourceRecord],
    primary: dict[str, Any],
) -> dict[str, Any]:
    payload = dict(primary)
    for record in records[1:]:
        candidate = record.payload
        for field_name in (
            "parent_refs",
            "tags",
            "seasonal_signals",
            "experience_signals",
            "adjacency_refs",
            "region_expansion_refs",
            "operational_notes",
        ):
            payload[field_name] = _merge_sequence(
                payload.get(field_name, []),
                candidate.get(field_name, []),
            )
        if not payload.get("summary") and candidate.get("summary"):
            payload["summary"] = candidate["summary"]
        if not payload.get("geo") and candidate.get("geo"):
            payload["geo"] = candidate["geo"]
        payload["mobility_profile"] = _merge_mapping(
            payload.get("mobility_profile"),
            candidate.get("mobility_profile"),
        )
    return payload


def _append_record_warnings(
    destination: Destination,
    records: list[RawSourceRecord],
    warnings: list[IngestionWarning],
) -> None:
    for record in records:
        record_warnings = record.payload.get("normalization_warnings", [])
        if not record_warnings:
            continue
        warnings.append(
            IngestionWarning(
                warning_id=f"{record.record_id}:normalization",
                severity="warning",
                code="normalization_warning",
                message="; ".join(record_warnings),
                record_ids=[record.record_id],
            )
        )
        _extend_destination_notes(destination, list(record_warnings))


def _extend_destination_notes(destination: Destination, notes: list[str]) -> None:
    if not notes:
        return
    if destination.operational_notes:
        existing = destination.operational_notes[0].notes
        for note in notes:
            if note not in existing:
                existing.append(note)
        return
    if destination.source_refs:
        existing = destination.source_refs[0].notes
        for note in notes:
            if note not in existing:
                existing.append(note)


def _resolution_source_ref(
    snapshot: RawSnapshot,
    resolution: EntityResolution,
    destination_id: str,
) -> list[DestinationSourceRef]:
    notes = [f"resolution:{resolution.resolution_id}", *resolution.notes]
    unresolved = unresolved_conflicts(resolution.conflicts)
    notes.extend(f"{conflict.attribute_path}:{conflict.reason}" for conflict in unresolved)
    return [
        DestinationSourceRef(
            provenance_id=f"{snapshot.snapshot_id}:{resolution.resolution_id}",
            role="identity",
            source_id=snapshot.source_id,
            source_category=snapshot.source_category,
            contribution_kind="comparison",
            summary=resolution.summary,
            notes=list(dict.fromkeys(notes)),
        )
    ]


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


def _resolution_for_record(
    record_id: str,
    resolutions: list[EntityResolution],
) -> EntityResolution | None:
    for resolution in resolutions:
        for candidate in resolution.match_candidates:
            if record_id in candidate.source_record_ids:
                return resolution
    return None


def _canonical_destination_id(record: RawSourceRecord, resolution: EntityResolution | None) -> str:
    if resolution is not None:
        return resolution.canonical_entity_id
    payload_destination_id = record.payload.get("destination_id")
    if isinstance(payload_destination_id, str) and payload_destination_id:
        return payload_destination_id
    return record.provider_entity_id


def _lowest_match_confidence(resolution: EntityResolution) -> float:
    if not resolution.match_candidates:
        return 0.0
    return min(candidate.confidence for candidate in resolution.match_candidates)


def _dedupe_conflicts(conflicts: list[AttributeConflict]) -> list[AttributeConflict]:
    deduped: list[AttributeConflict] = []
    seen: set[tuple[str, str, str]] = set()
    for conflict in conflicts:
        key = (conflict.conflict_id, conflict.attribute_path, conflict.status)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(conflict)
    return deduped


def _merge_sequence(existing: Any, incoming: Any) -> list[Any]:
    merged: list[Any] = []
    for value in (existing or []):
        if value not in merged:
            merged.append(value)
    for value in (incoming or []):
        if value not in merged:
            merged.append(value)
    return merged


def _merge_scalar_list(existing: Any, incoming: Any) -> list[str]:
    merged: list[str] = []
    for value in (existing or []):
        if isinstance(value, str) and value not in merged:
            merged.append(value)
    for value in (incoming or []):
        if isinstance(value, str) and value not in merged:
            merged.append(value)
    return merged


def _merge_mapping(existing: Any, incoming: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if isinstance(existing, dict):
        result.update(existing)
    if isinstance(incoming, dict):
        for key, value in incoming.items():
            if key == "notes":
                result[key] = _merge_scalar_list(result.get(key, []), value)
                continue
            if key not in result or result[key] in ("", None, [], {}):
                result[key] = value
    return result


def _destination_role(source_category: str) -> str:
    if source_category == "official_operational":
        return "operational"
    if source_category in {"editorial", "specialist_non_commercial"}:
        return "experience"
    return "identity"


def _contribution_kind(source_category: str) -> str:
    if source_category == "official_operational":
        return "operational"
    if source_category in {"editorial", "specialist_non_commercial"}:
        return "editorial"
    return "inventory"
