from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from trip_planner.sources.adapters import AmtrakGtfsAdapter
from trip_planner.sources.snapshots import SourceQuery

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "gtfs"


def _fixture_zip(tmp_path: Path, *, overrides: dict[str, str | None] | None = None) -> Path:
    overrides = overrides or {}
    archive_path = tmp_path / "amtrak-nec-minimal.zip"
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        for fixture_path in sorted(FIXTURE_ROOT.iterdir()):
            if fixture_path.name in overrides:
                content = overrides[fixture_path.name]
                if content is not None:
                    archive.writestr(fixture_path.name, content)
            else:
                archive.write(fixture_path, fixture_path.name)
    return archive_path


def _query() -> SourceQuery:
    return SourceQuery(
        query_id="amtrak-nec-2026-09-23",
        entity_scope="transport",
        option_kind="rail",
        market="US",
        locale="en-US",
        origin="New York",
        destination="Washington",
        requested_at="2026-09-23T21:00:00Z",
    )


def test_parses_fixture_trips(tmp_path: Path) -> None:
    adapter = AmtrakGtfsAdapter(_fixture_zip(tmp_path))

    snapshot = adapter.fetch_snapshot(_query())
    handoff = adapter.build_handoff(snapshot)

    assert snapshot.adapter_id == "amtrak-gtfs-static"
    assert snapshot.source_category == "official_operational"
    assert snapshot.payload_metadata["trip_count"] == "1"
    assert snapshot.records[0].provider_entity_id == "NEC-171"
    assert snapshot.records[0].payload["route"]["route_long_name"] == "Northeast Regional"
    assert snapshot.records[0].payload["stops"] == [
        {
            "stop_sequence": 1,
            "stop_id": "NYP",
            "stop_name": "New York Penn Station",
            "arrival_time": "07:00:00",
            "departure_time": "07:00:00",
        },
        {
            "stop_sequence": 2,
            "stop_id": "PHL",
            "stop_name": "Philadelphia 30th Street Station",
            "arrival_time": "08:20:00",
            "departure_time": "08:22:00",
        },
        {
            "stop_sequence": 3,
            "stop_id": "WAS",
            "stop_name": "Washington Union Station",
            "arrival_time": "10:25:00",
            "departure_time": "10:25:00",
        },
    ]
    assert handoff.target_contract == "trip_planner/options/transport.py"
    assert handoff.input_record_ids == ["amtrak-nec-2026-09-23-trip-NEC-171"]
    assert handoff.provenance_refs[0].contribution_kind == "operational"


def test_corrupt_stop_times_rejected(tmp_path: Path) -> None:
    feed_path = _fixture_zip(
        tmp_path,
        overrides={
            "stop_times.txt": (
                "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
                "NEC-171,07:00:00,07:00:00,UNKNOWN,1\n"
            )
        },
    )

    with pytest.raises(ValueError, match="unknown stop_id 'UNKNOWN'"):
        AmtrakGtfsAdapter(feed_path).fetch_snapshot(_query())


def test_orders_stops_by_sequence(tmp_path: Path) -> None:
    feed_path = _fixture_zip(
        tmp_path,
        overrides={
            "stop_times.txt": (
                "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
                "NEC-171,10:25:00,10:25:00,WAS,3\n"
                "NEC-171,07:00:00,07:00:00,NYP,1\n"
                "NEC-171,08:20:00,08:22:00,PHL,2\n"
            )
        },
    )

    stops = AmtrakGtfsAdapter(feed_path).fetch_snapshot(_query()).records[0].payload["stops"]

    assert [stop["stop_id"] for stop in stops] == ["NYP", "PHL", "WAS"]


