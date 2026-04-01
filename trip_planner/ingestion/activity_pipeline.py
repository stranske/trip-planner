"""Activity ingestion scaffolding from raw snapshots to normalized activities."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from trip_planner._validators import require_non_empty, require_strings
from trip_planner.options.activities import ActivityOption
from trip_planner.sources import (
    AttributeConflict,
    DeduplicationDecision,
    EntityResolution,
    NormalizationHandoff,
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
class ActivityIngestionResult:
    pipeline_id: str
    snapshot_id: str
    activity_options: list[ActivityOption] = field(default_factory=list)
    unresolved_conflicts: list[AttributeConflict] = field(default_factory=list)
    warnings: list[IngestionWarning] = field(default_factory=list)
    handoff: NormalizationHandoff | None = None
    summary: IngestionSummary = field(default_factory=lambda: IngestionSummary(0, 0))
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.pipeline_id, "pipeline_id")
        require_non_empty(self.snapshot_id, "snapshot_id")
        if any(not isinstance(item, ActivityOption) for item in self.activity_options):
            raise ValueError("activity_options must contain ActivityOption instances")
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


def ingest_activity_snapshot(
    snapshot: RawSnapshot,
    *,
    resolutions: list[EntityResolution] | None = None,
    dedup_decisions: list[DeduplicationDecision] | None = None,
) -> ActivityIngestionResult:
    if snapshot.entity_scope != "activity":
        raise ValueError("snapshot.entity_scope must be activity")
    if snapshot.option_kind != "activity":
        raise ValueError("snapshot.option_kind must be activity")

    resolutions = resolutions or []
    dedup_decisions = dedup_decisions or []
    warnings = [warning_from_issue(issue) for issue in snapshot.issues]
    resolution_map = {resolution.resolution_id: resolution for resolution in resolutions}
    emitted_ids: set[str] = set()
    filtered_record_ids: list[str] = []
    low_confidence_option_ids: list[str] = []
    activity_options: list[ActivityOption] = []
    preserved_conflicts: list[AttributeConflict] = []
    provenance_refs = []

    for decision in dedup_decisions:
        if decision.entity_scope != "activity" or decision.option_kind != snapshot.option_kind:
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
                    message="Dedup decision did not map to any raw activity records.",
                )
            )
            continue
        option = _activity_option_from_records(records, snapshot, decision.canonical_entity_id)
        option.notes.extend([f"dedup_decision:{decision.decision_id}", *decision.notes])
        option.feasibility.constraints.extend(
            [
                f"{conflict.attribute_path}:{conflict.reason}"
                for conflict in unresolved_conflicts(decision.preserved_conflicts)
            ]
        )
        if decision.confidence < 0.75:
            low_confidence_option_ids.append(option.option_id)
        for record in records:
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
        activity_options.append(option)
        emitted_ids.update(record.record_id for record in records)
        filtered_record_ids.extend(record.record_id for record in records[1:])
        provenance_refs.extend(option.source_refs)

    for record in snapshot.records:
        if record.record_id in emitted_ids:
            continue
        resolution = _resolution_for_record(record.record_id, resolutions)
        option = _activity_option_from_records([record], snapshot, _canonical_option_id(record, resolution))
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
        activity_options.append(option)
        provenance_refs.extend(option.source_refs)

    preserved_conflicts = _dedupe_conflicts(preserved_conflicts)
    handoff_status = "ready"
    if warnings or preserved_conflicts:
        handoff_status = "partial"
    if not activity_options:
        handoff_status = "blocked"

    summary = IngestionSummary(
        total_records=len(snapshot.records),
        emitted_options=len(activity_options),
        skipped_records=max(0, len(snapshot.records) - len(activity_options)),
        degraded_options=sum(1 for option in activity_options if option.notes),
        unresolved_conflicts=len(preserved_conflicts),
        low_confidence_option_ids=sorted(set(low_confidence_option_ids)),
        filtered_record_ids=filtered_record_ids,
    )
    handoff = make_handoff(
        snapshot,
        target_contract="ActivityOption",
        status=handoff_status,
        input_record_ids=[record.record_id for record in snapshot.records],
        blocked_issue_ids=[warning.warning_id for warning in warnings if warning.severity == "error"],
        provenance_refs=provenance_refs,
        notes=["Activity ingestion scaffolding emitted normalized activity options from raw snapshots."],
    )
    return ActivityIngestionResult(
        pipeline_id=f"activity-ingestion:{snapshot.snapshot_id}",
        snapshot_id=snapshot.snapshot_id,
        activity_options=activity_options,
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


def _activity_option_from_records(
    records: list[RawSourceRecord],
    snapshot: RawSnapshot,
    option_id: str,
) -> ActivityOption:
    primary = records[0]
    payload = dict(primary.payload)
    payload["option_id"] = option_id
    payload["source_refs"] = [
        build_provenance_reference(
            snapshot,
            record,
            subject_id=option_id,
            contribution_kind=_contribution_kind(snapshot.source_category),
            summary=f"Normalized activity option sourced from {record.provider_entity_id}.",
        ).to_dict()
        for record in records
    ]
    payload["booking_links"] = _merge_string_lists(
        payload.get("booking_links", []),
        *[record.payload.get("booking_links", []) for record in records[1:]],
    )
    payload["tags"] = _merge_string_lists(
        payload.get("tags", []),
        *[record.payload.get("tags", []) for record in records[1:]],
    )
    payload["notes"] = _merge_string_lists(
        payload.get("notes", []),
        *[record.payload.get("ingestion_notes", []) for record in records],
    )
    for record in records[1:]:
        candidate = record.payload
        if not payload.get("summary") and candidate.get("summary"):
            payload["summary"] = candidate["summary"]
        if not payload.get("place_id") and candidate.get("place_id"):
            payload["place_id"] = candidate["place_id"]
        if not payload.get("destination_id") and candidate.get("destination_id"):
            payload["destination_id"] = candidate["destination_id"]
        payload["booking_terms"] = _merge_mapping(
            payload.get("booking_terms"),
            candidate.get("booking_terms"),
        )
        payload["feasibility"] = _merge_mapping(
            payload.get("feasibility"),
            candidate.get("feasibility"),
        )
    return ActivityOption.from_dict(payload)


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
    payload_option_id = record.payload.get("option_id")
    if isinstance(payload_option_id, str) and payload_option_id:
        return payload_option_id
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


def _merge_string_lists(*lists: Any) -> list[str]:
    merged: list[str] = []
    for values in lists:
        for value in values or []:
            if isinstance(value, str) and value not in merged:
                merged.append(value)
    return merged


def _merge_mapping(existing: Any, incoming: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if isinstance(existing, dict):
        result.update(existing)
    if isinstance(incoming, dict):
        for key, value in incoming.items():
            if key in {"constraints", "accessibility_notes", "notes", "approved_channels"}:
                result[key] = _merge_string_lists(result.get(key, []), value)
                continue
            if key not in result or result[key] in ("", None, [], {}):
                result[key] = value
    return result


def _contribution_kind(source_category: str) -> str:
    if source_category == "official_operational":
        return "operational"
    if source_category in {"editorial", "specialist_non_commercial"}:
        return "editorial"
    return "inventory"
