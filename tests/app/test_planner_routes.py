from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from trip_planner.app.main import create_app
from trip_planner.app.services.planner import set_planner_chat_model_factory_for_tests
from trip_planner.persistence.db import get_session_factory, reset_database_state
from trip_planner.persistence.models.activity import (
    PersistedActivityLogEvent,
    PersistedPlannerAction,
)
from trip_planner.persistence.models.planner_memory import (
    PersistedPlannerCheckpoint,
    PersistedPlannerMemoryArtifact,
)
from trip_planner.persistence.models.session import PersistedPlanningSessionState


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'planner.db'}")
    monkeypatch.delenv("TRIP_PLANNER_PLANNER_MODEL_PROVIDER", raising=False)
    monkeypatch.delenv("TRIP_PLANNER_PLANNER_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    set_planner_chat_model_factory_for_tests(None)
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

    set_planner_chat_model_factory_for_tests(None)
    reset_database_state()


class FakePlannerChatModel:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.requests: list[dict[str, Any]] = []

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.requests.append(payload)
        return self.response


class FailingPlannerChatModel:
    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        del payload
        raise RuntimeError("provider timeout")


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
    assert payload["planner_memory"]["current_checkpoint_id"] is None
    assert payload["runtime"]["mode"] == "fallback"
    assert payload["runtime"]["fallback_reason"] == "planner_model_not_configured"
    assert payload["available_tools"]
    assert payload["available_tools"][0]["tool_name"] == "read_workspace_state"
    assert payload["messages"] == []

    with get_session_factory()() as db_session:
        persisted = db_session.get(PersistedPlanningSessionState, f"session:{trip_id}")
        assert persisted is not None
        assert persisted.trip_id == trip_id


def test_planner_session_treats_blank_model_key_as_unconfigured(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trip_id = _create_trip(client)
    monkeypatch.setenv("TRIP_PLANNER_PLANNER_MODEL_PROVIDER", "openai")
    monkeypatch.setenv("TRIP_PLANNER_PLANNER_MODEL", "gpt-test")
    monkeypatch.setenv("OPENAI_API_KEY", "   ")

    response = client.get(f"/api/planner/{trip_id}/session")

    assert response.status_code == 200
    runtime = response.json()["runtime"]
    assert runtime["mode"] == "fallback"
    assert runtime["fallback_reason"] == "openai_api_key_missing"


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
    assert "Deterministic planner fallback is active" in payload["messages"][1]["content"]
    assert payload["messages"][1]["refs"]
    assert payload["planner_panel_state"]["trip"]["trip_id"] == trip_id
    assert payload["planner_memory"]["current_checkpoint_id"].startswith("planner-chk:")
    assert payload["planner_memory"]["artifacts"][0]["title"] == "Planner checkpoint 1"

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
        checkpoint_id = payload["planner_memory"]["current_checkpoint_id"]
        checkpoint = db_session.get(PersistedPlannerCheckpoint, checkpoint_id)
        assert checkpoint is not None
        assert len(checkpoint_id) <= 96
        artifact = db_session.get(
            PersistedPlannerMemoryArtifact,
            payload["planner_memory"]["artifacts"][0]["memory_artifact_id"],
        )
        assert artifact is not None
        assert artifact.memory_artifact_id.startswith("planner-mem:")
        assert artifact.checkpoint_id == checkpoint.checkpoint_id


def test_planner_turn_uses_configured_model_and_persists_requested_tool_trace(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trip_id = _create_trip(client)
    fake_model = FakePlannerChatModel(
        {
            "content": "I need to compare the current workspace state before recommending next steps.",
            "tool_calls": [{"tool_name": "read_workspace_state", "arguments": {}}],
        }
    )
    monkeypatch.setenv("TRIP_PLANNER_PLANNER_MODEL_PROVIDER", "openai")
    monkeypatch.setenv("TRIP_PLANNER_PLANNER_MODEL", "fake-planner-model")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-test-key")
    set_planner_chat_model_factory_for_tests(lambda _: fake_model)

    response = client.post(
        f"/api/planner/{trip_id}/turns",
        json={"message": "Compare my options and tell me what to revise."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["runtime"]["mode"] == "model"
    assert payload["runtime"]["model"] == "fake-planner-model"
    planner_reply = payload["messages"][-1]
    assert planner_reply["content"].startswith("I need to compare")
    assert planner_reply["tool_calls"][0]["tool_name"] == "read_workspace_state"
    assert planner_reply["tool_calls"][0]["status"] == "completed"
    assert fake_model.requests[0]["available_tools"][0]["tool_name"] == "read_workspace_state"
    runtime_context = fake_model.requests[0]["runtime_context"]
    assert isinstance(runtime_context, dict)
    assert runtime_context["trip"]["trip_id"] == trip_id
    assert runtime_context["context_readiness"]["status"] == "ready"
    assert runtime_context["autonomy_preferences"]["interaction_state"]["initiative_level"] == "balanced"
    assert runtime_context["budget_state"]["summary"]["currency"] == "USD"
    assert "policy_state" in runtime_context
    assert "proposal_state" in runtime_context
    assert "recent_activity" in runtime_context

    with get_session_factory()() as db_session:
        stored = db_session.scalars(
            select(PersistedPlannerAction)
            .where(PersistedPlannerAction.trip_id == trip_id)
            .order_by(PersistedPlannerAction.occurred_at.asc())
        ).all()
        assert stored[-1].payload["tool_calls"][0]["summary"] == "Read the current planner panel workspace state."
        assert stored[-1].payload["selected_planning_mode"] == "leisure"
        assert stored[-1].payload["runtime_mode"] == "model"
        checkpoint = db_session.get(
            PersistedPlannerCheckpoint,
            payload["planner_memory"]["current_checkpoint_id"],
        )
        assert checkpoint is not None
        assert checkpoint.metadata_payload["tool_call_count"] == 1
        assert checkpoint.metadata_payload["selected_planning_mode"] == "leisure"


def test_planner_turn_records_model_tool_errors_without_fabricating_success(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trip_id = _create_trip(client)
    monkeypatch.setenv("TRIP_PLANNER_PLANNER_MODEL_PROVIDER", "openai")
    monkeypatch.setenv("TRIP_PLANNER_PLANNER_MODEL", "fake-planner-model")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-test-key")
    set_planner_chat_model_factory_for_tests(
        lambda _: FakePlannerChatModel(
            {
                "content": "I tried to use a tool that is outside the app boundary.",
                "tool_calls": [{"tool_name": "launch_booking_agent", "arguments": {}}],
            }
        )
    )

    response = client.post(
        f"/api/planner/{trip_id}/turns",
        json={"message": "Book the lead option for me."},
    )

    assert response.status_code == 200
    planner_reply = response.json()["messages"][-1]
    assert planner_reply["tool_calls"][0]["tool_name"] == "launch_booking_agent"
    assert planner_reply["tool_calls"][0]["status"] == "error"
    assert "not supported" in planner_reply["tool_calls"][0]["summary"]


def test_planner_turn_records_malformed_model_tool_arguments_as_visible_error(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trip_id = _create_trip(client)
    monkeypatch.setenv("TRIP_PLANNER_PLANNER_MODEL_PROVIDER", "openai")
    monkeypatch.setenv("TRIP_PLANNER_PLANNER_MODEL", "fake-planner-model")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-test-key")
    set_planner_chat_model_factory_for_tests(
        lambda _: FakePlannerChatModel(
            {
                "content": "The budget tool received malformed arguments.",
                "tool_calls": [{"tool_name": "update_budget_plan", "arguments": "not-a-dict"}],
            }
        )
    )

    response = client.post(
        f"/api/planner/{trip_id}/turns",
        json={"message": "Set a budget from malformed model output."},
    )

    assert response.status_code == 200
    planner_reply = response.json()["messages"][-1]
    assert planner_reply["tool_calls"][0]["tool_name"] == "update_budget_plan"
    assert planner_reply["tool_calls"][0]["status"] == "error"
    assert "dictionary update sequence" in planner_reply["tool_calls"][0]["summary"]


def test_planner_turn_records_model_provider_failure_as_visible_error(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trip_id = _create_trip(client)
    monkeypatch.setenv("TRIP_PLANNER_PLANNER_MODEL_PROVIDER", "openai")
    monkeypatch.setenv("TRIP_PLANNER_PLANNER_MODEL", "fake-planner-model")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-test-key")
    set_planner_chat_model_factory_for_tests(lambda _: FailingPlannerChatModel())

    response = client.post(
        f"/api/planner/{trip_id}/turns",
        json={"message": "Try the configured model path."},
    )

    assert response.status_code == 200
    planner_reply = response.json()["messages"][-1]
    assert "Planner model runtime failed" in planner_reply["content"]
    assert planner_reply["tool_calls"][0]["tool_name"] == "planner_model"
    assert planner_reply["tool_calls"][0]["status"] == "error"
    assert planner_reply["tool_calls"][0]["summary"] == "provider timeout"


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
    assert payload["planner_memory"]["artifacts"][0]["title"] == "Planner checkpoint 1"


def test_planner_resume_regenerates_memory_from_raw_transcript(client: TestClient) -> None:
    trip_id = _create_trip(client)
    first_turn = client.post(
        f"/api/planner/{trip_id}/turns",
        json={"message": "Keep the baseline narrow and summarize the current direction."},
    )
    assert first_turn.status_code == 200

    with get_session_factory()() as db_session:
        db_session.execute(
            delete(PersistedPlannerMemoryArtifact).where(
                PersistedPlannerMemoryArtifact.trip_id == trip_id
            )
        )
        db_session.execute(
            delete(PersistedPlannerCheckpoint).where(
                PersistedPlannerCheckpoint.trip_id == trip_id
            )
        )
        session = db_session.get(PersistedPlanningSessionState, f"session:{trip_id}")
        assert session is not None
        session.current_checkpoint_id = None
        db_session.commit()

    resumed = client.post(f"/api/planner/{trip_id}/resume")

    assert resumed.status_code == 200
    payload = resumed.json()
    assert payload["planner_memory"]["current_checkpoint_id"].startswith("planner-chk:")
    assert payload["planner_memory"]["artifacts"][0]["summary"].startswith("Turn 1 checkpoint")
