"""Resolve traveller-entered destinations to real places, and measure real distance."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from math import asin, cos, radians, sin, sqrt

_EARTH_RADIUS_KM = 6371.0088

#: Trailing administrative qualifiers travellers habitually append ("Chicago, IL").
_QUALIFIER_SPLIT = re.compile(r"\s*[,/|]\s*")


@dataclass(frozen=True)
class ResolvedPlace:
    """A destination the planner has real coordinates for."""

    query: str
    name: str
    latitude: float
    longitude: float
    country_code: str
    population: int

    def to_geo_payload(self) -> dict[str, object]:
        """Shape the inventory adapter consumes."""

        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "country_code": self.country_code,
            "time_zone": "",
            "locality_hint": self.name,
        }


def _normalise(value: str) -> str:
    """Casefold and strip accents so 'Reykjavík' and 'Reykjavik' are the same place."""

    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(stripped.casefold().split())


@lru_cache(maxsize=1)
def _city_index() -> dict[str, tuple]:
    """Map every normalised city name (and alternate name) to its largest match.

    Built once per process. Ties are resolved by population so that "Chicago" is the
    Illinois city of 2.6 million rather than a hamlet that happens to share the name.
    """

    import geonamescache

    index: dict[str, tuple] = {}
    for city in geonamescache.GeonamesCache().get_cities().values():
        population = int(city.get("population") or 0)
        names = {city.get("name") or ""}
        names.update(city.get("alternatenames") or [])
        for name in names:
            if not name:
                continue
            key = _normalise(name)
            existing = index.get(key)
            if existing is None or population > existing[4]:
                index[key] = (
                    city.get("name") or name,
                    float(city["latitude"]),
                    float(city["longitude"]),
                    str(city.get("countrycode") or ""),
                    population,
                )
    return index


def _candidate_keys(destination: str) -> list[str]:
    """Progressively simpler forms of a traveller's destination string."""

    parts = [part for part in _QUALIFIER_SPLIT.split(destination) if part.strip()]
    candidates: list[str] = []
    if parts:
        # "Chicago, IL" -> try the whole string, then the leading locality.
        candidates.append(_normalise(destination))
        candidates.append(_normalise(parts[0]))
    else:
        candidates.append(_normalise(destination))
    ordered: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in ordered:
            ordered.append(candidate)
    return ordered


def resolve_place(destination: str) -> ResolvedPlace | None:
    """Return the real place a destination names, or None when it cannot be resolved.

    None means "the planner does not know this place" and must surface as a stated
    limit. It must never be replaced with a default coordinate.
    """

    if not destination or not destination.strip():
        return None
    index = _city_index()
    for key in _candidate_keys(destination):
        hit = index.get(key)
        if hit is not None:
            name, lat, lon, country, population = hit
            return ResolvedPlace(
                query=destination,
                name=name,
                latitude=lat,
                longitude=lon,
                country_code=country,
                population=population,
            )
    return None


def distance_km(origin: ResolvedPlace, destination: ResolvedPlace) -> float:
    """Great-circle distance between two resolved places, in kilometres."""

    lat1, lon1 = radians(origin.latitude), radians(origin.longitude)
    lat2, lon2 = radians(destination.latitude), radians(destination.longitude)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    haversine = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * asin(sqrt(haversine))
