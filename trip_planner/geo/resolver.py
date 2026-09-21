"""Resolve traveller-entered destinations to real places, and measure real distance."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from math import asin, cos, isfinite, radians, sin, sqrt

_EARTH_RADIUS_KM = 6371.0088

#: Trailing administrative qualifiers travellers habitually append ("Chicago, IL").
_QUALIFIER_SPLIT = re.compile(r"\s*[,/|]\s*")

_US_STATE_CODES = frozenset(
    {
        "AL",
        "AK",
        "AZ",
        "AR",
        "CA",
        "CO",
        "CT",
        "DE",
        "FL",
        "GA",
        "HI",
        "ID",
        "IL",
        "IN",
        "IA",
        "KS",
        "KY",
        "LA",
        "ME",
        "MD",
        "MA",
        "MI",
        "MN",
        "MS",
        "MO",
        "MT",
        "NE",
        "NV",
        "NH",
        "NJ",
        "NM",
        "NY",
        "NC",
        "ND",
        "OH",
        "OK",
        "OR",
        "PA",
        "RI",
        "SC",
        "SD",
        "TN",
        "TX",
        "UT",
        "VT",
        "VA",
        "WA",
        "WV",
        "WI",
        "WY",
        "DC",
    }
)

_COUNTRY_ALIASES: dict[str, str] = {
    "gb": "GB",
    "iceland": "IS",
    "is": "IS",
    "japan": "JP",
    "jp": "JP",
    "kenya": "KE",
    "ke": "KE",
    "uk": "GB",
    "united kingdom": "GB",
    "united states": "US",
    "us": "US",
    "usa": "US",
}


@dataclass(frozen=True)
class ResolvedPlace:
    """A destination the planner has real coordinates for."""

    query: str
    name: str
    latitude: float
    longitude: float
    country_code: str
    population: int

    def __post_init__(self) -> None:
        if not isfinite(self.latitude) or not -90.0 <= self.latitude <= 90.0:
            raise ValueError(f"invalid latitude: {self.latitude!r}")
        if not isfinite(self.longitude) or not -180.0 <= self.longitude <= 180.0:
            raise ValueError(f"invalid longitude: {self.longitude!r}")

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


def _coerce_float(value: object) -> float:
    if isinstance(value, (int, float, str)):
        return float(value)
    raise TypeError(f"expected numeric coordinate, got {type(value)!r}")


def _coerce_int(value: object, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        return int(value) if value else default
    return default


def _coerce_str_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return []


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


@lru_cache(maxsize=1)
def _country_name_index() -> dict[str, str]:
    """Map normalized GeoNames country names to their two-letter codes."""

    import geonamescache

    index: dict[str, str] = {}
    for code, country in geonamescache.GeonamesCache().get_countries().items():
        name = str(country.get("name") or "")
        if name:
            index[_normalise(name)] = str(code).upper()
    return index


def _qualifier_filters(qualifier: str) -> tuple[str | None, str | None]:
    token = qualifier.strip()
    if not token:
        return None, None
    upper = token.upper()
    if len(upper) == 2 and upper in _US_STATE_CODES:
        return "US", upper
    if len(upper) == 2:
        return upper, None
    country = _COUNTRY_ALIASES.get(_normalise(token))
    if country:
        return country, None
    country = _country_name_index().get(_normalise(token))
    if country:
        return country, None
    return None, None


def _city_matches_name(city: dict[str, object], city_key: str) -> bool:
    names = {str(city.get("name") or "")}
    names.update(_coerce_str_list(city.get("alternatenames")))
    return any(_normalise(name) == city_key for name in names if name)


def _resolved_place_from_city(
    destination: str, city: dict[str, object]
) -> ResolvedPlace:
    return ResolvedPlace(
        query=destination,
        name=str(city.get("name") or destination),
        latitude=_coerce_float(city["latitude"]),
        longitude=_coerce_float(city["longitude"]),
        country_code=str(city.get("countrycode") or ""),
        population=_coerce_int(city.get("population")),
    )


@lru_cache(maxsize=1)
def _qualified_city_index() -> dict[tuple[str, str, str], dict[str, object]]:
    """Index qualified city names once, retaining the largest matching place."""
    import geonamescache

    index: dict[tuple[str, str, str], dict[str, object]] = {}
    for raw_city in geonamescache.GeonamesCache().get_cities().values():
        city = dict(raw_city)
        country = str(city.get("countrycode") or "")
        admin = str(city.get("admin1code") or "")
        names = {str(city.get("name") or "")}
        names.update(_coerce_str_list(city.get("alternatenames")))
        for name in names:
            if not name:
                continue
            normalised = _normalise(name)
            for key in ((normalised, country, ""), (normalised, country, admin)):
                existing = index.get(key)
                if existing is None or _coerce_int(
                    city.get("population")
                ) > _coerce_int(existing.get("population")):
                    index[key] = city
    return index


def _resolve_with_qualifier(city: str, qualifier: str) -> ResolvedPlace | None:
    country_filter, admin_filter = _qualifier_filters(qualifier)
    if country_filter is None:
        return None

    city_key = _normalise(city)
    city_data = _qualified_city_index().get(
        (city_key, country_filter, admin_filter or "")
    )
    if city_data is None:
        return None
    return _resolved_place_from_city(f"{city}, {qualifier}", city_data)


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

    parts = [
        part.strip() for part in _QUALIFIER_SPLIT.split(destination) if part.strip()
    ]
    if len(parts) >= 2:
        qualified = _resolve_with_qualifier(parts[0], parts[-1])
        if qualified is not None:
            return qualified
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
