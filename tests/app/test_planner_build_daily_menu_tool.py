from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from trip_planner.app.services import planner_tools
from trip_planner.app.services.auth import AuthenticatedUser
from trip_planner.app.services.planner_tools import execute_planner_tool_call, list_planner_tools


def _activity(
    option_id: str,
    name: str,
    *,
    source_id: str,
    duration_minutes: int,
    overall_signal: float,
) -> dict[str, Any]:
    return {
        "option_id": option_id,
        "name": name,
        "activity_kind": "district",
        "destination_id": "dest-kyoto",
        "place_id": f"place-{option_id}",
        "category": {"primary": "district", "secondary": [], "tags": []},
        "timing_summary": {"duration_minutes": duration_minutes},
        "significance_summary": {"overall_signal": overall_signal},
        "quality_summary": {"overall_signal": overall_signal},
        "value_summary": {"overall_signal": overall_signal, "time_value_signal": overall_signal},
        "fit_summary": {"overall_signal": overall_signal},
        "source_refs": [{"source_id": source_id, "trust_snapshot": {"commerciality": 0.2}}],
        "summary": f"{name} is a compact candidate for the day menu.",
    }


def _workspace_payload() -> dict[str, Any]:
    return {
        "session": {"session_state_id": "session-1"},
        "inventory_summary": {
            "runtime_state": {"status": "ready", "commerciality_preference": 0.25},
            "bundles": [
                {
                    "bundle_id": "bundle-kyoto-activities",
                    "title": "Kyoto activity bundle",
                    "quality_value_fit": {
                        "quality_signal": 0.8,
                        "value_signal": 0.75,
                        "fit_signal": 0.8,
                    },
                    "activity_options": [
                        _activity(
                            "act-gion",
                            "Gion district stroll",
                            source_id="editorial-guide",
                            duration_minutes=45,
                            overall_signal=0.82,
                        ),
                        _activity(
                            "act-tea",
                            "Reserved tea ceremony",
                            source_id="booking-partner",
                            duration_minutes=60,
                            overall_signal=0.78,
                        ),
                    ],
                    "source_records": [
                        {
                            "source_id": "editorial-guide",
                            "provider_name": "Editorial Guide",
                            "display_name": "Editorial Guide",
                            "category": "editorial",
                            "trust_signals": {"commerciality": 0.1},
                        },
                        {
                            "source_id": "booking-partner",
                            "provider_name": "Booking Partner",
                            "display_name": "Booking Partner",
                            "category": "commercial_inventory",
                            "trust_signals": {"commerciality": 0.9},
                        },
                    ],
                }
            ],
        },
    }


def test_build_daily_menu_tool_registered_and_dispatches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert any(tool["tool_name"] == "build_daily_menu" for tool in list_planner_tools())

    monkeypatch.setattr(
        planner_tools,
        "get_workspace_payload",
        lambda *args, **kwargs: _workspace_payload(),
    )
    db_session = SimpleNamespace(info={})
    user = AuthenticatedUser(
        user_id="user-1",
        email="planner@example.com",
        display_name="Planner",
    )

    result = execute_planner_tool_call(
        db_session,  # type: ignore[arg-type]
        user=user,
        trip_id="trip-kyoto",
        tool_name="build_daily_menu",
        arguments={"time_budget_minutes": 120, "commercial_target": 0.2},
    ).to_dict()

    assert result["status"] == "completed"
    assert result["output"]["menu_state"] == "ready"
    assert result["output"]["selected_stops"]
    assert result["output"]["selected_stops"][0]["stop_id"] == "act-gion"
