"""Readiness must reflect traveller-supplied context, not generated placeholders.

A trip created with nothing but a title still receives generated inventory bundles and
scenario drafts. Before this guard the workspace reported "Your trip plan is ready to
review." for such a trip, which is the opposite of the truth.
"""

from __future__ import annotations

from typing import Any

from trip_planner.app.services.workspace_view_model import build_workspace_view_model


def _payload(*, mode: str = "business", **frame: Any) -> dict[str, Any]:
    trip_frame: dict[str, Any] = {
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


def test_malformed_or_reversed_dates_do_not_make_trip_ready() -> None:
    for start, end in (("bad-date", "2026-10-15"), ("2026-10-15", "2026-10-12")):
        frame = _complete_frame()
        frame["trip_frame"]["start_date"] = start
        frame["trip_frame"]["end_date"] = end
        model = build_workspace_view_model(_payload(**frame))
        assert model["user_summary"]["status"] == "empty"
        assert "travel dates" in model["user_summary"]["headline"]


def test_leisure_trip_does_not_require_a_business_purpose() -> None:
    frame = _complete_frame()
    frame["summary"] = ""
    model = build_workspace_view_model(_payload(mode="leisure", **frame))

    assert model["user_summary"]["status"] == "ready"
    assert "No prices have been entered yet" in model["user_summary"]["headline"]


def test_setup_complete_trip_does_not_claim_a_reviewable_plan() -> None:
    """Generated route shapes are not a plan, and are never the traveller's decisions."""

    model = build_workspace_view_model(_payload(**_complete_frame()))
    summary = model["user_summary"]

    assert summary["status"] == "ready"
    assert "ready to review" not in summary["headline"]
    assert summary["headline"] == "Trip setup is saved. No prices have been entered yet."
    next_step = model["next_step"]
    assert next_step["title"] == "Enter the prices you have"
    assert next_step["action_target"] == "budget"
    # Auto-generated drafts and bundles are never reported as traveller decisions.
    assert summary["decided"] == []


def test_generated_artefacts_are_never_listed_as_decisions() -> None:
    for mode in ("business", "leisure"):
        model = build_workspace_view_model(_payload(mode=mode, **_complete_frame()))
        assert model["user_summary"]["decided"] == [], mode


# --- Issue 1840: the header advances with what the traveller has done -----------------

_PRICED = {"priced_component_count": 2, "unpriced_component_count": 2}


def _submitted(summary: dict[str, Any]) -> dict[str, Any]:
    payload = _payload(**_complete_frame())
    payload["proposal_state"] = {"summary": summary}
    return payload


def test_priced_business_trip_is_told_to_submit_for_approval() -> None:
    model = build_workspace_view_model(_payload(**_complete_frame()), entered_prices=_PRICED)

    assert model["next_step"]["title"] == "Submit for approval"
    assert model["next_step"]["action_target"] == "approval"
    assert "Nothing has been planned" not in model["user_summary"]["headline"]
    assert model["business_summary"]["headline"] == (
        "Approval is not ready yet: the trip has not been submitted to the policy check."
    )


def test_blocked_submission_names_what_the_policy_flagged() -> None:
    model = build_workspace_view_model(
        _submitted(
            {
                "submission_outcome": "blocked_by_policy",
                "submission_blocking_codes": ["fare_evidence", "fare_comparison"],
                "follow_up": {
                    "failure_reasons": [
                        {
                            "code": "fare_evidence",
                            "message": "Screenshot or fare evidence must be attached.",
                        }
                    ]
                },
            }
        ),
        entered_prices=_PRICED,
    )

    step = model["next_step"]
    assert step["title"] == "Fix what the policy flagged"
    assert "Screenshot or fare evidence must be attached. (rule fare_evidence)" in step["summary"]
    assert "fare_comparison" in step["summary"]
    assert model["business_summary"]["approval_status"] == "needs_attention"
    assert model["business_summary"]["blockers"][0].startswith("Screenshot or fare evidence")


def test_compliant_trip_is_told_to_print_the_packet() -> None:
    model = build_workspace_view_model(
        _submitted({"submission_outcome": "succeeded", "evaluation_result_status": "compliant"}),
        entered_prices=_PRICED,
    )

    assert model["user_summary"]["headline"] == "This trip passed the travel policy check."
    assert model["next_step"]["title"] == "Print the approval packet"
    assert model["business_summary"]["approval_status"] == "approved"


def test_unreachable_policy_service_is_not_reported_as_a_verdict() -> None:
    model = build_workspace_view_model(
        _submitted({"submission_outcome": "failed"}), entered_prices=_PRICED
    )

    assert model["next_step"]["title"] == "Submit again"
    assert "did not reach the policy service" in model["next_step"]["summary"]


def test_unpriced_trip_explains_why_approval_is_not_ready() -> None:
    model = build_workspace_view_model(_payload(**_complete_frame()), entered_prices=None)

    assert model["business_summary"]["headline"] == (
        "Approval is not ready yet: no prices have been entered."
    )


def test_workspace_payload_passes_prices_to_the_header() -> None:
    """The seam the served payload uses must forward the price record, or none of the above
    reaches a traveller."""

    from trip_planner.app.services import workspace as workspace_service

    model = workspace_service._build_workspace_view_model(
        _payload(**_complete_frame()), trip_mode="business", entered_prices=_PRICED
    )
    assert model["next_step"]["title"] == "Submit for approval"
