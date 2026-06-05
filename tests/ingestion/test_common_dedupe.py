from trip_planner.ingestion._common import _dedupe_conflicts
from trip_planner.sources import AttributeConflict


def test_dedupe_conflicts_preserves_distinct_attribute_rows() -> None:
    conflicts = [
        AttributeConflict(
            conflict_id="conflict-shared",
            attribute_path="booking_terms.refundable",
            reason="source_disagreement",
            status="needs_review",
            values_by_source={"source-a": "yes", "source-b": "no"},
        ),
        AttributeConflict(
            conflict_id="conflict-shared",
            attribute_path="booking_terms.deposit",
            reason="source_disagreement",
            status="needs_review",
            values_by_source={"source-a": "none", "source-b": "required"},
        ),
        AttributeConflict(
            conflict_id="conflict-shared",
            attribute_path="booking_terms.deposit",
            reason="source_disagreement",
            status="needs_review",
            values_by_source={"source-a": "none", "source-b": "required"},
        ),
    ]

    deduped = _dedupe_conflicts(conflicts)

    assert [
        (conflict.conflict_id, conflict.attribute_path, conflict.status)
        for conflict in deduped
    ] == [
        ("conflict-shared", "booking_terms.refundable", "needs_review"),
        ("conflict-shared", "booking_terms.deposit", "needs_review"),
    ]
