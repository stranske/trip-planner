"""Real geographic resolution for planned destinations.

The planner previously knew six cities and placed everything else at latitude 0.0,
longitude 0.0 — Null Island — which meant no route, duration or distance could vary by
destination. This package resolves a traveller-entered destination to a real city from
the bundled GeoNames dataset and exposes real great-circle distance between stops, so
the figures the planner produces follow from the trip it is actually planning.
"""

from trip_planner.geo.resolver import (
    ResolvedPlace,
    distance_km,
    resolve_place,
)

__all__ = ["ResolvedPlace", "distance_km", "resolve_place"]
