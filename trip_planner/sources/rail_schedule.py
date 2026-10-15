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
from datetime import date, timedelta
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


#: GTFS route_type for rail. Amtrak's feed also carries Thruway buses (route_type 3),
#: which must not be shown as a train.
RAIL_ROUTE_TYPE = "2"


@dataclass(frozen=True)
class TrainTrip:
    trip_id: str
    service_id: str
    route_name: str
    train_number: str
    headsign: str
    #: (stop_id, arrival minutes, departure minutes, can board, can alight), in order.
    calls: tuple[tuple[str, int | None, int | None, bool, bool], ...]


@dataclass(frozen=True)
class DirectTrain:
    trip_id: str
    route_name: str
    train_number: str
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


def _minutes(value: str) -> int | None:
    """GTFS time "HH:MM:SS"; hours may exceed 23 for trips past midnight."""

    if not value or not value.strip():
        return None
    hours, minutes, *_ = value.strip().split(":")
    return int(hours) * 60 + int(minutes)


_DAY = 24 * 60


def _clock(minutes: int) -> str:
    """Minutes after midnight on the day the traveller boards, as "HH:MM"."""

    day_minutes = minutes % _DAY
    return f"{day_minutes // 60:02d}:{day_minutes % 60:02d}"


def _arrival_clock(departs: int, arrives: int) -> str:
    """Arrival time, with how many days after boarding it falls (overnight trains)."""

    days = arrives // _DAY - departs // _DAY
    suffix = "" if days == 0 else f" (+{days} day{'s' if days > 1 else ''})"
    return f"{_clock(arrives)}{suffix}"


def service_name(route_name: str) -> str:
    """ "Amtrak Acela", and "Amtrak Cascades" rather than "Amtrak Amtrak Cascades"."""

    return route_name if route_name.lower().startswith("amtrak") else f"Amtrak {route_name}"


