"""Build a scenario search from saved scenario drafts — test fixture only.

Until issue 1827 the workspace served this to any trip whose inventory could not be
assembled, with invented timings (duration x 120 minutes, +45 for the "fallback", 1 / 2
transfers). Production no longer does; the policy-preview tests still need scenario rows
shaped from the saved-scenario fixtures, so the builder lives here, not in the product.
"""

from __future__ import annotations

from typing import Any

from trip_planner.app.services.workspace import _ordered_saved_scenarios
from trip_planner.persistence.models.trip import PersistedTrip

_BOOTSTRAP_SCENARIO_SCORE_BY_LABEL = {
    "baseline": 0.82,
    "fallback": 0.68,
}


def _bootstrap_route_sequence(record: PersistedTrip, *, label: str) -> list[str]:
    primary_regions = [region for region in record.primary_regions if region]
    if not primary_regions:
        primary_regions = [record.title]
    if label == "fallback":
        return [*primary_regions, "comparison-pass"]
    return primary_regions


def _bootstrap_scenario_metrics(
    record: PersistedTrip,
    *,
    label: str,
) -> tuple[float, int, int, dict[str, Any]]:
    duration_days = max(record.duration_days or 1, 1)
    base_minutes = 90 if record.mode == "leisure" else 120
    if label == "fallback":
        travel_minutes = duration_days * (base_minutes + 45)
        transfers = 2
    else:
        travel_minutes = duration_days * base_minutes
        transfers = 1
    return (
        _BOOTSTRAP_SCENARIO_SCORE_BY_LABEL.get(label, 0.6),
        travel_minutes,
        transfers,
        {
            "currency": "USD",
            "typical_amount": None,
            "nightly_typical_amount": None,
        },
    )


def build_saved_scenario_search(
    record: PersistedTrip,
    *,
    saved_scenarios: list[dict[str, Any]],
) -> dict[str, Any]:
    ordered = _ordered_saved_scenarios(saved_scenarios)
    scenario_rows: list[dict[str, Any]] = []
    source_refs = [f"session:{record.trip_id}"]
    for index, saved_scenario in enumerate(ordered, start=1):
        version = saved_scenario["versions"][0]
        label = version["label"]
        score, travel_minutes, transfers, estimated_total = _bootstrap_scenario_metrics(
            record,
            label=label,
        )
        route_sequence = _bootstrap_route_sequence(record, label=label)
        source_refs.extend(
            ref
            for ref in (
                version["snapshot_refs"].get("scenario_search_id"),
                version["snapshot_refs"].get("session_state_id"),
            )
            if ref
        )
        scenario_rows.append(
            {
                "scenario_id": saved_scenario["saved_scenario_id"],
                "label": label,
                "title": version["title"],
                "rank": index,
                "bundle_id": None,
                "source_result_id": version["version_id"],
                "score": score,
                "scenario_summary": {
                    "headline": version["summary"],
                    "scenario_kind": "fallback" if label == "fallback" else "primary",
                    "feasible": True,
                    "recommended_for_selection": label != "fallback",
                    "coherence_passed": True,
                    "estimated_total": estimated_total,
                    "total_travel_minutes": travel_minutes,
                    "total_transfer_count": transfers,
                    "route_sequence": route_sequence,
                    "notes": list(version.get("notes") or []),
                },
                "supporting_option_ids": list(version["snapshot_refs"].get("option_set_ids") or []),
                "objective_refs": [
                    ref for ref in [version["snapshot_refs"].get("objective_id")] if ref is not None
                ],
                "unresolved_tradeoffs": (
                    [
                        {
                            "tradeoff_id": f"tradeoff:{record.trip_id}:workspace-bootstrap",
                            "code": "broader_scope",
                            "summary": "Fallback stays available until live ranking can compare a broader planning pass.",
                            "severity": "info",
                        }
                    ]
                    if label == "fallback"
                    else []
                ),
            }
        )

    return {
        "search_id": f"scenario-search:{record.trip_id}:workspace-bootstrap",
        "trip_id": record.trip_id,
        "purpose": "workspace_bootstrap",
        "title": "Persisted workspace bootstrap comparison",
        "source_result_set_id": f"workspace-bootstrap:{record.trip_id}",
        "scenarios": scenario_rows,
        "explanation": [
            "Saved scenarios are bootstrapped from the persisted trip record until deeper planner ranking is available.",
            "The workspace comparison surface can render immediately without falling back to seeded trip fixtures.",
        ],
        "source_refs": list(dict.fromkeys(source_refs)),
    }
