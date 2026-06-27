from trip_planner.ingestion._common import (
    IngestionSummary,
    IngestionWarning,
    _record_ids_for_decision,
    _records_for_decision,
    make_handoff,
    unresolved_conflicts,
    warning_from_issue,
)
from trip_planner.sources import (
    AdapterIssue,
    AttributeConflict,
    DeduplicationDecision,
    EntityResolution,
    MatchCandidate,
    ProvenanceReference,
    RawSnapshot,
    RawSourceRecord,
    SourceQuery,
)


def _sample_conflict(*, status: str, conflict_id: str = "conflict-1") -> AttributeConflict:
    kwargs: dict[str, object] = {
        "conflict_id": conflict_id,
        "attribute_path": "booking_terms.refundable",
        "reason": "source_disagreement",
        "status": status,
        "values_by_source": {"source-a": "yes", "source-b": "no"},
    }
    if status == "selected":
        kwargs["selected_value"] = "yes"
    return AttributeConflict(**kwargs)


def _sample_record(record_id: str) -> RawSourceRecord:
    return RawSourceRecord(
        record_id=record_id,
        entity_scope="lodging",
        provider_entity_id=f"provider-{record_id}",
        payload_type="json_document",
        payload={},
    )


def _sample_snapshot() -> RawSnapshot:
    return RawSnapshot(
        snapshot_id="snapshot-lodging-1",
        adapter_id="lodging-fixture",
        source_id="booking-fixture",
        source_category="editorial",
        entity_scope="lodging",
        option_kind="lodging",
        fetched_at="2026-03-31T22:35:00Z",
        query=SourceQuery(
            query_id="lodging-amsterdam",
            entity_scope="lodging",
            option_kind="lodging",
            destination="Amsterdam",
        ),
    )


def test_ingestion_warning_to_dict_serializes_all_fields() -> None:
    warning = IngestionWarning(
        warning_id="warn-1",
        severity="warning",
        code="MISSING_FIELD",
        message="required field missing",
        record_ids=["rec-1", "rec-2"],
        notes=["check payload"],
    )

    assert warning.to_dict() == {
        "warning_id": "warn-1",
        "severity": "warning",
        "code": "MISSING_FIELD",
        "message": "required field missing",
        "record_ids": ["rec-1", "rec-2"],
        "notes": ["check payload"],
    }


def test_ingestion_summary_to_dict_serializes_defaults_and_counters() -> None:
    summary = IngestionSummary(
        total_records=4,
        emitted_options=2,
        skipped_records=1,
        degraded_options=1,
        unresolved_conflicts=1,
        low_confidence_option_ids=["opt-low"],
        filtered_record_ids=["rec-filtered"],
        notes=["partial handoff"],
    )

    assert summary.to_dict() == {
        "total_records": 4,
        "emitted_options": 2,
        "skipped_records": 1,
        "degraded_options": 1,
        "unresolved_conflicts": 1,
        "low_confidence_option_ids": ["opt-low"],
        "filtered_record_ids": ["rec-filtered"],
        "notes": ["partial handoff"],
    }


def test_warning_from_issue_maps_adapter_issue_fields() -> None:
    issue = AdapterIssue(
        issue_id="issue-1",
        stage="validation",
        severity="warning",
        code="INVALID_PAYLOAD",
        message="payload failed validation",
        affected_record_ids=["rec-1", "rec-2"],
    )

    warning = warning_from_issue(issue)

    assert isinstance(warning, IngestionWarning)
    assert warning.warning_id == issue.issue_id
    assert warning.severity == issue.severity
    assert warning.code == issue.code
    assert warning.message == issue.message
    assert warning.record_ids == issue.affected_record_ids
    assert warning.notes == []


def test_unresolved_conflicts_excludes_selected_status() -> None:
    selected = _sample_conflict(status="selected", conflict_id="conflict-selected")
    needs_review = _sample_conflict(status="needs_review", conflict_id="conflict-review")
    preserved = _sample_conflict(status="preserved", conflict_id="conflict-preserved")

    unresolved = unresolved_conflicts([selected, needs_review, preserved])

    assert unresolved == [needs_review, preserved]


def test_record_ids_for_decision_collects_unique_ids_in_resolution_order() -> None:
    resolution_a = EntityResolution(
        resolution_id="resolution-a",
        entity_scope="lodging",
        option_kind="lodging",
        status="match",
        canonical_entity_id="entity-1",
        summary="matched duplicate lodging records",
        match_candidates=[
            MatchCandidate(
                candidate_id="candidate-a",
                entity_scope="lodging",
                option_kind="lodging",
                match_strategy="provider_id",
                confidence=0.95,
                source_record_ids=["rec-1", "rec-2"],
            )
        ],
    )
    resolution_b = EntityResolution(
        resolution_id="resolution-b",
        entity_scope="lodging",
        option_kind="lodging",
        status="match",
        canonical_entity_id="entity-1",
        summary="matched overlapping lodging records",
        match_candidates=[
            MatchCandidate(
                candidate_id="candidate-b",
                entity_scope="lodging",
                option_kind="lodging",
                match_strategy="provider_id",
                confidence=0.9,
                source_record_ids=["rec-2", "rec-3"],
            )
        ],
    )
    decision = DeduplicationDecision(
        decision_id="decision-1",
        entity_scope="lodging",
        option_kind="lodging",
        decision="merge",
        canonical_entity_id="entity-1",
        summary="merge duplicate lodging records",
        duplicate_entity_ids=["entity-2"],
        resolution_ids=["resolution-a", "resolution-b"],
    )

    record_ids = _record_ids_for_decision(
        decision,
        {
            "resolution-a": resolution_a,
            "resolution-b": resolution_b,
        },
    )

    assert record_ids == ["rec-1", "rec-2", "rec-3"]


