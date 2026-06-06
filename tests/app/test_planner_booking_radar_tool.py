from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from trip_planner.app.services import planner_tools
from trip_planner.app.services.auth import AuthenticatedUser
from trip_planner.app.services.planner_tools import execute_planner_tool_call, list_planner_tools


def _workspace_payload() -> dict[str, Any]:
    return {
        "session": {"session_state_id": "session-1"},
        "trip_record": {"trip": {"trip_id": "trip-swiss-spain", "title": "Alps to Andalucia"}},
        "planner_panel_state": {"trip": {"trip_id": "trip-swiss-spain"}},
        "inventory_summary": {
            "runtime_state": {"status": "ready"},
            "bundles": [
                {
                    "bundle_id": "bundle-rail-culture",
                    "title": "Rail plus Granada anchor",
                    "transport_options": [
                        {
                            "option_id": "transport-glacier",
                            "mode": "rail",
                            "operator": "Glacier Express",
                            "route": "Zermatt to St Moritz",
                        }
                    ],
                    "activity_options": [
                        {
                            "option_id": "act-alhambra",
                            "name": "Alhambra Nasrid Palaces",
                            "activity_kind": "sight",
                        }
                    ],
                }
            ],
        },
    }


def test_read_booking_radar_tool_registered_and_dispatches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert any(tool["tool_name"] == "read_booking_radar" for tool in list_planner_tools())

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
        trip_id="trip-swiss-spain",
        tool_name="read_booking_radar",
        arguments={"appetite": "anchored"},
    ).to_dict()

    assert result["status"] == "completed"
    assert result["output"]["radar_state"] == "ready"
    assert result["output"]["flag_count"] == 2
    assert {flag["item"] for flag in result["output"]["flags"]} == {
        "Glacier Express seat reservation",
        "Alhambra Nasrid Palaces timed entry",
    }
