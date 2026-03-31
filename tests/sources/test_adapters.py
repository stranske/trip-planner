import json
from pathlib import Path

from trip_planner.sources import (
    AdapterIssue,
    NormalizationHandoff,
    ProvenanceReference,
    RawSnapshot,
    RawSourceRecord,
    SourceAdapter,
    SourceQuery,
    SourceRecord,
)


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "sources" / "raw"


def _load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_ROOT / name).read_text())


class FixtureAdapter(SourceAdapter):
    def __init__(self, adapter_id: str, source_record: SourceRecord, payload_name: str) -> None:
        self.adapter_id = adapter_id
        self.source_record = source_record
        self.payload_name = payload_name
        self.supported_entity_scopes = ("lodging", "destination", "managed_travel")
        self.supported_option_kinds = ("lodging", "mixed", "policy")
        self.capabilities = ("read_fixture", "supports_normalization_handoff")

    def fetch_snapshot(self, query: SourceQuery) -> RawSnapshot:
        payload = _load_fixture(self.payload_name)
        record = RawSourceRecord(
            record_id=f"{query.query_id}-record-1",
            entity_scope=query.entity_scope,
            provider_entity_id=str(
                payload.get("hotel_id") or payload.get("listing_id") or payload.get("property_id")
            ),
            payload_type="json_document",
            payload=payload,
            captured_at="2026-03-31T22:25:00Z",
            metadata={"fixture_name": self.payload_name},
        )
        return RawSnapshot(
            snapshot_id=f"{query.query_id}-snapshot",
            adapter_id=self.adapter_id,
            source_id=self.source_record.source_id,
            source_category=self.source_record.category,
            entity_scope=query.entity_scope,
            option_kind=query.option_kind,
            fetched_at="2026-03-31T22:25:00Z",
            query=query,
            records=[record],
            payload_metadata={"fixture_name": self.payload_name},
            handoff_status="ready",
        )

    def build_handoff(self, snapshot: RawSnapshot) -> NormalizationHandoff:
        return NormalizationHandoff(
            handoff_id=f"{snapshot.snapshot_id}-handoff",
            snapshot_id=snapshot.snapshot_id,
            target_contract=f"trip_planner/contracts/{snapshot.entity_scope}.py",
            entity_scope=snapshot.entity_scope,
            status="ready",
            input_record_ids=[record.record_id for record in snapshot.records],
            provenance_refs=[
                ProvenanceReference(
                    provenance_id=f"prov-{snapshot.snapshot_id}",
                    source_id=snapshot.source_id,
                    source_category=snapshot.source_category,
                    subject_kind="option" if snapshot.entity_scope != "destination" else "destination",
                    subject_id=f"{snapshot.entity_scope}-candidate-1",
                    contribution_kind="inventory"
                    if snapshot.source_category == "commercial_inventory"
                    else "editorial"
                    if snapshot.source_category == "editorial"
                    else "policy",
                    summary="Normalization receives a stable snapshot wrapper and provenance seed.",
                    captured_at=snapshot.fetched_at,
                )
            ],
            record_count=len(snapshot.records),
        )


def test_fixture_adapter_supports_commercial_inventory_snapshot() -> None:
    adapter = FixtureAdapter(
        adapter_id="booking-fixture",
        source_record=SourceRecord(
            source_id="booking-com-hotel",
            provider_name="Booking.com",
            display_name="Booking.com Hotel Search",
            category="commercial_inventory",
            supported_option_kinds=["lodging"],
        ),
        payload_name="booking_lodging_search.json",
    )

    query = SourceQuery(
        query_id="lodging-paris-april",
        entity_scope="lodging",
        option_kind="lodging",
        market="FR",
        locale="en-FR",
        destination="Paris",
    )
    snapshot = adapter.fetch_snapshot(query)
    handoff = adapter.build_handoff(snapshot)

    assert snapshot.records[0].payload["hotel_name"] == "Rive Gauche Stay"
    assert snapshot.payload_metadata["fixture_name"] == "booking_lodging_search.json"
    assert handoff.status == "ready"
    assert handoff.provenance_refs[0].contribution_kind == "inventory"


def test_fixture_adapter_supports_editorial_ratings_snapshot() -> None:
    adapter = FixtureAdapter(
        adapter_id="tripadvisor-fixture",
        source_record=SourceRecord(
            source_id="tripadvisor-editorial",
            provider_name="Tripadvisor",
            display_name="Tripadvisor Neighborhood Summary",
            category="editorial",
            supported_option_kinds=["mixed"],
        ),
        payload_name="tripadvisor_editorial_summary.json",
    )

    snapshot = adapter.fetch_snapshot(
        SourceQuery(
            query_id="rome-neighborhoods",
            entity_scope="destination",
            option_kind="mixed",
            destination="Rome",
        )
    )

    assert snapshot.records[0].payload["rating_summary"]["overall"] == 4.6
    assert snapshot.records[0].payload["highlights"][0] == "Food-centric base"


def test_fixture_adapter_supports_managed_travel_snapshot() -> None:
    adapter = FixtureAdapter(
        adapter_id="navan-fixture",
        source_record=SourceRecord(
            source_id="navan-travel-policy",
            provider_name="Navan",
            display_name="Navan Managed Travel",
            category="managed_travel_policy",
            supported_option_kinds=["lodging", "policy"],
            business_approval_status="preferred",
        ),
        payload_name="navan_managed_hotel.json",
    )

    snapshot = adapter.fetch_snapshot(
        SourceQuery(
            query_id="managed-hotel-nyc",
            entity_scope="managed_travel",
            option_kind="policy",
            market="US",
            destination="New York",
        )
    )

    assert snapshot.source_category == "managed_travel_policy"
    assert snapshot.records[0].payload["approval_status"] == "preferred"


def test_raw_snapshot_supports_partial_failures_without_losing_records() -> None:
    query = SourceQuery(
        query_id="kyoto-lodging",
        entity_scope="lodging",
        option_kind="lodging",
        destination="Kyoto",
    )
    snapshot = RawSnapshot(
        snapshot_id="snapshot-1",
        adapter_id="fixture",
        source_id="booking-com-hotel",
        source_category="commercial_inventory",
        entity_scope="lodging",
        option_kind="lodging",
        fetched_at="2026-03-31T22:30:00Z",
        query=query,
        records=[
            RawSourceRecord(
                record_id="record-1",
                entity_scope="lodging",
                provider_entity_id="hotel-1",
                payload_type="json_document",
                payload=_load_fixture("booking_lodging_search.json"),
            )
        ],
        issues=[
            AdapterIssue(
                issue_id="issue-1",
                stage="fetch",
                severity="warning",
                code="partial_room_inventory",
                message="Some room classes were missing from the provider response.",
                affected_record_ids=["record-1"],
                details={"provider_error": "inventory_trimmed"},
            )
        ],
        snapshot_status="partial",
        handoff_status="partial",
    )

    payload = snapshot.to_dict()

    assert payload["snapshot_status"] == "partial"
    assert payload["issues"][0]["code"] == "partial_room_inventory"
    assert payload["records"][0]["provider_entity_id"] == "hotel-1"
