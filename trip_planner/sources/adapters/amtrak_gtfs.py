"""Read static Amtrak GTFS feeds into the canonical source snapshot boundary."""

from __future__ import annotations

import csv
import hashlib
from collections.abc import Iterable
from io import TextIOWrapper
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from trip_planner.sources.models import SourceRecord
from trip_planner.sources.provenance import ProvenanceReference
from trip_planner.sources.snapshots import (
    NormalizationHandoff,
    RawSnapshot,
    RawSourceRecord,
    SourceQuery,
)

from .base import SourceAdapter

_TARGET_CONTRACT = "trip_planner/options/transport.py"
_REQUIRED_COLUMNS = {
    "stops.txt": {"stop_id", "stop_name"},
    "routes.txt": {"route_id", "route_short_name", "route_long_name", "route_type"},
    "trips.txt": {"route_id", "service_id", "trip_id", "trip_headsign"},
    "stop_times.txt": {
        "trip_id",
        "arrival_time",
        "departure_time",
        "stop_id",
        "stop_sequence",
    },
}


def _read_table(archive: ZipFile, table_name: str) -> list[dict[str, str]]:
    """Read one required GTFS table and validate its header and row values."""

    try:
        member = archive.open(table_name)
    except KeyError as exc:
        raise ValueError(f"GTFS feed is missing required table {table_name!r}") from exc

    with member, TextIOWrapper(member, encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = set(reader.fieldnames or ())
        missing = _REQUIRED_COLUMNS[table_name] - columns
        if missing:
            raise ValueError(
                f"GTFS table {table_name!r} is missing required columns: {sorted(missing)!r}"
            )
        rows: list[dict[str, str]] = []
        try:
            for row in reader:
                if None in row:
                    raise ValueError(
                        f"GTFS table {table_name!r} row {reader.line_num} has more values "
                        "than header columns"
                    )
                rows.append({key: (value or "").strip() for key, value in row.items()})
        except csv.Error as exc:
            raise ValueError(f"GTFS table {table_name!r} is not valid CSV: {exc}") from exc

    if not rows:
        raise ValueError(f"GTFS table {table_name!r} must contain at least one row")
    for row_number, row in enumerate(rows, start=2):
        empty = sorted(column for column in _REQUIRED_COLUMNS[table_name] if not row[column])
        if empty:
            raise ValueError(
                f"GTFS table {table_name!r} row {row_number} has empty required values: {empty!r}"
            )
    return rows


def _unique_by(
    rows: Iterable[dict[str, str]], key: str, table_name: str
) -> dict[str, dict[str, str]]:
    indexed: dict[str, dict[str, str]] = {}
    for row in rows:
        value = row[key]
        if value in indexed:
            raise ValueError(f"GTFS table {table_name!r} contains duplicate {key} {value!r}")
        indexed[value] = row
    return indexed


class AmtrakGtfsAdapter(SourceAdapter):
    """Load a static Amtrak GTFS ZIP without making a live network request."""

    def __init__(self, feed_path: str | Path) -> None:
        self.feed_path = Path(feed_path)
        self.adapter_id = "amtrak-gtfs-static"
        self.source_record = SourceRecord(
            source_id="amtrak-static-gtfs",
            provider_name="Amtrak",
            display_name="Amtrak Static GTFS",
            category="official_operational",
            coverage_scope="regional",
            supported_option_kinds=["rail"],
            coverage_regions=["US Northeast Corridor"],
            base_url="https://www.amtrak.com/",
            notes=["Static schedule feed; it does not represent live availability or pricing."],
        )
        self.supported_entity_scopes = ("transport",)
        self.supported_option_kinds = ("rail",)
        self.capabilities = ("read_file", "supports_normalization_handoff")

    def fetch_snapshot(self, query: SourceQuery) -> RawSnapshot:
        if query.entity_scope != "transport":
            raise ValueError("query.entity_scope must be transport")
        if query.option_kind != "rail":
            raise ValueError("query.option_kind must be rail")
        if not query.requested_at:
            raise ValueError("query.requested_at is required for a static GTFS snapshot")
        if not self.feed_path.is_file():
            raise ValueError(f"GTFS feed does not exist: {self.feed_path}")

        try:
            with ZipFile(self.feed_path) as archive:
                stops = _unique_by(_read_table(archive, "stops.txt"), "stop_id", "stops.txt")
                routes = _unique_by(_read_table(archive, "routes.txt"), "route_id", "routes.txt")
                trips = _unique_by(_read_table(archive, "trips.txt"), "trip_id", "trips.txt")
                stop_times = _read_table(archive, "stop_times.txt")
        except BadZipFile as exc:
            raise ValueError(f"GTFS feed is not a readable ZIP archive: {self.feed_path}") from exc

        stops_by_trip: dict[str, list[tuple[int, dict[str, str]]]] = {}
        for row in stop_times:
            trip_id = row["trip_id"]
            stop_id = row["stop_id"]
            if trip_id not in trips:
                raise ValueError(f"stop_times.txt references unknown trip_id {trip_id!r}")
            if stop_id not in stops:
                raise ValueError(f"stop_times.txt references unknown stop_id {stop_id!r}")
            try:
                sequence = int(row["stop_sequence"])
            except ValueError as exc:
                raise ValueError(
                    f"stop_times.txt has non-integer stop_sequence {row['stop_sequence']!r}"
                ) from exc
            if sequence < 0:
                raise ValueError("stop_times.txt stop_sequence must be non-negative")
            stops_by_trip.setdefault(trip_id, []).append((sequence, row))

        checksum = hashlib.sha256(self.feed_path.read_bytes()).hexdigest()
        records: list[RawSourceRecord] = []
        for trip_id, trip in trips.items():
            route_id = trip["route_id"]
            if route_id not in routes:
                raise ValueError(f"trips.txt references unknown route_id {route_id!r}")
            ordered_stops = sorted(stops_by_trip.get(trip_id, ()), key=lambda item: item[0])
            if not ordered_stops:
                raise ValueError(f"trip {trip_id!r} has no stop_times.txt rows")
            sequences = [sequence for sequence, _ in ordered_stops]
            if len(sequences) != len(set(sequences)):
                raise ValueError(f"trip {trip_id!r} has duplicate stop_sequence values")

            stop_payload = [
                {
                    "stop_sequence": sequence,
                    "stop_id": row["stop_id"],
                    "stop_name": stops[row["stop_id"]]["stop_name"],
                    "arrival_time": row["arrival_time"],
                    "departure_time": row["departure_time"],
                }
                for sequence, row in ordered_stops
            ]
            locator = f"{self.feed_path.name}!/trips.txt#{trip_id}"
            records.append(
                RawSourceRecord(
                    record_id=f"{query.query_id}-trip-{trip_id}",
                    entity_scope="transport",
                    provider_entity_id=trip_id,
                    payload_type="gtfs_static_trip",
                    payload={
                        "trip_id": trip_id,
                        "service_id": trip["service_id"],
                        "trip_headsign": trip["trip_headsign"],
                        "route": routes[route_id],
                        "stops": stop_payload,
                    },
                    content_language=query.locale,
                    captured_at=query.requested_at,
                    payload_locator=locator,
                    payload_checksum=checksum,
                    provenance_hint="official_static_schedule",
                    metadata={"feed_name": self.feed_path.name, "route_id": route_id},
                    notes=["Static schedule data; confirm live service before booking."],
                )
            )

        return RawSnapshot(
            snapshot_id=f"{query.query_id}-snapshot",
            adapter_id=self.adapter_id,
            source_id=self.source_record.source_id,
            source_category=self.source_record.category,
            entity_scope="transport",
            option_kind="rail",
            fetched_at=query.requested_at,
            query=query,
            records=records,
            payload_format="gtfs",
            transport="file",
            snapshot_status="complete",
            handoff_status="ready",
            payload_metadata={
                "feed_name": self.feed_path.name,
                "sha256": checksum,
                "trip_count": str(len(records)),
            },
            notes=["Loaded from a static Amtrak GTFS ZIP; no live request was made."],
        )

    def build_handoff(self, snapshot: RawSnapshot) -> NormalizationHandoff:
        provenance_refs = [
            ProvenanceReference(
                provenance_id=f"{snapshot.snapshot_id}:{record.record_id}",
                source_id=snapshot.source_id,
                source_category=snapshot.source_category,
                subject_kind="option",
                subject_id=f"{record.record_id}:rail-option",
                contribution_kind="operational",
                summary="Amtrak static GTFS supplied the rail route and scheduled stops.",
                locator=record.payload_locator,
                captured_at=record.captured_at or snapshot.fetched_at,
                notes=["Static schedule only; availability and price require another source."],
            )
            for record in snapshot.records
        ]
        return NormalizationHandoff(
            handoff_id=f"{snapshot.snapshot_id}-handoff",
            snapshot_id=snapshot.snapshot_id,
            target_contract=_TARGET_CONTRACT,
            entity_scope=snapshot.entity_scope,
            status="ready",
            input_record_ids=[record.record_id for record in snapshot.records],
            provenance_refs=provenance_refs,
            record_count=len(snapshot.records),
            notes=["Rail schedule records are ready for transport-option normalization."],
        )