def test_record_ids_for_decision_skips_missing_resolution_entries() -> None:
    resolution = EntityResolution(
        resolution_id="resolution-a",
        entity_scope="lodging",
        option_kind="lodging",
        status="match",
        canonical_entity_id="entity-1",
        summary="matched lodging record",
        match_candidates=[
            MatchCandidate(
                candidate_id="candidate-a",
                entity_scope="lodging",
                option_kind="lodging",
                match_strategy="provider_id",
                confidence=0.95,
                source_record_ids=["rec-1"],
            )
        ],
    )
    decision = DeduplicationDecision(
        decision_id="decision-1",
        entity_scope="lodging",
        option_kind="lodging",
        decision="merge",
        canonical_entity_id="entity-1",
        summary="merge duplicate lodging records",
        duplicate_entity_ids=["entity-2"],
        resolution_ids=["resolution-a", "resolution-missing"],
    )

    record_ids = _record_ids_for_decision(decision, {"resolution-a": resolution})

    assert record_ids == ["rec-1"]


def test_records_for_decision_returns_matching_records_in_id_order() -> None:
    records = [_sample_record("rec-1"), _sample_record("rec-2"), _sample_record("rec-3")]
    resolution = EntityResolution(
        resolution_id="resolution-a",
        entity_scope="lodging",
        option_kind="lodging",
        status="match",
        canonical_entity_id="entity-1",
        summary="matched lodging records",
        match_candidates=[
            MatchCandidate(
                candidate_id="candidate-a",
                entity_scope="lodging",
                option_kind="lodging",
                match_strategy="provider_id",
                confidence=0.95,
                source_record_ids=["rec-3", "rec-1"],
            )
        ],
    )
    decision = DeduplicationDecision(
        decision_id="decision-1",
        entity_scope="lodging",
        option_kind="lodging",
        decision="merge",
        canonical_entity_id="entity-1",
        summary="merge duplicate lodging records",
        duplicate_entity_ids=["entity-2"],
        resolution_ids=["resolution-a"],
    )

    selected = _records_for_decision(
        records,
        decision,
        {"resolution-a": resolution},
    )

    assert [record.record_id for record in selected] == ["rec-3", "rec-1"]


def test_records_for_decision_omits_unknown_record_ids() -> None:
    records = [_sample_record("rec-1")]
    resolution = EntityResolution(
        resolution_id="resolution-a",
        entity_scope="lodging",
        option_kind="lodging",
        status="match",
        canonical_entity_id="entity-1",
        summary="matched lodging records",
        match_candidates=[
            MatchCandidate(
                candidate_id="candidate-a",
                entity_scope="lodging",
                option_kind="lodging",
                match_strategy="provider_id",
                confidence=0.95,
                source_record_ids=["rec-1", "rec-missing"],
            )
        ],
    )
    decision = DeduplicationDecision(
        decision_id="decision-1",
        entity_scope="lodging",
        option_kind="lodging",
        decision="merge",
        canonical_entity_id="entity-1",
        summary="merge duplicate lodging records",
        duplicate_entity_ids=["entity-2"],
        resolution_ids=["resolution-a"],
    )

    selected = _records_for_decision(
        records,
        decision,
        {"resolution-a": resolution},
    )

    assert [record.record_id for record in selected] == ["rec-1"]


def test_records_for_decision_returns_empty_list_when_no_resolution_ids() -> None:
    decision = DeduplicationDecision(
        decision_id="decision-1",
        entity_scope="lodging",
        option_kind="lodging",
        decision="merge",
        canonical_entity_id="entity-1",
        summary="merge duplicate lodging records",
        duplicate_entity_ids=["entity-2"],
        resolution_ids=[],
    )

    selected = _records_for_decision([_sample_record("rec-1")], decision, {})

    assert selected == []


def test_make_handoff_builds_normalization_handoff_from_snapshot() -> None:
    snapshot = _sample_snapshot()
    provenance_ref = ProvenanceReference(
        provenance_id="prov-1",
        source_id=snapshot.source_id,
        source_category=snapshot.source_category,
        subject_kind="option",
        subject_id="lodging-option-1",
        contribution_kind="editorial",
        summary="fixture provenance",
    )

    handoff = make_handoff(
        snapshot,
        target_contract="TripPlanner/Lodging",
        status="ready",
        input_record_ids=["rec-1", "rec-2"],
        blocked_issue_ids=["issue-blocked"],
        provenance_refs=[provenance_ref],
        notes=["ready for normalization"],
    )

    assert handoff.handoff_id == "snapshot-lodging-1:tripplanner/lodging"
    assert handoff.snapshot_id == snapshot.snapshot_id
    assert handoff.target_contract == "TripPlanner/Lodging"
    assert handoff.entity_scope == snapshot.entity_scope
    assert handoff.status == "ready"
    assert handoff.input_record_ids == ["rec-1", "rec-2"]
    assert handoff.blocked_issue_ids == ["issue-blocked"]
    assert handoff.provenance_refs == [provenance_ref]
    assert handoff.record_count == 2
    assert handoff.notes == ["ready for normalization"]
