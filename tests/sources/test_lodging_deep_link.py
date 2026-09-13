from trip_planner.sources.adapters.lodging_deep_link import (
    LodgingDeepLinkAdapter,
    LodgingDeepLinkCapture,
)
from trip_planner.sources.snapshots import SourceQuery


def _sample_query() -> SourceQuery:
    return SourceQuery(
        query_id="lodging-alfama-april",
        entity_scope="lodging",
        option_kind="lodging",
        destination="Lisbon",
        requested_at="2026-06-04T18:30:00Z",
    )


def test_provenance_seed_present() -> None:
    adapter = LodgingDeepLinkAdapter()
    deep_link = "https://booking.example/hotels/alfama-loft?checkin=2026-06-04"
    query = _sample_query()
    snapshot = adapter.capture(
        LodgingDeepLinkCapture(
            deep_link=deep_link,
            provider_label="Booking.com",
            listing_title="Alfama loft with terrace",
        ),
        query,
    )
    handoff = adapter.build_handoff(snapshot)

    assert snapshot.records[0].payload["deep_link"] == deep_link
    assert snapshot.records[0].payload_locator == deep_link
    assert handoff.status == "ready"
    assert handoff.provenance_refs
    provenance = handoff.provenance_refs[0]
    assert provenance.locator == deep_link
    assert provenance.subject_kind == "option"
    assert provenance.contribution_kind == "editorial"


def test_fetch_snapshot_reads_deep_link_filter() -> None:
    adapter = LodgingDeepLinkAdapter()
    deep_link = "https://airbnb.example/rooms/12345"

    snapshot = adapter.fetch_snapshot(
        SourceQuery(
            query_id="lodging-airbnb-capture",
            entity_scope="lodging",
            option_kind="lodging",
            destination="Porto",
            requested_at="2026-06-05T09:15:00Z",
            filters={"deep_link": deep_link, "listing_title": "Ribeira studio"},
        )
    )

    assert snapshot.records[0].payload["deep_link"] == deep_link
    assert adapter.build_handoff(snapshot).provenance_refs[0].locator == deep_link
