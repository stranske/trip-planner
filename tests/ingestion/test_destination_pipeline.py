import json
from pathlib import Path
from typing import Any

from trip_planner.ingestion import ingest_destination_snapshot
from trip_planner.sources import (
    AdapterIssue,
    AttributeConflict,
    DeduplicationDecision,
    EntityResolution,
    MatchCandidate,
    RawSnapshot,
    RawSourceRecord,
    SourceQuery,
)


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures/ingestion/destinations"


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def _build_snapshot(payload: dict[str, Any]) -> RawSnapshot:
    return RawSnapshot(
        snapshot_id=payload["snapshot_id"],
        adapter_id=payload["adapter_id"],
        source_id=payload["source_id"],
        source_category=payload["source_category"],
        entity_scope=payload["entity_scope"],
        option_kind=payload["option_kind"],
        fetched_at=payload["fetched_at"],
        query=SourceQuery(**payload["query"]),
        records=[RawSourceRecord(**item) for item in payload["records"]],
        issues=[AdapterIssue(**item) for item in payload.get("issues", [])],
    )


def _build_resolution(payload: dict[str, Any]) -> EntityResolution:
    return EntityResolution(
        resolution_id=payload["resolution_id"],
        entity_scope=payload["entity_scope"],
        option_kind=payload["option_kind"],
        status=payload["status"],
        canonical_entity_id=payload["canonical_entity_id"],
        summary=payload["summary"],
        match_candidates=[MatchCandidate(**item) for item in payload.get("match_candidates", [])],
        conflicts=[AttributeConflict(**item) for item in payload.get("conflicts", [])],
        review_required=payload.get("review_required", False),
        notes=payload.get("notes", []),
    )


def _build_decision(payload: dict[str, Any]) -> DeduplicationDecision:
    return DeduplicationDecision(
        decision_id=payload["decision_id"],
        entity_scope=payload["entity_scope"],
        option_kind=payload["option_kind"],
        decision=payload["decision"],
        canonical_entity_id=payload["canonical_entity_id"],
        summary=payload["summary"],
        duplicate_entity_ids=payload.get("duplicate_entity_ids", []),
        resolution_ids=payload.get("resolution_ids", []),
        preserved_conflicts=[
            AttributeConflict(**item) for item in payload.get("preserved_conflicts", [])
        ],
        confidence=payload.get("confidence", 0.0),
    )


def test_destination_pipeline_emits_a_clean_normalized_destination() -> None:
    fixture = _load_fixture("clean_destination_snapshot.json")

    result = ingest_destination_snapshot(_build_snapshot(fixture["snapshot"]))

    assert result.handoff is not None
    assert result.handoff.status == "ready"
    assert result.summary.emitted_options == 1
    assert result.destinations[0].destination_id == "dest-city-lisbon"
    assert result.destinations[0].source_refs[0].role == "experience"


def test_destination_pipeline_merges_duplicates_and_preserves_operational_gaps() -> None:
    fixture = _load_fixture("conflicted_destination_snapshot.json")
    fixture["snapshot"]["records"][1]["payload"]["ingestion_notes"] = [
        "Operational source notes shoulder-season crowding can spike around festivals."
    ]

    result = ingest_destination_snapshot(
        _build_snapshot(fixture["snapshot"]),
        resolutions=[_build_resolution(item) for item in fixture["resolutions"]],
        dedup_decisions=[_build_decision(item) for item in fixture["dedup_decisions"]],
    )

    assert result.handoff is not None
    assert result.handoff.status == "partial"
    assert result.summary.emitted_options == 1
    assert result.summary.filtered_record_ids == ["record-destination-b"]
    assert result.summary.low_confidence_option_ids == ["dest-city-kyoto"]
    assert len(result.destinations[0].source_refs) == 2
    assert result.destinations[0].operational_notes[0].summary.startswith("Bus crowding")
    assert (
        "Operational source notes shoulder-season crowding can spike around festivals."
        in result.destinations[0].source_refs[1].notes
    )
    assert result.unresolved_conflicts[0].attribute_path == "operational_notes[0].impact"
    assert {warning.code for warning in result.warnings} == {
        "partial_operational_context",
        "normalization_warning",
    }


def test_destination_pipeline_scopes_resolution_notes_to_comparison_refs() -> None:
    fixture = _load_fixture("conflicted_destination_snapshot.json")
    fixture["resolutions"][0]["notes"] = ["Manual comparison review confirmed same destination."]

    result = ingest_destination_snapshot(
        _build_snapshot(fixture["snapshot"]),
        resolutions=[_build_resolution(item) for item in fixture["resolutions"]],
    )

    assert result.handoff is not None
    assert result.summary.emitted_options == 2
    first_destination = result.destinations[0]
    raw_ref = first_destination.source_refs[0]
    comparison_ref = first_destination.source_refs[1]
    assert comparison_ref.contribution_kind == "comparison"
    assert comparison_ref.notes == [
        "resolution:resolution-destination-1",
        "Manual comparison review confirmed same destination.",
        "operational_notes[0].impact:source_disagreement",
    ]
    assert raw_ref.notes == []


def test_destination_pipeline_keeps_separate_decisions_as_individual_destinations() -> None:
    fixture = _load_fixture("conflicted_destination_snapshot.json")
    decision = _build_decision(fixture["dedup_decisions"][0])
    decision.decision = "keep_separate"

    result = ingest_destination_snapshot(
        _build_snapshot(fixture["snapshot"]),
        resolutions=[_build_resolution(item) for item in fixture["resolutions"]],
        dedup_decisions=[decision],
    )

    assert result.handoff is not None
    assert result.summary.emitted_options == 2
    assert result.summary.filtered_record_ids == []
    assert len(result.unresolved_conflicts) == 1
    assert sorted(destination.destination_id for destination in result.destinations) == [
        "dest-city-kyoto",
        "dest-city-kyoto",
    ]


def test_destination_pipeline_suppresses_records_from_suppressed_decisions() -> None:
    fixture = _load_fixture("conflicted_destination_snapshot.json")
    decision = _build_decision(fixture["dedup_decisions"][0])
    decision.decision = "suppress"

    result = ingest_destination_snapshot(
        _build_snapshot(fixture["snapshot"]),
        resolutions=[_build_resolution(item) for item in fixture["resolutions"]],
        dedup_decisions=[decision],
    )

    assert result.handoff is not None
    assert result.handoff.status == "blocked"
    assert result.summary.emitted_options == 0
    assert result.summary.filtered_record_ids == ["record-destination-a", "record-destination-b"]
    assert len(result.unresolved_conflicts) == 1
