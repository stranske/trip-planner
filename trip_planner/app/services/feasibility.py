from __future__ import annotations

from typing import Any

from trip_planner.itinerary import evaluate_bundle_feasibility
from trip_planner.options import InventoryBundle


def _humanize_reason(code: str) -> str:
    return code.replace("_", " ")


def _assessment_status(assessment: dict[str, Any]) -> str:
    if not assessment["feasible"] or assessment["blocking_reasons"]:
        return "critical"
    if assessment["recommended_for_ranking"]:
        return "positive"
    return "caution"


def build_feasibility_summary_payload(bundles: list[InventoryBundle]) -> dict[str, Any]:
    assessments: list[dict[str, Any]] = []

    for bundle in bundles:
        assessment = evaluate_bundle_feasibility(bundle).to_dict()
        assessment["bundle_title"] = bundle.title
        assessment["bundle_context"] = bundle.bundle_context
        assessment["status"] = _assessment_status(assessment)
        assessments.append(assessment)

    recommended_bundle_count = sum(
        1 for assessment in assessments if assessment["recommended_for_ranking"]
    )
    blocking_bundle_count = sum(
        1 for assessment in assessments if assessment["status"] == "critical"
    )
    attention_bundle_count = sum(
        1 for assessment in assessments if assessment["status"] == "caution"
    )

    notes = (
        [
            "Feasibility outputs stay explicit so later ranking and route-search services can consume move costs, timing conflicts, and route warnings without rebuilding them.",
        ]
        if assessments
        else [
            "No inventory bundles are available yet, so feasibility and move-cost outputs have not been generated.",
        ]
    )

    return {
        "assessment_count": len(assessments),
        "recommended_bundle_count": recommended_bundle_count,
        "blocking_bundle_count": blocking_bundle_count,
        "attention_bundle_count": attention_bundle_count,
        "assessments": assessments,
        "notes": notes,
    }


def _move_cost_highlight(assessment: dict[str, Any]) -> str | None:
    move_costs = assessment.get("move_costs", [])
    if not move_costs:
        return None

    highest_friction = max(move_costs, key=lambda item: item["friction_penalty"])
    reasons = highest_friction["blocking_reasons"] or highest_friction["warnings"]
    if reasons:
        return (
            f"Move cost: {_humanize_reason(reasons[0]).capitalize()} "
            f"on {highest_friction['origin_id']} -> {highest_friction['destination_id']}."
        )
    return (
        f"Move cost: {highest_friction['travel_minutes']} travel minutes and "
        f"{highest_friction['transfer_count']} transfer(s) on the highest-friction leg."
    )


def _assessment_highlights(assessment: dict[str, Any]) -> list[str]:
    highlights: list[str] = []

    for reason in assessment.get("blocking_reasons", [])[:2]:
        highlights.append(f"Blocking: {_humanize_reason(reason).capitalize()}.")
    for conflict in assessment.get("timing_conflicts", [])[:2]:
        highlights.append(f"Timing: {conflict['summary']}")
    for warning in assessment.get("route_warnings", [])[:1]:
        highlights.append(f"Route: {warning['summary']}")

    move_cost_highlight = _move_cost_highlight(assessment)
    if move_cost_highlight:
        highlights.append(move_cost_highlight)

    if assessment.get("missing_data_fields"):
        highlights.append(
            f"Missing data: {len(assessment['missing_data_fields'])} field(s) still need confirmation."
        )

    if not highlights:
        highlights.append("No blocking transitions or timing conflicts are currently surfaced.")

    return highlights[:4]


def build_feasibility_planner_outputs(
    *,
    trip_id: str,
    feasibility_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    assessments = feasibility_summary["assessments"]
    if not assessments:
        return []

    outputs: list[dict[str, Any]] = [
        {
            "output_id": f"output:{trip_id}:feasibility-summary",
            "title": "Feasibility summary",
            "body": (
                f"{feasibility_summary['assessment_count']} bundle(s) evaluated: "
                f"{feasibility_summary['recommended_bundle_count']} ready for ranking, "
                f"{feasibility_summary['attention_bundle_count']} need planner attention, and "
                f"{feasibility_summary['blocking_bundle_count']} are currently blocked."
            ),
            "tags": ["feasibility", "move-cost", "workspace-runtime"],
            "status": (
                "critical"
                if feasibility_summary["blocking_bundle_count"]
                else "caution"
                if feasibility_summary["attention_bundle_count"]
                else "positive"
            ),
            "highlights": list(feasibility_summary["notes"]),
        }
    ]

    for assessment in assessments:
        outputs.append(
            {
                "output_id": f"output:{trip_id}:feasibility:{assessment['bundle_id']}",
                "title": f"{assessment['bundle_title']} feasibility",
                "body": (
                    (
                        "Blocked until feasibility conflicts are resolved. "
                        if assessment["status"] == "critical"
                        else "Feasible but not yet ready for ranking. "
                        if assessment["status"] == "caution"
                        else "Ready for ranking with current feasibility signals. "
                    )
                    + (
                        f"{assessment['total_travel_minutes']} travel minutes, "
                        f"{assessment['total_transfer_count']} transfer(s), "
                        f"friction penalty {assessment['friction_penalty_total']:.2f}."
                    )
                ),
                "tags": [
                    "feasibility",
                    assessment["bundle_context"],
                    "ranking-ready"
                    if assessment["recommended_for_ranking"]
                    else "needs-attention",
                ],
                "status": assessment["status"],
                "highlights": _assessment_highlights(assessment),
            }
        )

    return outputs
