from __future__ import annotations

from trip_planner.logistics.booking_radar import scan_trip


def test_flags_known_scarce_items() -> None:
    trip = {
        "transport_segments": [
            {
                "mode": "rail",
                "operator": "Glacier Express",
                "route": "Zermatt to St Moritz",
            }
        ],
        "pois": [
            {
                "name": "Alhambra Nasrid Palaces",
                "activity_kind": "sight",
            }
        ],
    }

    flags = scan_trip(trip)
    by_item = {flag.item: flag for flag in flags}

    assert "Glacier Express seat reservation" in by_item
    assert "Alhambra Nasrid Palaces timed entry" in by_item
    assert by_item["Glacier Express seat reservation"].deadline_rule
    assert by_item["Glacier Express seat reservation"].backup
    assert by_item["Alhambra Nasrid Palaces timed entry"].deadline_rule
    assert by_item["Alhambra Nasrid Palaces timed entry"].backup


def test_no_release_item_never_promises_release() -> None:
    trip = {
        "pois": [
            {
                "name": "Classic Inca Trail trek",
                "summary": "Four-day operator-led Machu Picchu trek.",
            }
        ],
    }

    flags = scan_trip(trip)
    flag = next(item for item in flags if item.item == "Inca Trail permit")

    assert flag.release_pattern == "none"
    assert "release" not in flag.backup.casefold()
    assert "operator" in flag.deadline_rule.casefold()


def test_declared_lists_bound_match_surface() -> None:
    trip = {
        "transport_segments": [],
        "pois": [],
        "inventory_summary": {
            "bundles": [
                {
                    "title": "Glacier Express and Alhambra research notes",
                    "summary": "Contains text that should not count as a saved transport segment or POI.",
                }
            ]
        },
    }

    assert scan_trip(trip) == []


def test_minimal_appetite_truncates_but_keeps_no_release_flags() -> None:
    trip = {
        "transport_segments": [
            {"mode": "rail", "operator": "Glacier Express", "route": "Zermatt St Moritz"},
            {"mode": "rail", "operator": "Bernina Express", "route": "Tirano Chur"},
            {"mode": "rail", "operator": "Eurostar", "route": "London Paris"},
            {"mode": "rail", "route": "Paris Milan"},
        ],
        "pois": [
            {"name": "Classic Inca Trail trek"},
            {"name": "Alhambra Nasrid Palaces"},
            {"name": "The Last Supper"},
            {"name": "Half Dome"},
        ],
    }

    minimal_flags = scan_trip(trip, appetite="minimal")
    expansive_flags = scan_trip(trip, appetite="expansive")

    assert len(minimal_flags) < len(expansive_flags)
    assert any(flag.item == "Inca Trail permit" for flag in minimal_flags)