@pytest.mark.parametrize(
    ("table_name", "content", "message"),
    [
        ("stops.txt", None, "missing required table 'stops.txt'"),
        (
            "stops.txt",
            "stop_id,stop_lat,stop_lon\nNYP,40.7506,-73.9935\n",
            r"missing required columns: \['stop_name'\]",
        ),
        (
            "stops.txt",
            "stop_id,stop_name,stop_lat,stop_lon\nNYP,,40.7506,-73.9935\n",
            r"empty required values: \['stop_name'\]",
        ),
        (
            "stops.txt",
            "stop_id,stop_name\nNYP,First\nNYP,Duplicate\n",
            "duplicate stop_id 'NYP'",
        ),
        (
            "routes.txt",
            (
                "route_id,route_short_name,route_long_name,route_type\n"
                "NEC,NEC,Northeast Regional,2\nNEC,NEC,Duplicate,2\n"
            ),
            "duplicate route_id 'NEC'",
        ),
        (
            "trips.txt",
            (
                "route_id,service_id,trip_id,trip_headsign\n"
                "NEC,WEEKDAY,NEC-171,Washington\nNEC,WEEKDAY,NEC-171,Duplicate\n"
            ),
            "duplicate trip_id 'NEC-171'",
        ),
        (
            "stop_times.txt",
            (
                "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
                "UNKNOWN,07:00:00,07:00:00,NYP,1\n"
            ),
            "unknown trip_id 'UNKNOWN'",
        ),
        (
            "trips.txt",
            ("route_id,service_id,trip_id,trip_headsign\n" "UNKNOWN,WEEKDAY,NEC-171,Washington\n"),
            "unknown route_id 'UNKNOWN'",
        ),
        (
            "stop_times.txt",
            (
                "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
                "NEC-171,07:00:00,07:00:00,NYP,abc\n"
            ),
            "non-integer stop_sequence 'abc'",
        ),
        (
            "stop_times.txt",
            (
                "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
                "NEC-171,07:00:00,07:00:00,NYP,-1\n"
            ),
            "stop_sequence must be non-negative",
        ),
        (
            "stop_times.txt",
            (
                "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
                "NEC-171,07:00:00,07:00:00,NYP,1\n"
                "NEC-171,08:20:00,08:22:00,PHL,1\n"
            ),
            "duplicate stop_sequence values",
        ),
        (
            "stop_times.txt",
            (
                "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
                "OTHER,07:00:00,07:00:00,NYP,1\n"
            ),
            "unknown trip_id 'OTHER'",
        ),
        (
            "stop_times.txt",
            (
                "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
                "NEC-171,07:00:00,07:00:00,NYP,1,EXTRA\n"
            ),
            "more values than header columns",
        ),
    ],
)
def test_rejects_invalid_feed_tables(
    table_name: str, content: str | None, message: str, tmp_path: Path
) -> None:
    feed_path = _fixture_zip(tmp_path, overrides={table_name: content})

    with pytest.raises(ValueError, match=message):
        AmtrakGtfsAdapter(feed_path).fetch_snapshot(_query())


def test_rejects_trip_without_stop_times(tmp_path: Path) -> None:
    feed_path = _fixture_zip(
        tmp_path,
        overrides={
            "trips.txt": (
                "route_id,service_id,trip_id,trip_headsign\n"
                "NEC,WEEKDAY,NEC-171,Washington\n"
                "NEC,WEEKDAY,NEC-172,New York\n"
            )
        },
    )

    with pytest.raises(ValueError, match="trip 'NEC-172' has no stop_times.txt rows"):
        AmtrakGtfsAdapter(feed_path).fetch_snapshot(_query())


def test_rejects_non_zip_feed(tmp_path: Path) -> None:
    feed_path = tmp_path / "not-a-feed.zip"
    feed_path.write_text("not a zip", encoding="utf-8")

    with pytest.raises(ValueError, match="not a readable ZIP archive"):
        AmtrakGtfsAdapter(feed_path).fetch_snapshot(_query())


@pytest.mark.parametrize(
    ("query", "message"),
    [
        (replace(_query(), entity_scope="destination"), "entity_scope must be transport"),
        (replace(_query(), option_kind="flight"), "option_kind must be rail"),
        (replace(_query(), requested_at=""), "requested_at is required"),
    ],
)
def test_rejects_unsupported_query(query: SourceQuery, message: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=message):
        AmtrakGtfsAdapter(_fixture_zip(tmp_path)).fetch_snapshot(query)
