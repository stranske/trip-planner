import json
from pathlib import Path

import pytest

from trip_planner.sources import (
    AttributeConflict,
    DeduplicationDecision,
    MergedEntityProvenance,
    ProvenanceReference,
)


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "sources" / "resolution"


def load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_ROOT / name).read_text())


def build_provenance(canonical_entity_id: str, entity_scope: str) -> MergedEntityProvenance:
    return MergedEntityProvenance(
        canonical_entity_id=canonical_entity_id,
        entity_scope=entity_scope,
        source_record_ids=[f"{canonical_entity_id}-record-a", f"{canonical_entity_id}-record-b"],
        source_snapshot_ids=[f"{canonical_entity_id}-snapshot-a", f"{canonical_entity_id}-snapshot-b"],
        provenance_refs=[
            ProvenanceReference(
                provenance_id=f"prov-{canonical_entity_id}",
                source_id="fixture-source",
                source_category="commercial_inventory",
                subject_kind="option",
                subject_id=canonical_entity_id,
                contribution_kind="inventory",
                summary="Deduplication retains contributing raw sources.",
                captured_at="2026-04-01T00:06:00Z",
            )
        ],
    )


def test_deduplication_merge_supports_transport_and_activity_contracts() -> None:
    shared_conflict = AttributeConflict(
        conflict_id="conflict-transport-1",
        attribute_path="transport.operator_name",
        reason="source_disagreement",
        status="selected",
        values_by_source={"source:amtrak": "Amtrak", "source:rail-europe": "Amtrak USA"},
        selected_value="Amtrak",
    )

    transport_decision = DeduplicationDecision(
        decision_id="decision-transport-1",
        entity_scope="transport",
        option_kind="rail",
        decision="merge",
        canonical_entity_id="transport-chi-stl-amtrak",
        duplicate_entity_ids=["transport-amtrak-301"],
        resolution_ids=["resolution-transport-1"],
        preserved_conflicts=[shared_conflict],
        merged_provenance=build_provenance("transport-chi-stl-amtrak", "transport"),
        confidence=0.88,
        summary="The route signatures align strongly enough to merge transport options.",
    )
    activity_decision = DeduplicationDecision(
        decision_id="decision-activity-1",
        entity_scope="activity",
        option_kind="activity",
        decision="merge",
        canonical_entity_id="activity-colosseum-tour",
        duplicate_entity_ids=["activity-colosseum-priority-tour"],
        resolution_ids=["resolution-activity-1"],
        preserved_conflicts=[shared_conflict],
        merged_provenance=build_provenance("activity-colosseum-tour", "activity"),
        confidence=0.9,
        summary="Two activity listings collapse into one inspectable activity candidate.",
    )

    assert transport_decision.to_dict()["decision"] == "merge"
    assert activity_decision.to_dict()["entity_scope"] == "activity"


def test_deduplication_can_keep_destination_records_separate() -> None:
    fixture = load_fixture("activity_non_match.json")
    conflict = AttributeConflict(conflict_id="conflict-activity-1", **fixture["conflict"])
    decision = DeduplicationDecision(
        decision_id="decision-activity-2",
        entity_scope="activity",
        option_kind="activity",
        decision=str(fixture["decision"]),
        canonical_entity_id=str(fixture["canonical_entity_id"]),
        duplicate_entity_ids=list(fixture["duplicate_entity_ids"]),
        resolution_ids=list(fixture["resolution_ids"]),
        preserved_conflicts=[conflict],
        merged_provenance=build_provenance("activity-river-cruise-separate", "activity"),
        confidence=float(fixture["confidence"]),
        summary="Duration and itinerary disagreement keep the cruises separate.",
    )

    payload = decision.to_dict()

    assert payload["decision"] == "keep_separate"
    assert payload["preserved_conflicts"][0]["status"] == "needs_review"


def test_deduplication_merge_requires_duplicates() -> None:
    with pytest.raises(ValueError, match="duplicate_entity_ids"):
        DeduplicationDecision(
            decision_id="decision-lodging-invalid",
            entity_scope="lodging",
            option_kind="lodging",
            decision="merge",
            canonical_entity_id="lodging-canal-house",
            merged_provenance=build_provenance("lodging-canal-house", "lodging"),
            confidence=0.91,
            summary="Merges must name the duplicate ids they collapse.",
        )
