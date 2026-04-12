from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from trip_planner.app.main import create_app
from trip_planner.persistence.db import get_session_factory, reset_database_state
from trip_planner.persistence.models.activity import (
    PersistedActivityLogEvent,
    PersistedPlannerAction,
)
from trip_planner.persistence.models.session import PersistedPlanningSessionState


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'planner.db'}")
    reset_database_state()
    app = create_app()

    with TestClient(app) as test_client:
        signup = test_client.post(
            "/api/auth/signup",
            json={
                "email": "planner@example.com",
                "password": "password123",
                "display_name": "Planner Owner",
            },
        )
        assert signup.status_code == 201
        yield test_client

    reset_database_state()


def _create_trip(client: TestClient) -> str:
    response = client.post(
        "/api/trips",
        json={
            "title": "Planner API kickoff",
            "summary": "Need a persisted planner session.",
            "mode": "leisure",
            "trip_frame": {
                "start_date": "2026-05-04",
                "end_date": "2026-05-06",
                "duration_days": 3,
                "primary_regions": ["Chicago"],
                "traveler_party": {
                    "kind": "solo",
                    "traveler_count": 1,
                    "notes": "Planner API test",
                },
            },
        },
    )
    assert response.status_code == 201
    return response.json()["trip"]["trip_id"]


def test_planner_session_endpoint_bootstraps_trip_scoped_session(client: TestClient) -> None:
    trip_id = _create_trip(client)

    response = client.get(f"/api/planner/{trip_id}/session")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trip_id"] == trip_id
    assert payload["session_state_id"] == f"session:{trip_id}"
    assert payload["conversation_id"] == f"planner-conversation:{trip_id}"
    assert payload["session"]["trip_id"] == trip_id
    assert payload["planner_panel_state"]["trip"]["trip_id"] == trip_id
    assert payload["available_tools"]
    assert payload["available_tools"][0]["tool_name"] == "read_workspace_state"
    assert payload["messages"] == []

    with get_session_factory()() as db_session:
        persisted = db_session.get(PersistedPlanningSessionState, f"session:{trip_id}")
        assert persisted is not None
        assert persisted.trip_id == trip_id


def test_planner_turn_persists_user_and_planner_messages(client: TestClient) -> None:
    trip_id = _create_trip(client)

    response = client.post(
        f"/api/planner/{trip_id}/turns",
        json={"message": "Help me decide what the planner should do next."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert [message["role"] for message in payload["messages"]] == ["user", "planner"]
    assert "Help me decide" in payload["messages"][0]["content"]
    assert payload["messages"][1]["refs"]
    assert payload["planner_panel_state"]["trip"]["trip_id"] == trip_id

    with get_session_factory()() as db_session:
        stored = db_session.scalars(
            select(PersistedPlannerAction)
            .where(PersistedPlannerAction.trip_id == trip_id)
            .order_by(PersistedPlannerAction.occurred_at.asc())
        ).all()
        assert [item.action_type for item in stored] == [
            "planner_user_turn",
            "planner_response",
        ]
        activity_events = db_session.scalars(
            select(PersistedActivityLogEvent)
            .where(PersistedActivityLogEvent.trip_id == trip_id)
            .order_by(PersistedActivityLogEvent.occurred_at.asc())
        ).all()
        assert [item.event_kind for item in activity_events] == [
            "planner_message",
            "planner_message",
        ]
        assert [item.actor for item in activity_events] == ["traveler", "planner"]


def test_planner_turn_executes_explicit_tool_calls(client: TestClient) -> None:
    trip_id = _create_trip(client)

    response = client.post(
        f"/api/planner/{trip_id}/turns",
        json={
            "message": "Use the planner tools to inspect budget state and set a first pass budget.",
            "tool_calls": [
                {"tool_name": "read_budget_state"},
                {
                    "tool_name": "update_budget_plan",
                    "arguments": {"total_amount": 1200, "title": "Planner first-pass budget"},
                },
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    planner_reply = payload["messages"][-1]
    assert len(planner_reply["tool_calls"]) == 2
    assert planner_reply["tool_calls"][0]["tool_name"] == "read_budget_state"
    assert planner_reply["tool_calls"][1]["tool_name"] == "update_budget_plan"
    assert planner_reply["tool_calls"][1]["mutates_state"] is True
    assert "Tool results:" in planner_reply["content"]

    with get_session_factory()() as db_session:
        stored = db_session.scalars(
            select(PersistedPlannerAction)
            .where(PersistedPlannerAction.trip_id == trip_id)
            .order_by(PersistedPlannerAction.occurred_at.asc())
        ).all()
        assert stored[-1].payload["tool_calls"][1]["tool_name"] == "update_budget_plan"
        session = db_session.get(PersistedPlanningSessionState, f"session:{trip_id}")
        assert session is not None
        assert session.active_budget_plan_id is not None


def test_planner_turn_rejects_invalid_tool_calls(client: TestClient) -> None:
    trip_id = _create_trip(client)

    response = client.post(
        f"/api/planner/{trip_id}/turns",
        json={
            "message": "Try an unsupported tool.",
            "tool_calls": [{"tool_name": "launch_booking_agent"}],
        },
    )

    assert response.status_code == 400
    assert "not supported" in response.json()["detail"]


def test_planner_turn_normalizes_lowercase_budget_currency(client: TestClient) -> None:
    trip_id = _create_trip(client)

    response = client.post(
        f"/api/planner/{trip_id}/turns",
        json={
            "message": "Set a lowercase-currency planner budget.",
            "tool_calls": [
                {
                    "tool_name": "update_budget_plan",
                    "arguments": {
                        "total_amount": 900,
                        "currency": "usd",
                    },
                }
            ],
        },
    )

    assert response.status_code == 200
    planner_reply = response.json()["messages"][-1]
    assert planner_reply["tool_calls"][0]["tool_name"] == "update_budget_plan"
    assert "USD 900.00" in planner_reply["tool_calls"][0]["summary"]

    with get_session_factory()() as db_session:
        stored = db_session.scalars(
            select(PersistedPlannerAction)
            .where(PersistedPlannerAction.trip_id == trip_id)
            .order_by(PersistedPlannerAction.occurred_at.asc())
        ).all()
        assert stored[-1].payload["tool_calls"][0]["summary"] == "Updated the workspace budget plan to USD 900.00."


def test_planner_resume_returns_prior_conversation_history(client: TestClient) -> None:
    trip_id = _create_trip(client)
    first_turn = client.post(
        f"/api/planner/{trip_id}/turns",
        json={"message": "Summarize my current planner context."},
    )
    assert first_turn.status_code == 200

    resumed = client.post(f"/api/planner/{trip_id}/resume")

    assert resumed.status_code == 200
    payload = resumed.json()
    assert payload["resumed_at"] is not None
    assert [message["role"] for message in payload["messages"]] == ["user", "planner"]
    assert payload["messages"][1]["content"].startswith("Planner API kickoff is using")
