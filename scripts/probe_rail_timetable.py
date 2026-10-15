"""Real-situation check for the rail wiring: served workspace vs an independent timetable query.

    python scripts/probe_rail_timetable.py data/amtrak/GTFS.zip

Creates trips for fixed city pairs on a Tuesday and a Saturday, reads the train each served
workspace shows (or the reason it shows none), and compares it with a query of the same GTFS
ZIP written with the plain csv module, which does not import the lookup it checks. Shared
with the lookup: the geo resolver for city coordinates. The last line printed is
"PASS NUMBER: <agree>/<total>". Uses a throwaway SQLite database.
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import sys
import tempfile
import zipfile
from datetime import date, timedelta
from typing import Any

PAIRS = [
    ("Boston", "New York, NY"),
    ("New York, NY", "Washington, DC"),
    ("New York, NY", "Philadelphia, PA"),
    ("Chicago, IL", "Milwaukee, WI"),
    ("Seattle", "Portland, OR"),
    ("Los Angeles, CA", "San Diego, CA"),
    ("Chicago, IL", "St. Louis, MO"),
    ("Washington, DC", "Boston"),
    ("Seattle", "Chicago, IL"),
    ("Denver, CO", "Salt Lake City, UT"),
    ("Atlanta, GA", "Miami, FL"),
    ("Dallas, TX", "Houston, TX"),
    ("Phoenix, AZ", "Las Vegas, NV"),
    ("Austin, TX", "Chicago, IL"),
]
DAYS = [date(2026, 10, 20), date(2026, 10, 24)]
RADIUS_KM = 30.0
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


class IndependentTimetable:
    """The same question asked of the raw tables, without trip_planner.sources."""

    def __init__(self, feed: str) -> None:
        archive = zipfile.ZipFile(feed)

        def table(name: str) -> list[dict[str, str]]:
            return list(csv.DictReader(io.TextIOWrapper(archive.open(name), encoding="utf-8-sig")))

        self.stops = {row["stop_id"]: row for row in table("stops.txt")}
        self.routes = {row["route_id"]: row for row in table("routes.txt")}
        self.trips = {row["trip_id"]: row for row in table("trips.txt")}
        self.calendar = {row["service_id"]: row for row in table("calendar.txt")}
        self.calls: dict[str, list[dict[str, str]]] = {}
        for row in table("stop_times.txt"):
            self.calls.setdefault(row["trip_id"], []).append(row)

    @staticmethod
    def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
        h = (
            math.sin((lat2 - lat1) / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
        )
        return 2 * 6371.0088 * math.asin(math.sqrt(h))

    def _distance(self, place: Any, stop_id: str) -> float:
        stop = self.stops[stop_id]
        return self._km(
            place.latitude, place.longitude, float(stop["stop_lat"]), float(stop["stop_lon"])
        )

    def _runs(self, service_id: str, day: date) -> bool:
        entry = self.calendar.get(service_id)
        if entry is None:
            return False
        in_range = entry["start_date"] <= day.strftime("%Y%m%d") <= entry["end_date"]
        return in_range and entry[WEEKDAYS[day.weekday()]] == "1"

    @staticmethod
    def _minutes(value: str) -> int:
        hours, minutes, _ = value.split(":")
        return int(hours) * 60 + int(minutes)

    def answer(self, origin: Any, destination: Any, day: date) -> tuple[str, Any]:
        near_origin = {s for s in self.stops if self._distance(origin, s) <= RADIUS_KM}
        near_destination = {s for s in self.stops if self._distance(destination, s) <= RADIUS_KM}
        if not near_origin:
            return "no_station_near_origin", None
        if not near_destination:
            return "no_station_near_destination", None
        best: tuple[tuple[int, int], str, str] | None = None
        any_direct = False
        for trip_id, rows in self.calls.items():
            if self.routes[self.trips[trip_id]["route_id"]]["route_type"] != "2":
                continue
            rows = sorted(rows, key=lambda row: int(row["stop_sequence"]))
            boards = [
                (index, row)
                for index, row in enumerate(rows)
                if row["stop_id"] in near_origin and row.get("pickup_type") != "1"
            ]
            if not boards:
                continue
            board_index, board = min(
                boards, key=lambda item: self._distance(origin, item[1]["stop_id"])
            )
            alights = [
                row
                for row in rows[board_index + 1 :]
                if row["stop_id"] in near_destination and row.get("drop_off_type") != "1"
            ]
            if not alights:
                continue
            alight = min(alights, key=lambda row: self._distance(destination, row["stop_id"]))
            any_direct = True
            departs = self._minutes(board["departure_time"])
            if self._runs(self.trips[trip_id]["service_id"], day - timedelta(days=departs // 1440)):
                key = (self._minutes(alight["arrival_time"]) - departs, departs)
                if best is None or key < best[0]:
                    number = self.trips[trip_id].get("trip_short_name") or trip_id
                    best = (key, number, self.stops[alight["stop_id"]]["stop_name"])
        if best is not None:
            return "found", (best[0][0], best[1], best[2])
        return ("no_train_on_date" if any_direct else "no_direct_train"), None


def main(argv: list[str]) -> int:
    feed = argv[1]
    os.environ["TRIP_PLANNER_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/probe.db"
    os.environ["TRIP_PLANNER_AMTRAK_GTFS_PATH"] = feed
    from fastapi.testclient import TestClient

    from trip_planner.app.main import create_app
    from trip_planner.geo.resolver import resolve_place
    from trip_planner.persistence.db import ensure_database_ready, reset_database_state

    independent = IndependentTimetable(feed)
    reset_database_state()
    ensure_database_ready()
    results = []
    with TestClient(create_app()) as client:
        client.post(
            "/api/auth/signup",
            json={"email": "probe@example.com", "password": "password123", "display_name": "Probe"},
        )
        for origin, destination in PAIRS:
            for day in DAYS:
                created = client.post(
                    "/api/trips",
                    json={
                        "title": f"{origin} to {destination}",
                        "summary": "Rail probe.",
                        "mode": "business",
                        "trip_frame": {
                            "origin": origin,
                            "start_date": day.isoformat(),
                            "end_date": day.isoformat(),
                            "duration_days": 1,
                            "primary_regions": [destination],
                        },
                    },
                )
                workspace = client.get(f"/api/workspace/{created.json()['trip']['trip_id']}").json()
                lookup = workspace["inventory_summary"]["rail_lookup"]
                rail = [
                    row
                    for row in workspace["runtime_scenario_comparison"]["scenarios"]
                    if "Amtrak" in row["title"]
                ]
                status, expected = independent.answer(
                    resolve_place(origin), resolve_place(destination), day
                )
                if expected is None:
                    agree = lookup["status"] == status and not rail
                else:
                    minutes, number, station = expected
                    agree = (
                        lookup["status"] == status
                        and len(rail) == 1
                        and rail[0]["metrics"]["travel_minutes"] == minutes
                        and f" {number}:" in rail[0]["summary"]
                        and f"→ {station} " in rail[0]["summary"]
                    )
                results.append(
                    {
                        "pair": f"{origin} -> {destination}",
                        "day": day.isoformat(),
                        "served": lookup["status"],
                        "independent": status,
                        "agree": agree,
                        "summary": lookup["summary"],
                    }
                )
    print(json.dumps(results, indent=1))
    agreed = sum(1 for row in results if row["agree"])
    print(
        f"PASS NUMBER: {agreed}/{len(results)} probe cases agree with the independent timetable query"
    )
    return 0 if agreed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
