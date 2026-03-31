from trip_planner.sources import (
    AdapterIssue,
    NormalizationHandoff,
    ProvenanceReference,
    RawSnapshot,
    RawSourceRecord,
    SourceQuery,
)


def test_normalization_handoff_preserves_provenance_boundary() -> None:
    snapshot = RawSnapshot(
        snapshot_id="snapshot-destination-1",
        adapter_id="editorial-fixture",
        source_id="city-guide",
        source_category="editorial",
        entity_scope="destination",
        option_kind="mixed",
        fetched_at="2026-03-31T22:35:00Z",
        query=SourceQuery(
            query_id="destination-rome",
            entity_scope="destination",
            option_kind="mixed",
            destination="Rome",
        ),
        records=[
            RawSourceRecord(
                record_id="record-destination-1",
                entity_scope="destination",
                provider_entity_id="rome-trastevere",
                payload_type="json_document",
                payload={"headline": "Trastevere"},
            )
        ],
    )

    handoff = NormalizationHandoff(
        handoff_id="handoff-1",
        snapshot_id=snapshot.snapshot_id,
        target_contract="trip_planner/contracts/destinations.py",
        entity_scope="destination",
        status="ready",
        input_record_ids=["record-destination-1"],
        provenance_refs=[
            ProvenanceReference(
                provenance_id="prov-destination-1",
                source_id="city-guide",
                source_category="editorial",
                subject_kind="destination",
                subject_id="rome-trastevere",
                contribution_kind="editorial",
                summary="Editorial source identified the neighborhood as a candidate shell.",
                captured_at="2026-03-31T22:35:00Z",
            )
        ],
        record_count=1,
    )

    payload = handoff.to_dict()

    assert payload["target_contract"] == "trip_planner/contracts/destinations.py"
    assert payload["provenance_refs"][0]["subject_kind"] == "destination"


def test_failed_snapshot_cannot_keep_records() -> None:
    try:
        RawSnapshot(
            snapshot_id="snapshot-failed",
            adapter_id="fixture",
            source_id="amtrak",
            source_category="official_operational",
            entity_scope="transport",
            option_kind="rail",
            fetched_at="2026-03-31T22:40:00Z",
            query=SourceQuery(
                query_id="rail-failure",
                entity_scope="transport",
                option_kind="rail",
                origin="Chicago",
                destination="St. Louis",
            ),
            records=[
                RawSourceRecord(
                    record_id="record-1",
                    entity_scope="transport",
                    provider_entity_id="amtrak-301",
                    payload_type="json_document",
                    payload={"status": "late"},
                )
            ],
            snapshot_status="failed",
        )
    except ValueError as exc:
        assert "failed snapshots" in str(exc)
    else:
        raise AssertionError("RawSnapshot should reject records on failed snapshots")


def test_adapter_issue_rejects_invalid_stage() -> None:
    try:
        AdapterIssue(
            issue_id="issue-bad",
            stage="parse_everything",
            severity="warning",
            code="bad_stage",
            message="Invalid stage",
        )
    except ValueError as exc:
        assert "stage" in str(exc)
    else:
        raise AssertionError("AdapterIssue should reject unsupported stages")
