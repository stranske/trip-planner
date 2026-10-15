"""Find the timetabled train between two places from a static GTFS feed (Amtrak).

This is the first provider data the planner uses for a route: real stations, real
departure and arrival times, real journey durations. It carries no fares and no seat
availability, and it says so. Wired from `docs/provider-sources-plan.md` §7a.

Every lookup returns a `RailLookup` whose `status` names what happened. "No feed on this
server" and "no direct train" must never read alike: the first is a gap in the planner, the
second is a fact about the railway.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from io import TextIOWrapper
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from trip_planner.geo.resolver import ResolvedPlace, distance_km
from trip_planner.sources.adapters.amtrak_gtfs import AmtrakGtfsAdapter
from trip_planner.sources.snapshots import SourceQuery

#: Where the server finds the Amtrak static GTFS ZIP. Unset means rail is not looked up.
FEED_PATH_ENV = "TRIP_PLANNER_AMTRAK_GTFS_PATH"
#: A station counts as serving a place when it is this close to the place's coordinates.
STATION_RADIUS_KM = 30.0

#: RailLookup.status values. One constant per outcome, consumed by producer and readers.
NOT_CONFIGURED = "not_configured"
FEED_UNREADABLE = "feed_unreadable"
NO_STATION_NEAR_ORIGIN = "no_station_near_origin"
NO_STATION_NEAR_DESTINATION = "no_station_near_destination"
NO_DIRECT_TRAIN = "no_direct_train"
NO_TRAIN_ON_DATE = "no_train_on_date"
FOUND = "found"


@dataclass(frozen=True)
class Station:
    stop_id: str
    name: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class TrainTrip:
    trip_id: str
    service_id: str
    route_name: str
    headsign: str
    #: (stop_id, arrival minutes, departure minutes) in timetable order.
    calls: tuple[tuple[str, int, int], ...]


@dataclass(frozen=True)
class DirectTrain:
    trip_id: str
    route_name: str
    headsign: str
    origin_station: Station
    destination_station: Station
    departs: str
    arrives: str
    duration_minutes: int
    #: True: the feed's calendar says it runs on the travel date. None: not checkable.
    runs_on_date: bool | None


@dataclass(frozen=True)
class RailLookup:
    status: str
    summary: str
    train: DirectTrain | None = None
    #: How many distinct direct trains serve the pair on the date (or in the feed).
    direct_train_count: int = 0
    feed_name: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)


def _minutes(value: str) -> int:
    """GTFS time "HH:MM:SS"; hours may exceed 23 for trips past midnight."""

    hours, minutes, *_ = value.split(":")
    return int(hours) * 60 + int(minutes)


def _clock(minutes: int) -> str:
    day_minutes = minutes % (24 * 60)
    suffix = " (+1 day)" if minutes >= 24 * 60 else ""
    return f"{day_minutes // 60:02d}:{day_minutes % 60:02d}{suffix}"


def _optional_table(archive: ZipFile, name: str) -> list[dict[str, str]] | None:
    try:
        member = archive.open(name)
    except KeyError:
        return None
    with member, TextIOWrapper(member, encoding="utf-8-sig", newline="") as stream:
        return [
            {key: (value or "").strip() for key, value in row.items() if key}
            for row in csv.DictReader(stream)
        ]


@dataclass(frozen=True)
class RailSchedule:
    feed_name: str
    stations: dict[str, Station]
    trips: tuple[TrainTrip, ...]
    #: service_id -> (weekday flags Mon..Sun, start, end); None when the feed has no calendar.
    calendar: dict[str, tuple[tuple[bool, ...], date, date]] | None
    #: (service_id, date) -> True added / False removed.
    exceptions: dict[tuple[str, date], bool]

    def runs_on(self, service_id: str, day: date) -> bool | None:
        if self.calendar is None and not self.exceptions:
            return None
        override = self.exceptions.get((service_id, day))
        if override is not None:
            return override
        entry = (self.calendar or {}).get(service_id)
        if entry is None:
            return False
        weekdays, start, end = entry
        return start <= day <= end and weekdays[day.weekday()]

    def stations_near(self, place: ResolvedPlace) -> list[Station]:
        near = []
        for station in self.stations.values():
            probe = ResolvedPlace(
                query=station.name,
                name=station.name,
                latitude=station.latitude,
                longitude=station.longitude,
                country_code=place.country_code,
                population=0,
            )
            if distance_km(place, probe) <= STATION_RADIUS_KM:
                near.append(station)
        return near


def _gtfs_date(value: str) -> date:
    return date(int(value[:4]), int(value[4:6]), int(value[6:8]))


def _load(path: Path) -> RailSchedule:
    """Parse a feed. Trips go through the adapter, so its validation applies unchanged."""

    snapshot = AmtrakGtfsAdapter(path).fetch_snapshot(
        SourceQuery(
            query_id="rail-schedule-load",
            entity_scope="transport",
            option_kind="rail",
            requested_at="1970-01-01T00:00:00Z",
        )
    )
    trips = []
    for record in snapshot.records:
        payload = record.payload
        route = payload["route"]
        trips.append(
            TrainTrip(
                trip_id=payload["trip_id"],
                service_id=payload["service_id"],
                route_name=route.get("route_long_name") or route.get("route_short_name") or "",
                headsign=payload.get("trip_headsign") or "",
                calls=tuple(
                    (
                        stop["stop_id"],
                        _minutes(stop["arrival_time"]),
                        _minutes(stop["departure_time"]),
                    )
                    for stop in payload["stops"]
                ),
            )
        )
    with ZipFile(path) as archive:
        stations = {}
        for row in _optional_table(archive, "stops.txt") or []:
            try:
                latitude, longitude = float(row["stop_lat"]), float(row["stop_lon"])
            except (KeyError, ValueError):
                continue  # a stop without coordinates cannot be matched to a place
            if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
                continue
            stations[row["stop_id"]] = Station(
                stop_id=row["stop_id"],
                name=row["stop_name"],
                latitude=latitude,
                longitude=longitude,
            )
        calendar_rows = _optional_table(archive, "calendar.txt")
        exception_rows = _optional_table(archive, "calendar_dates.txt") or []
    days = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
    calendar = (
        {
            row["service_id"]: (
                tuple(row.get(day) == "1" for day in days),
                _gtfs_date(row["start_date"]),
                _gtfs_date(row["end_date"]),
            )
            for row in calendar_rows
        }
        if calendar_rows is not None
        else None
    )
    exceptions = {
        (row["service_id"], _gtfs_date(row["date"])): row.get("exception_type") == "1"
        for row in exception_rows
    }
    return RailSchedule(
        feed_name=path.name,
        stations=stations,
        trips=tuple(trips),
        calendar=calendar,
        exceptions=exceptions,
    )


@lru_cache(maxsize=4)
def _load_cached(path: str, mtime_ns: int) -> RailSchedule:
    del mtime_ns  # part of the cache key, so a replaced feed is read again
    return _load(Path(path))


def configured_feed_path() -> Path | None:
    raw = os.getenv(FEED_PATH_ENV, "").strip()
    return Path(raw) if raw else None


def _direct_trains(
    schedule: RailSchedule, origins: list[Station], destinations: list[Station]
) -> list[tuple[TrainTrip, Station, Station, int, int]]:
    origin_ids = {station.stop_id: station for station in origins}
    destination_ids = {station.stop_id: station for station in destinations}
    found = []
    for trip in schedule.trips:
        boarding: tuple[Station, int] | None = None
        for stop_id, arrival, departure in trip.calls:
            if boarding is None and stop_id in origin_ids:
                boarding = (origin_ids[stop_id], departure)
            elif boarding is not None and stop_id in destination_ids:
                found.append((trip, boarding[0], destination_ids[stop_id], boarding[1], arrival))
                break
    return found


def find_direct_train(
    origin: ResolvedPlace,
    destination: ResolvedPlace,
    *,
    travel_date: date | None,
    feed_path: Path | None = None,
) -> RailLookup:
    """The fastest timetabled direct train from origin to destination, or why there is none."""

    path = feed_path or configured_feed_path()
    if path is None:
        return RailLookup(NOT_CONFIGURED, "Train timetables are not loaded on this server.")
    try:
        schedule = _load_cached(str(path), path.stat().st_mtime_ns)
    except (OSError, ValueError, BadZipFile) as error:
        return RailLookup(
            FEED_UNREADABLE,
            f"The train timetable file could not be read ({type(error).__name__}).",
            feed_name=path.name,
        )
    origins = schedule.stations_near(origin)
    if not origins:
        return RailLookup(
            NO_STATION_NEAR_ORIGIN,
            f"No Amtrak station within {STATION_RADIUS_KM:.0f} km of {origin.name}.",
            feed_name=schedule.feed_name,
        )
    destinations = schedule.stations_near(destination)
    if not destinations:
        return RailLookup(
            NO_STATION_NEAR_DESTINATION,
            f"No Amtrak station within {STATION_RADIUS_KM:.0f} km of {destination.name}.",
            feed_name=schedule.feed_name,
        )
    candidates = _direct_trains(schedule, origins, destinations)
    if not candidates:
        return RailLookup(
            NO_DIRECT_TRAIN,
            f"No direct Amtrak train runs from {origin.name} to {destination.name}; "
            "journeys with a change are not searched.",
            feed_name=schedule.feed_name,
        )
    runs = {
        trip.trip_id: (
            schedule.runs_on(trip.service_id, travel_date) if travel_date is not None else None
        )
        for trip, *_ in candidates
    }
    dated = [c for c in candidates if runs[c[0].trip_id] is not False]
    if not dated:
        return RailLookup(
            NO_TRAIN_ON_DATE,
            f"Direct Amtrak trains run from {origin.name} to {destination.name}, but the "
            f"timetable shows none on {travel_date.isoformat() if travel_date else 'that date'}.",
            direct_train_count=0,
            feed_name=schedule.feed_name,
        )
    trip, board, alight, departs, arrives = min(dated, key=lambda c: (c[4] - c[3], c[3]))
    train = DirectTrain(
        trip_id=trip.trip_id,
        route_name=trip.route_name,
        headsign=trip.headsign,
        origin_station=board,
        destination_station=alight,
        departs=_clock(departs),
        arrives=_clock(arrives),
        duration_minutes=arrives - departs,
        runs_on_date=runs[trip.trip_id],
    )
    notes = ["Timetable only: no fare and no seat availability."]
    if train.runs_on_date is None:
        notes.append(
            "The timetable file has no service calendar, so the travel date was not checked."
        )
    return RailLookup(
        FOUND,
        (
            f"Amtrak {train.route_name}: {board.name} {train.departs} → {alight.name} "
            f"{train.arrives}, {train.duration_minutes // 60} h {train.duration_minutes % 60:02d} min, "
            "direct."
        ),
        train=train,
        direct_train_count=len({c[0].trip_id for c in dated}),
        feed_name=schedule.feed_name,
        notes=tuple(notes),
    )
