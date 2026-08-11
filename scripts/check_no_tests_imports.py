#!/usr/bin/env python3
"""Fail when production modules import from the tests package."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    trip_planner_root = repo_root / "trip_planner"
    offenders: list[str] = []

    for path in sorted(trip_planner_root.rglob("*.py")):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "from tests." in stripped or stripped.startswith("import tests"):
                offenders.append(f"{path.relative_to(repo_root)}:{line_no}: {stripped}")

    if offenders:
        print("Production code must not import from tests:", file=sys.stderr)
        for offender in offenders:
            print(f"  {offender}", file=sys.stderr)
        return 1

    print("No production imports from tests detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