def _optional_table(
    archive: ZipFile, name: str, *, required_columns: set[str] | None = None
) -> list[dict[str, str]] | None:
    try:
        member = archive.open(name)
    except KeyError:
        return None
    with member, TextIOWrapper(member, encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = (required_columns or set()) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(
                f"GTFS table {name!r} is missing required columns: {sorted(missing)!r}"
            )
        return [{key: (value or "").strip() for key, value in row.items() if key} for row in reader]


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
        if route.get("route_type") != RAIL_ROUTE_TYPE:
            continue
        trips.append(
            TrainTrip(
                trip_id=payload["trip_id"],
                service_id=payload["service_id"],
                route_name=route.get("route_long_name") or route.get("route_short_name") or "",
                train_number=payload.get("trip_short_name") or "",
                headsign=payload.get("trip_headsign") or "",
                calls=tuple(
                    (
                        stop["stop_id"],
                        _minutes(stop["arrival_time"]),
                        _minutes(stop["departure_time"]),
                        stop.get("pickup_type") != "1",
                        stop.get("drop_off_type") != "1",
                    )
                    for stop in payload["stops"]
                ),
            )
        )
    days = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
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
        calendar_rows = _optional_table(
            archive,
            "calendar.txt",
            required_columns={"service_id", "start_date", "end_date", *days},
        )
        exception_rows = (
            _optional_table(
                archive,
                "calendar_dates.txt",
                required_columns={"service_id", "date", "exception_type"},
            )
            or []
        )
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


#: timetable_status() values beyond NOT_CONFIGURED / FEED_UNREADABLE.
LOADED = "loaded"


def timetable_status() -> dict[str, object]:
    """Whether this server can answer rail questions, for /api/health.

    Three distinct answers: no feed configured, a feed that cannot be read (a failed
    download at deploy), or a loaded feed with its size. Never one word for two of them.
    """

    path = configured_feed_path()
    if path is None:
        return {"status": NOT_CONFIGURED, "feed_name": None, "stations": 0, "trips": 0}
    try:
        schedule = _load_cached(str(path), path.stat().st_mtime_ns)
    except (OSError, ValueError, BadZipFile) as error:
        return {
            "status": FEED_UNREADABLE,
            "feed_name": path.name,
            "reason": type(error).__name__,
            "stations": 0,
            "trips": 0,
        }
    return {
        "status": LOADED,
        "feed_name": schedule.feed_name,
        "stations": len(schedule.stations),
        "trips": len(schedule.trips),
    }


def _closest(stations: list[Station], place: ResolvedPlace) -> dict[str, float]:
    return {
        station.stop_id: distance_km(
            place,
            ResolvedPlace(
                query=station.name,
                name=station.name,
                latitude=station.latitude,
                longitude=station.longitude,
                country_code=place.country_code,
                population=0,
            ),
        )
        for station in stations
    }


def _direct_trains(
    schedule: RailSchedule,
    origin: ResolvedPlace,
    destination: ResolvedPlace,
    origins: list[Station],
    destinations: list[Station],
) -> list[tuple[TrainTrip, Station, Station, int, int]]:
    """Per train: board at the stop nearest the origin, leave at the stop nearest the
    destination. The fastest call pair would pick a suburban stop the train reaches a few
    minutes before the city ("Route 128" for Boston, "Glenview" for Chicago)."""

    origin_km = _closest(origins, origin)
    destination_km = _closest(destinations, destination)
    found = []
    for trip in schedule.trips:
        boards = [
            (index, stop_id, departure)
            for index, (stop_id, _arrival, departure, can_board, _alight) in enumerate(trip.calls)
            if stop_id in origin_km and can_board and departure is not None
        ]
        if not boards:
            continue
        b_index, b_stop, b_time = min(boards, key=lambda call: origin_km[call[1]])
        alights = [
            (stop_id, arrival)
            for stop_id, arrival, _departure, _board, can_alight in trip.calls[b_index + 1 :]
            if stop_id in destination_km and can_alight and arrival is not None
        ]
        if not alights:
            continue
        a_stop, a_time = min(alights, key=lambda call: destination_km[call[0]])
        found.append((trip, schedule.stations[b_stop], schedule.stations[a_stop], b_time, a_time))
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
    candidates = _direct_trains(schedule, origin, destination, origins, destinations)
    if not candidates:
        return RailLookup(
            NO_DIRECT_TRAIN,
            f"No direct Amtrak train runs from {origin.name} to {destination.name}; "
            "journeys with a change are not searched.",
            feed_name=schedule.feed_name,
        )
    # GTFS times count from the train's service day, so a long-distance train boards the
    # traveller's station a day or more after it starts (the Zephyr leaves Denver on day 2).
    # The calendar is asked about the service day that puts the boarding on the travel date.
    runs = {
        trip.trip_id: (
            schedule.runs_on(trip.service_id, travel_date - timedelta(days=departs // _DAY))
            if travel_date is not None
            else None
        )
        for trip, _board, _alight, departs, _arrives in candidates
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
        train_number=trip.train_number,
        headsign=trip.headsign,
        origin_station=board,
        destination_station=alight,
        departs=_clock(departs),
        arrives=_arrival_clock(departs, arrives),
        duration_minutes=arrives - departs,
        runs_on_date=runs[trip.trip_id],
    )
    notes = ["Timetable only: no fare and no seat availability."]
    if travel_date is None:
        date_summary = "No travel date was provided, so the date was not checked."
    elif train.runs_on_date is None:
        date_summary = (
            "The timetable file has no service calendar, so the travel date was not checked."
        )
    else:
        date_summary = f"Scheduled to run on {travel_date.isoformat()}."
    if train.runs_on_date is None:
        notes.append(date_summary)
    return RailLookup(
        FOUND,
        (
            f"{service_name(train.route_name)}"
            f"{f' {train.train_number}' if train.train_number else ''}: "
            f"{board.name} {train.departs} → {alight.name} "
            f"{train.arrives}, {train.duration_minutes // 60} h {train.duration_minutes % 60:02d} min, "
            f"direct. {date_summary}"
        ),
        train=train,
        direct_train_count=len({c[0].trip_id for c in dated}),
        feed_name=schedule.feed_name,
        notes=tuple(notes),
    )
