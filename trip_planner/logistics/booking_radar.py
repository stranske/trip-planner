"""Static advance-booking radar for known scarce trip items."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from importlib import resources
from typing import Any

_SPACE_RE = re.compile(r"[^a-z0-9]+")
_APPETITE_LIMITS = {
    "minimal": 3,
    "anchored": 6,
    "expansive": 12,
}


@dataclass(frozen=True, slots=True)
class BookingFlag:
    item: str
    why: str
    deadline_rule: str
    confidence: str
    release_pattern: str
    backup: str
    matched_on: str
    pattern_id: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def scan_trip(trip: dict[str, Any], *, appetite: str = "anchored") -> list[BookingFlag]:
    """Return static advance-booking flags for matching trip segments and POIs."""

    if not isinstance(trip, dict):
        raise ValueError("trip must be a dictionary")
    matches = [
        flag
        for pattern in _load_patterns()
        for flag in _match_pattern(pattern, trip)
    ]
    deduped = _dedupe(matches)
    deduped.sort(key=_flag_sort_key)
    return _apply_appetite_limit(deduped, appetite)


def _load_patterns() -> list[dict[str, Any]]:
    data = (
        resources.files("trip_planner.resources.logistics")
        .joinpath("must_prebook.json")
        .read_text(encoding="utf-8")
    )
    payload = json.loads(data)
    patterns = payload.get("patterns", [])
    if not isinstance(patterns, list):
        raise ValueError("must_prebook.json must contain a patterns list")
    return [pattern for pattern in patterns if isinstance(pattern, dict)]


def _match_pattern(pattern: dict[str, Any], trip: dict[str, Any]) -> list[BookingFlag]:
    scope = str(pattern.get("scope") or "").strip()
    if scope == "transport":
        candidates = _transport_candidates(trip)
    elif scope == "poi":
        candidates = _poi_candidates(trip)
    else:
        return []
    flags: list[BookingFlag] = []
    for candidate in candidates:
        if _candidate_matches(pattern, candidate):
            flags.append(_flag_from_pattern(pattern, matched_on=candidate["matched_on"]))
    return flags


def _transport_candidates(trip: dict[str, Any]) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for item in _iter_nested_dicts(trip):
        mode = _text(item.get("mode") or item.get("transport_mode") or item.get("category"))
        operator = _text(item.get("operator") or item.get("provider") or item.get("carrier"))
        route_text = _joined(
            item.get("route"),
            item.get("route_name"),
            item.get("title"),
            item.get("name"),
            item.get("summary"),
            item.get("from"),
            item.get("origin"),
            item.get("to"),
            item.get("destination"),
        )
        if not any((mode, operator, route_text)):
            continue
        candidates.append(
            {
                "mode": mode,
                "operator": operator,
                "route": route_text,
                "matched_on": _joined(operator, route_text, mode),
            }
        )
    return candidates


def _poi_candidates(trip: dict[str, Any]) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for item in _iter_nested_dicts(trip):
        name = _text(item.get("name") or item.get("title") or item.get("label"))
        if not name:
            continue
        place_kind = _text(item.get("place_kind") or item.get("activity_kind") or item.get("kind"))
        aliases = _joined(
            item.get("poi"),
            item.get("site"),
            item.get("destination"),
            item.get("summary"),
            item.get("notes"),
        )
        candidates.append(
            {
                "name": name,
                "aliases": aliases,
                "kind": place_kind,
                "matched_on": _joined(name, aliases),
            }
        )
    return candidates


def _candidate_matches(pattern: dict[str, Any], candidate: dict[str, str]) -> bool:
    terms = [
        _normalized(term)
        for term in pattern.get("match_terms", [])
        if isinstance(term, str) and term.strip()
    ]
    haystack = _normalized(" ".join(candidate.values()))
    if not terms or not any(term in haystack for term in terms):
        return False
    modes = [
        _normalized(mode)
        for mode in pattern.get("modes", [])
        if isinstance(mode, str) and mode.strip()
    ]
    return not modes or any(mode in haystack for mode in modes)


def _flag_from_pattern(pattern: dict[str, Any], *, matched_on: str) -> BookingFlag:
    return BookingFlag(
        item=str(pattern["item"]),
        why=str(pattern["why"]),
        deadline_rule=str(pattern["deadline_rule"]),
        confidence=str(pattern["confidence"]),
        release_pattern=str(pattern["release_pattern"]),
        backup=str(pattern["backup"]),
        matched_on=matched_on,
        pattern_id=str(pattern["id"]),
    )


def _iter_nested_dicts(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        found.append(value)
        for child in value.values():
            found.extend(_iter_nested_dicts(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_iter_nested_dicts(child))
    return found


def _dedupe(flags: list[BookingFlag]) -> list[BookingFlag]:
    by_pattern: dict[str, BookingFlag] = {}
    for flag in flags:
        by_pattern.setdefault(flag.pattern_id, flag)
    return list(by_pattern.values())


def _flag_sort_key(flag: BookingFlag) -> tuple[int, int, str]:
    release_rank = 0 if flag.release_pattern == "none" else 1
    confidence_rank = {"high": 0, "medium": 1, "low": 2}.get(flag.confidence, 3)
    return (release_rank, confidence_rank, flag.item)


def _apply_appetite_limit(flags: list[BookingFlag], appetite: str) -> list[BookingFlag]:
    limit = _APPETITE_LIMITS.get(str(appetite or "anchored").strip().lower(), 6)
    required = [flag for flag in flags if flag.release_pattern == "none" or flag.confidence == "high"]
    selected: list[BookingFlag] = []
    for flag in [*required, *flags]:
        if flag not in selected:
            selected.append(flag)
        if len(selected) >= limit and flag not in required:
            break
    return selected


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return " ".join(_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(_text(item) for item in value.values())
    return str(value)


def _joined(*values: Any) -> str:
    return " ".join(part for part in (_text(value).strip() for value in values) if part)


def _normalized(value: str) -> str:
    return _SPACE_RE.sub(" ", value.casefold()).strip()
