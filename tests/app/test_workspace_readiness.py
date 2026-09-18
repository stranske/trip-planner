"""Readiness must reflect traveller-supplied context, not generated placeholders.

A trip created with nothing but a title still receives generated inventory bundles and
scenario drafts. Before this guard the workspace reported "Your trip plan is ready to
review." for such a trip, which is the opposite of the truth.
"""

from __future__ import annotations

from typing import Any

from trip_planner.app.services.workspace_view_model import build_workspace_view_model


def _payload(*, mode: str = "business", **frame: Any) -> dict[str, Any]:
    trip_frame = {
        "start_date": None,
        "end_date": None,
        "duration_days": 7,
        "primary_regions": [],
        "traveler_party": {"kind": "solo", "traveler_count": 1, "notes": ""},
    }
    trip_frame.update(frame.pop("trip_frame", {}))
    return {
        "trip_record": {
            "trip": {
                "trip_id": "trip-test",
                "title": "Test trip",
                "summary": frame.pop("summary", ""),
                "mode": mode,
                "trip_frame": trip_frame,
            }
        },
        # Placeholder artefacts that exist for every trip from the moment it is created.
        "runtime_state": {"status": "ready"},
        "saved_scenarios": [{"saved_scenario_id": "a"}, {"saved_scenario_id": "b"}],
        "inventory_summary": {"bundle_count": 1},
        "feasibility_summary": {},
    }


def _complete_frame() -> dict[str, Any]:
    return {
        "trip_frame": {
            "start_date": "2026-10-12",
            "end_date": "2026-10-15",
            "duration_days": 4,
            "primary_regions": ["Chicago, IL"],
            "traveler_party": {"kind": "solo", "traveler_count": 1, "notes": ""},
        },
        "summary": "Quarterly review with the Northwind account team",
    }


def test_bare_trip_is_not_reported_as_ready_to_review() -> None:
    model = build_workspace_view_model(_payload())
    summary = model["user_summary"]

    assert summary["status"] == "empty"
    assert "ready to review" not in summary["headline"]
    assert "a destination" in summary["headline"]
    assert "travel dates" in summary["headline"]


def test_bare_trip_does_not_claim_generated_artefacts_as_decisions() -> None:
    model = build_workspace_view_model(_payload())

    # Generated drafts/bundles must not be presented as progress the traveller made.
    assert model["user_summary"]["decided"] == []
    assert any("missing a destination" in item for item in model["user_summary"]["uncertain"])


def test_business_trip_requires_a_purpose_for_the_approver() -> None:
    frame = _complete_frame()
    frame["summary"] = ""
    model = build_workspace_view_model(_payload(mode="business", **frame))

    assert model["user_summary"]["status"] == "empty"
    assert "business purpose" in model["user_summary"]["headline"]


def test_leisure_trip_does_not_require_a_business_purpose() -> None:
    frame = _complete_frame()
    frame["summary"] = ""
    model = build_workspace_view_model(_payload(mode="leisure", **frame))

    assert model["user_summary"]["status"] == "ready"
    assert model["user_summary"]["headline"] == "Your trip plan is ready to review."


def test_complete_trip_is_still_reported_as_ready() -> None:
    model = build_workspace_view_model(_payload(**_complete_frame()))
    summary = model["user_summary"]

    assert summary["status"] == "ready"
    assert summary["headline"] == "Your trip plan is ready to review."
    assert "2 saved scenario draft(s)" in summary["decided"]
