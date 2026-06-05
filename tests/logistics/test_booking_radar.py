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
