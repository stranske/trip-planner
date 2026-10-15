"""Download Amtrak's public static GTFS feed for the rail timetable lookup.

    python scripts/fetch_amtrak_gtfs.py data/amtrak/GTFS.zip
    export TRIP_PLANNER_AMTRAK_GTFS_PATH=data/amtrak/GTFS.zip

The file is public and free (docs/provider-sources-plan.md §7a). It is written to a
temporary name and only replaces the target once it parses, so a failed download never
leaves the server with a half-written timetable.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path
from urllib.request import urlopen

FEED_URL = "https://content.amtrak.com/content/gtfs/GTFS.zip"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("target", type=Path, help="where to write GTFS.zip")
    parser.add_argument("--url", default=FEED_URL)
    args = parser.parse_args(argv)

    from trip_planner.sources import rail_schedule

    args.target.parent.mkdir(parents=True, exist_ok=True)
    partial = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=args.target.parent,
            prefix=f".{args.target.name}.",
            suffix=".partial",
            delete=False,
        ) as download:
            partial = Path(download.name)
            with urlopen(args.url, timeout=120) as response:  # noqa: S310 - fixed public URL
                download.write(response.read())
        schedule = rail_schedule._load(partial)
        partial.replace(args.target)
    finally:
        if partial is not None:
            partial.unlink(missing_ok=True)
    print(
        f"{args.target}: {len(schedule.stations)} stations, {len(schedule.trips)} trips, "
        f"calendar {'present' if schedule.calendar is not None else 'absent'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
