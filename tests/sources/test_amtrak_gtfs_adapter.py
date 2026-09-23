from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from trip_planner.sources.adapters import AmtrakGtfsAdapter
from trip_planner.sources.snapshots import SourceQuery

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "gtfs"


def _fixture_zip(tmp_path: Path, *, stop_times: str | None = None) -> Path:
    archive_path = tmp_path / "amtrak-nec-minimal.zip"
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        for fixture_path in sorted(FIXTURE_ROOT.iterdir()):
            if fixture_path.name == "stop_times.txt" and stop_times is not None:
                archive.writestr(fixture_path.name, stop_times)
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
        stop_times=(
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            "NEC-171,07:00:00,07:00:00,UNKNOWN,1\n"
        ),
    )

    with pytest.raises(ValueError, match="unknown stop_id 'UNKNOWN'"):
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
