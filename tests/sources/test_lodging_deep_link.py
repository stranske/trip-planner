from dataclasses import replace

import pytest

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


@pytest.mark.parametrize(
    "deep_link", ["not-a-url", "/hotel/123", "https:///hotel", "ftp://example.com/hotel"]
)
def test_fetch_snapshot_rejects_invalid_urls(deep_link: str) -> None:
    query = replace(_sample_query(), filters={"deep_link": deep_link})
    with pytest.raises(ValueError, match="absolute http or https URL"):
        LodgingDeepLinkAdapter().fetch_snapshot(query)


@pytest.mark.parametrize("field", ["entity_scope", "option_kind"])
def test_fetch_snapshot_rejects_unsupported_scope(field: str) -> None:
    query = replace(
        _sample_query(),
        **{field: "transport" if field == "entity_scope" else "flight"},
        filters={"deep_link": "https://example.com/hotel"},
    )
    with pytest.raises(ValueError, match=rf"query\.{field} must be lodging"):
        LodgingDeepLinkAdapter().fetch_snapshot(query)


def test_fetch_snapshot_requires_deep_link_filter() -> None:
    with pytest.raises(ValueError, match="must include 'deep_link'"):
        LodgingDeepLinkAdapter().fetch_snapshot(_sample_query())


def test_capture_requires_timestamp() -> None:
    query = replace(_sample_query(), requested_at="")
    with pytest.raises(ValueError, match="capture or query must provide a timestamp"):
        LodgingDeepLinkAdapter().capture(LodgingDeepLinkCapture("https://example.com/hotel"), query)


@pytest.mark.parametrize("query_time", ["", "2026-06-04T18:30:00Z"])
def test_capture_timestamp_preserved_in_provenance(query_time: str) -> None:
    adapter = LodgingDeepLinkAdapter()
    timestamp = "2026-06-05T09:15:00Z"
    snapshot = adapter.capture(
        LodgingDeepLinkCapture("https://example.com/hotel", captured_at=timestamp),
        replace(_sample_query(), requested_at=query_time),
    )
    assert snapshot.fetched_at == timestamp
    assert snapshot.records[0].captured_at == timestamp
    assert adapter.build_handoff(snapshot).provenance_refs[0].captured_at == timestamp
