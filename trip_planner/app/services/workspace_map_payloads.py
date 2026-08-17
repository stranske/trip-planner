"""Runtime map payload builders for workspace scenario comparison rows."""

from __future__ import annotations

from typing import Any


def _humanize_route_stop(stop: str) -> str:
    return (
        stop.replace("dest-city-", "")
        .replace("dest-", "")
        .replace("city-", "")
        .replace("_", " ")
        .replace("-", " ")
        .strip()
        .title()
    )


def _map_coordinate_for_route_index(index: int, route_length: int) -> dict[str, float]:
    if route_length <= 1:
        return {"x": 0.5, "y": 0.5}

    progress = index / (route_length - 1)
    wave = -1 if index % 2 == 0 else 1
    return {
        "x": round(0.12 + progress * 0.76, 4),
        "y": round(0.52 + wave * 0.18, 4),
    }


def _build_runtime_map_place_markers(
    route_sequence: list[str],
    *,
    source_refs: list[str],
) -> list[dict[str, Any]]:
    stop_count = len([stop for stop in route_sequence if stop])
    return [
        {
            "id": f"route-stop:{index + 1}",
            "source_id": stop,
            "label": _humanize_route_stop(stop),
            "description": (
                f"Route stop {index + 1} of {stop_count}, sourced from the ranked scenario "
                "route sequence."
            ),
            "source_refs": list(source_refs),
            "route_index": index,
            **_map_coordinate_for_route_index(index, len(route_sequence)),
        }
        for index, stop in enumerate(route_sequence)
        if stop
    ]


def _build_runtime_map_route_geometry(
    place_markers: list[dict[str, Any]],
    *,
    route_warning: str | None,
    total_travel_minutes: int,
    feasible: bool,
    source_refs: list[str],
    total_distance_km: float | None = None,
) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    segment_count = max(1, len(place_markers) - 1)
    per_segment_minutes = max(0, round(total_travel_minutes / segment_count))
    per_segment_distance_km = (
        round(total_distance_km / segment_count, 1)
        if total_distance_km is not None and total_distance_km > 0
        else None
    )
    distance_available = per_segment_distance_km is not None
    for index, marker in enumerate(place_markers[:-1]):
        next_marker = place_markers[index + 1]
        segments.append(
            {
                "id": f"route-segment:{index + 1}",
                "from_marker_id": marker["id"],
                "to_marker_id": next_marker["id"],
                "from_label": marker["label"],
                "to_label": next_marker["label"],
                "x1": marker["x"],
                "y1": marker["y"],
                "x2": next_marker["x"],
                "y2": next_marker["y"],
                "warning": route_warning if index == 0 else None,
                "duration_minutes": per_segment_minutes,
                "distance_km": per_segment_distance_km,
                "confidence": "medium" if feasible else "low",
                "provider_distance_available": distance_available,
                "distance_verification_state": (
                    "scenario_distance_available"
                    if distance_available
                    else "duration_estimate_only"
                ),
                "distance_source": "scenario_summary" if distance_available else None,
                "source_refs": list(source_refs),
                "unavailable_reason": (
                    None
                    if distance_available
                    else "Provider distance is not available; duration is estimated from ranked scenario timing."
                ),
            }
        )
    return segments


def build_runtime_map_view_payload(
    *,
    scenario: dict[str, Any],
    summary: dict[str, Any],
    route_sequence: list[str],
) -> dict[str, Any]:
    confidence_level = "high" if summary.get("feasible", False) else "medium"
    route_warning = None if summary.get("feasible", False) else "Scenario feasibility needs review."
    source_refs = [
        ref
        for ref in [
            scenario.get("source_result_id"),
            *list(scenario.get("objective_refs") or []),
        ]
        if ref
    ]
    place_markers = _build_runtime_map_place_markers(route_sequence, source_refs=source_refs)
    rough_route_geometry = _build_runtime_map_route_geometry(
        place_markers,
        route_warning=route_warning,
        total_travel_minutes=int(summary.get("total_travel_minutes") or 0),
        total_distance_km=summary.get("total_distance_km"),
        feasible=bool(summary.get("feasible", False)),
        source_refs=source_refs,
    )
    return {
        "active_scope": "regional",
        "active_route_option_id": scenario["scenario_id"],
        "selected_segment_id": rough_route_geometry[0]["id"] if rough_route_geometry else None,
        "place_markers": place_markers,
        "rough_route_geometry": rough_route_geometry,
        "confidence": {
            "level": confidence_level,
            "summary": (
                "This route outline is drawn from ranked scenario data."
                if confidence_level == "high"
                else "This route outline is approximate while feasibility is still settling."
            ),
        },
    }


def build_runtime_map_diagnostics_payload(
    *,
    scenario: dict[str, Any],
    summary: dict[str, Any],
    route_sequence: list[str],
) -> dict[str, Any]:
    has_route = len(route_sequence) > 1
    return {
        "provider": {
            "kind": "fallback",
            "status": "sparse-route" if not has_route else "fallback",
            "details": "Route geometry is synthesized from scenario route_sequence.",
        },
        "route_state": "ready" if has_route else "sparse",
        "route_warning": None if summary.get("feasible", False) else "scenario_not_feasible",
        "source_result_id": scenario["source_result_id"],
        "objective_refs": list(scenario.get("objective_refs") or []),
    }
