import json
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
from trip_planner.sources import CONFIDENCE_LABELS


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv(
        "TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'planner.db'}"
    )
    monkeypatch.delenv("TRIP_PLANNER_PLANNER_MODEL_PROVIDER", raising=False)
    monkeypatch.delenv("TRIP_PLANNER_PLANNER_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    monkeypatch.delenv("LANGCHAIN_PROJECT", raising=False)
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    monkeypatch.delenv("TRIP_PLANNER_LANGSMITH_FLEET_PATH", raising=False)
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


def _create_business_trip(client: TestClient) -> str:
    response = client.post(
        "/api/trips",
        json={
            "title": "Planner API business kickoff",
            "summary": "Need policy and proposal-backed planner context.",
            "mode": "business",
            "trip_frame": {
                "start_date": "2026-05-04",
                "end_date": "2026-05-06",
                "duration_days": 3,
                "primary_regions": ["Chicago"],
                "traveler_party": {
                    "kind": "solo",
                    "traveler_count": 1,
                    "notes": "Planner business API test",
                },
            },
        },
    )
    assert response.status_code == 201
    return response.json()["trip"]["trip_id"]


def test_planner_session_endpoint_bootstraps_trip_scoped_session(
    client: TestClient,
) -> None:
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


def test_planner_session_reports_model_runtime_when_configured(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trip_id = _create_trip(client)
    monkeypatch.setenv("TRIP_PLANNER_PLANNER_MODEL_PROVIDER", "openai")
    monkeypatch.setenv("TRIP_PLANNER_PLANNER_MODEL", "fake-planner-model")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-test-key")

    response = client.get(f"/api/planner/{trip_id}/session")

    assert response.status_code == 200
    runtime = response.json()["runtime"]
    assert runtime["mode"] == "model"
    assert runtime["provider"] == "openai"
    assert runtime["model"] == "fake-planner-model"


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
    assert "fallback" not in payload["messages"][1]["content"].lower()
    assert payload["messages"][1]["turn_metadata"]["plan_maturity"] == "partial_plan"
    planner_blocks = payload["messages"][1]["structured_blocks"]
    planner_block_kinds = {block["kind"] for block in planner_blocks}
    assert {
        "visible_sections",
        "summary",
        "question",
        "assumption",
        "diagnostic",
    }.issubset(planner_block_kinds)
    assert (
        next(block for block in planner_blocks if block["kind"] == "diagnostic")[
            "hidden"
        ]
        is True
    )
    assert payload["messages"][1]["refs"]
    assert payload["planner_panel_state"]["trip"]["trip_id"] == trip_id
    assert payload["planner_memory"]["current_checkpoint_id"].startswith("planner-chk:")
    assert payload["planner_memory"]["artifacts"][0]["title"] == "Planner checkpoint 1"
    checkpoint_payload = payload["planner_memory"]["checkpoints"][0]["metadata_payload"]
    assert checkpoint_payload["plan_maturity"] == "partial_plan"
    assert checkpoint_payload["task_class"] == "first_turn_triage"

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
        assert stored[-1].payload["turn_metadata"]["task_class"] == "first_turn_triage"
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
        assert checkpoint.metadata_payload["plan_maturity"] == "partial_plan"
        assert checkpoint.metadata_payload["task_class"] == "first_turn_triage"
        artifact = db_session.get(
            PersistedPlannerMemoryArtifact,
            payload["planner_memory"]["artifacts"][0]["memory_artifact_id"],
        )
        assert artifact is not None
        assert artifact.memory_artifact_id.startswith("planner-mem:")
        assert artifact.checkpoint_id == checkpoint.checkpoint_id
        assert "partial_plan" not in artifact.detail
        assert "first_turn_triage" not in artifact.detail


def test_planner_turn_summarizes_scattered_traveler_input(client: TestClient) -> None:
    trip_id = _create_trip(client)

    response = client.post(
        f"/api/planner/{trip_id}/turns",
        json={
            "message": (
                "We're considering Sweden and Norway in August for 12 days. "
                "Budget matters and we prefer scenic trains, low transfer days, and food markets. "
                "Maybe Bergen, but I'm not sure. "
                "Also remind me to check passport renewal later."
            )
        },
    )

    assert response.status_code == 200
    user_message = response.json()["messages"][0]
    summary_block = user_message["structured_blocks"][0]
    assert summary_block["kind"] == "traveler_input_summary"
    assert "Traveler input summary" == summary_block["title"]
    assert any("Destinations:" in item for item in summary_block["items"])
    assert any("Timing:" in item for item in summary_block["items"])
    assert any("Constraints:" in item for item in summary_block["items"])
    assert any("Preferences:" in item for item in summary_block["items"])
    assert any("Open questions:" in item for item in summary_block["items"])
    assert any("Notes to remember:" in item for item in summary_block["items"])
    assert "Sweden" in summary_block["metadata"]["destinations"]
    assert "Norway" in summary_block["metadata"]["destinations"]
    assert "Bergen" in summary_block["metadata"]["destinations"]
    assert "Maybe Bergen" not in summary_block["metadata"]["destinations"]
    assert "Not" not in summary_block["metadata"]["destinations"]
    assert "august" in summary_block["metadata"]["dates"]


@pytest.mark.parametrize(
    ("message", "expected_maturity", "expected_task"),
    [
        (
            "We want five days in Kyoto in May with a moderate budget and low-transfer hotels.",
            "coherent_plan",
            "planning_synthesis",
        ),
        (
            "We have June dates and a hotel budget but no destination yet.",
            "partial_plan",
            "first_turn_triage",
        ),
        (
            "Maybe Japan with good food",
            "partial_plan",
            "first_turn_triage",
        ),
        (
            "Plan a trip",
            "open_ended",
            "first_turn_triage",
        ),
        (
            (
                "Compare options for a business trip with approval, budget, hotel, train, "
                "walking, family, food, transfer, and accessibility constraints?"
            ),
            "overloaded_constraints",
            "planning_synthesis",
        ),
    ],
)
def test_planner_turn_records_adaptive_triage_metadata(
    client: TestClient,
    message: str,
    expected_maturity: str,
    expected_task: str,
) -> None:
    trip_id = _create_trip(client)

    response = client.post(f"/api/planner/{trip_id}/turns", json={"message": message})

    assert response.status_code == 200
    planner_reply = response.json()["messages"][-1]
    metadata = planner_reply["turn_metadata"]
    assert metadata["plan_maturity"] == expected_maturity
    assert metadata["task_class"] == expected_task
    assert metadata["visible_response_blocks"]
    assert metadata["debug_routing_details"]["runtime_mode"] == "fallback"
    structured_kinds = {block["kind"] for block in planner_reply["structured_blocks"]}
    assert "summary" in structured_kinds
    assert "diagnostic" in structured_kinds
    assert "visible_sections" in structured_kinds
    assert (
        next(
            block
            for block in planner_reply["structured_blocks"]
            if block["kind"] == "diagnostic"
        )["hidden"]
        is True
    )
    visible_content = planner_reply["content"].lower()
    assert "model routing" not in visible_content
    assert "provider" not in visible_content
    assert "fallback" not in visible_content


def test_planner_turn_records_effort_class_and_provider_state_on_fallback(
    client: TestClient,
) -> None:
    trip_id = _create_trip(client)

    response = client.post(
        f"/api/planner/{trip_id}/turns",
        json={"message": "We want five days in Kyoto in May with a moderate budget."},
    )

    assert response.status_code == 200
    planner_reply = response.json()["messages"][-1]
    metadata = planner_reply["turn_metadata"]
    # Task class is unchanged (planning_synthesis); effort class is added; provider
    # state and fallback_reason are recorded alongside without leaking into traveler copy.
    assert metadata["task_class"] == "planning_synthesis"
    assert metadata["effort_class"] == "deep"
    assert metadata["base_effort_class"] == "deep"
    assert metadata["provider_state"] == "fallback"
    assert metadata["fallback_reason"] == "planner_model_not_configured"
    assert metadata["selected_planning_mode"] == "collaborative"
    assert metadata["debug_routing_details"]["routing_reasoning"]
    visible_content = planner_reply["content"].lower()
    assert "effort" not in visible_content
    assert "deep" not in visible_content
    assert "fast" not in visible_content


def test_quick_acknowledgement_routes_to_fast_path(client: TestClient) -> None:
    trip_id = _create_trip(client)

    response = client.post(
        f"/api/planner/{trip_id}/turns",
        json={"message": "Thanks!"},
    )

    assert response.status_code == 200
    metadata = response.json()["messages"][-1]["turn_metadata"]
    assert metadata["task_class"] == "quick_acknowledgement"
    assert metadata["effort_class"] == "fast"


def test_note_capture_message_routes_to_fast_path(client: TestClient) -> None:
    trip_id = _create_trip(client)

    response = client.post(
        f"/api/planner/{trip_id}/turns",
        json={"message": "Remember this for later: passport expiration is in March"},
    )

    assert response.status_code == 200
    metadata = response.json()["messages"][-1]["turn_metadata"]
    assert metadata["task_class"] == "note_capture"
    assert metadata["effort_class"] == "fast"


def test_focus_switch_message_routes_to_fast_path(client: TestClient) -> None:
    trip_id = _create_trip(client)

    response = client.post(
        f"/api/planner/{trip_id}/turns",
        json={"message": "Let's switch to lodging for now"},
    )

    assert response.status_code == 200
    metadata = response.json()["messages"][-1]["turn_metadata"]
    assert metadata["task_class"] == "focus_switch"
    assert metadata["effort_class"] == "fast"


def test_delegated_planning_mode_biases_standard_band_to_deep(
    client: TestClient,
) -> None:
    trip_id = _create_trip(client)

    mode_response = client.put(
        f"/api/workspace/{trip_id}/planning-mode",
        json={"planning_mode": "delegated"},
    )
    assert mode_response.status_code == 200, mode_response.text

    response = client.post(
        f"/api/planner/{trip_id}/turns",
        json={"message": "Maybe Japan with good food"},
    )

    assert response.status_code == 200
    metadata = response.json()["messages"][-1]["turn_metadata"]
    # Base task class is first_turn_triage (standard band); delegated mode bumps
    # it to deep without changing the task class itself.
    assert metadata["task_class"] == "first_turn_triage"
    assert metadata["base_effort_class"] == "standard"
    assert metadata["effort_class"] == "deep"
    assert metadata["selected_planning_mode"] == "delegated"


def test_delegated_planning_mode_does_not_override_fast_task(
    client: TestClient,
) -> None:
    trip_id = _create_trip(client)

    mode_response = client.put(
        f"/api/workspace/{trip_id}/planning-mode",
        json={"planning_mode": "delegated"},
    )
    assert mode_response.status_code == 200, mode_response.text

    response = client.post(
        f"/api/planner/{trip_id}/turns",
        json={"message": "thanks"},
    )

    assert response.status_code == 200
    metadata = response.json()["messages"][-1]["turn_metadata"]
    # Quick acknowledgement is a fast-pinned task; delegated mode must not override it.
    assert metadata["task_class"] == "quick_acknowledgement"
    assert metadata["effort_class"] == "fast"


def test_planner_turn_partial_reply_does_not_echo_internal_user_terms(
    client: TestClient,
) -> None:
    trip_id = _create_trip(client)

    response = client.post(
        f"/api/planner/{trip_id}/turns",
        json={"message": "Could the provider model fallback explain a trip idea?"},
    )

    assert response.status_code == 200
    planner_reply = response.json()["messages"][-1]
    visible_content = planner_reply["content"].lower()
    assert planner_reply["turn_metadata"]["plan_maturity"] == "partial_plan"
    assert "provider" not in visible_content
    assert "model" not in visible_content
    assert "fallback" not in visible_content


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
    completed_tool_names = {
        item["tool_name"]
        for item in planner_reply["tool_calls"]
        if item["status"] == "completed"
    }
    assert completed_tool_names == {
        "read_workspace_state",
        "refresh_inventory",
        "refresh_scenarios",
        "read_budget_state",
        "read_policy_state",
        "read_proposal_state",
    }
    assert (
        fake_model.requests[0]["available_tools"][0]["tool_name"]
        == "read_workspace_state"
    )
    runtime_context = fake_model.requests[0]["runtime_context"]
    assert isinstance(runtime_context, dict)
    assert runtime_context["trip"]["trip_id"] == trip_id
    assert runtime_context["context_readiness"]["status"] == "ready"
    assert (
        runtime_context["autonomy_preferences"]["interaction_state"]["initiative_level"]
        == "balanced"
    )
    assert runtime_context["budget_state"]["summary"]["currency"] == "USD"
    assert "planning_ledger" in runtime_context
    assert "policy_state" in runtime_context
    assert "proposal_state" in runtime_context
    assert "recent_activity" in runtime_context

    with get_session_factory()() as db_session:
        stored = db_session.scalars(
            select(PersistedPlannerAction)
            .where(PersistedPlannerAction.trip_id == trip_id)
            .order_by(PersistedPlannerAction.occurred_at.asc())
        ).all()
        assert (
            stored[-1].payload["tool_calls"][0]["summary"]
            == "Read the current planner panel workspace state."
        )
        assert stored[-1].payload["selected_planning_mode"] == "collaborative"
        assert stored[-1].payload["runtime_mode"] == "model"
        checkpoint = db_session.get(
            PersistedPlannerCheckpoint,
            payload["planner_memory"]["current_checkpoint_id"],
        )
        assert checkpoint is not None
        assert checkpoint.metadata_payload["tool_call_count"] == 6
        assert checkpoint.metadata_payload["selected_planning_mode"] == "collaborative"


def test_planner_turn_emits_no_secret_langsmith_fleet_artifact(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    trip_id = _create_trip(client)
    artifact_path = tmp_path / "langsmith-fleet.ndjson"
    monkeypatch.setenv("TRIP_PLANNER_LANGSMITH_FLEET_PATH", str(artifact_path))

    response = client.post(
        f"/api/planner/{trip_id}/turns",
        json={
            "message": "Compare Chicago food options without storing my exact traveler note.",
            "tool_calls": [{"tool_name": "read_budget_state"}],
        },
    )

    assert response.status_code == 200
    records = [json.loads(line) for line in artifact_path.read_text().splitlines()]
    assert len(records) == 1
    record = records[0]
    assert record["schema_version"] == "langsmith-fleet/v1"
    assert record["repo"] == "stranske/trip-planner"
    assert record["surface"] == "planner-conversation"
    assert record["operation"] == "planner-turn"
    assert record["status"] == "no_secret"
    assert record["github_issue"] == "stranske/trip-planner#1208"
    domain = record["domain"]
    assert domain["planning_mode"] == "collaborative"
    assert domain["tool_call_count"] == 1
    assert domain["budget_constraint_status"] == "used"
    assert "trip_id_hash" in domain
    serialized = json.dumps(record)
    assert trip_id not in serialized
    assert "Compare Chicago food options" not in serialized

    with get_session_factory()() as db_session:
        stored = db_session.scalars(
            select(PersistedPlannerAction)
            .where(PersistedPlannerAction.trip_id == trip_id)
            .order_by(PersistedPlannerAction.occurred_at.asc())
        ).all()
        fleet_payload = stored[-1].payload["langsmith_fleet"]
        assert fleet_payload["artifact_path"] == str(artifact_path)
        assert fleet_payload["record_count"] == 1
        assert fleet_payload["run_id"].startswith("planner-turn:")


def test_configured_planner_model_receives_langsmith_trace_config(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    trip_id = _create_trip(client)
    artifact_path = tmp_path / "langsmith-fleet.ndjson"
    fake_model = FakePlannerChatModel(
        {
            "content": "I read the current workspace before recommending next steps.",
            "tool_calls": [{"tool_name": "read_workspace_state", "arguments": {}}],
        }
    )
    monkeypatch.setenv("TRIP_PLANNER_LANGSMITH_FLEET_PATH", str(artifact_path))
    monkeypatch.setenv("LANGSMITH_API_KEY", "fake-langsmith-key")
    monkeypatch.setenv("TRIP_PLANNER_PLANNER_MODEL_PROVIDER", "openai")
    monkeypatch.setenv("TRIP_PLANNER_PLANNER_MODEL", "fake-planner-model")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-openai-key")
    set_planner_chat_model_factory_for_tests(lambda _: fake_model)

    response = client.post(
        f"/api/planner/{trip_id}/turns",
        json={"message": "Use the configured model path with trace metadata."},
    )

    assert response.status_code == 200
    langsmith_config = fake_model.requests[0]["langsmith_run_config"]
    assert langsmith_config["run_name"] == "trip-planner.planner-conversation"
    assert "repo:trip-planner" in langsmith_config["tags"]
    assert langsmith_config["metadata"]["repo"] == "stranske/trip-planner"
    assert langsmith_config["metadata"]["trip_id_hash"]
    assert langsmith_config["metadata"]["trip_id_hash"] != trip_id
    assert langsmith_config["metadata"]["provider"] == "openai"
    assert langsmith_config["metadata"]["model"] == "fake-planner-model"
    assert "langsmith_run_config" not in fake_model.requests[0]["runtime_context"]
    records = [json.loads(line) for line in artifact_path.read_text().splitlines()]
    assert records
    assert records[0]["status"] == "success"
    assert records[0]["provider"] == "openai"
    assert records[0]["model"] == "fake-planner-model"
    assert records[0]["domain"]["provider_state"] == "model"


def test_planner_turn_tool_reads_are_grounded_in_persisted_workspace_state(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trip_id = _create_business_trip(client)
    seeded_budget = client.post(
        f"/api/planner/{trip_id}/turns",
        json={
            "message": "Seed planner budget state before model reads.",
            "tool_calls": [
                {"tool_name": "update_budget_plan", "arguments": {"total_amount": 2400}}
            ],
        },
    )
    assert seeded_budget.status_code == 200

    expected_workspace = client.get(f"/api/workspace/{trip_id}")
    expected_budget = client.get(f"/api/workspace/{trip_id}/budget")
    expected_policy = client.get(f"/api/workspace/{trip_id}/policy")
    expected_proposal = client.get(f"/api/workspace/{trip_id}/proposal")
    assert expected_workspace.status_code == 200
    assert expected_budget.status_code == 200
    assert expected_policy.status_code == 200
    assert expected_proposal.status_code == 200

    fake_model = FakePlannerChatModel(
        {
            "content": "I pulled the latest persisted planner state before recommending a direction.",
            "tool_calls": [
                {"tool_name": "read_workspace_state", "arguments": {}},
                {"tool_name": "refresh_inventory", "arguments": {}},
                {"tool_name": "refresh_scenarios", "arguments": {}},
                {"tool_name": "read_budget_state", "arguments": {}},
                {"tool_name": "read_policy_state", "arguments": {}},
                {"tool_name": "read_proposal_state", "arguments": {}},
            ],
        }
    )
    monkeypatch.setenv("TRIP_PLANNER_PLANNER_MODEL_PROVIDER", "openai")
    monkeypatch.setenv("TRIP_PLANNER_PLANNER_MODEL", "fake-planner-model")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-test-key")
    set_planner_chat_model_factory_for_tests(lambda _: fake_model)

    response = client.post(
        f"/api/planner/{trip_id}/turns",
        json={
            "message": "Ground your recommendation in persisted workspace and approval state."
        },
    )

    assert response.status_code == 200
    payload = response.json()
    planner_reply = payload["messages"][-1]
    assert payload["runtime"]["mode"] == "model"
    assert "Tool results:" not in planner_reply["content"]
    tool_outputs = {item["tool_name"]: item for item in planner_reply["tool_calls"]}
    assert set(tool_outputs) == {
        "read_workspace_state",
        "refresh_inventory",
        "refresh_scenarios",
        "read_budget_state",
        "read_policy_state",
        "read_proposal_state",
    }
    for result in tool_outputs.values():
        assert result["status"] == "completed"

    workspace_payload = expected_workspace.json()
    budget_payload = expected_budget.json()
    policy_payload = expected_policy.json()
    proposal_payload = expected_proposal.json()
    assert (
        tool_outputs["read_workspace_state"]["output"]["trip_title"]
        == workspace_payload["trip_record"]["trip"]["title"]
    )
    assert tool_outputs["read_workspace_state"]["output"][
        "pending_decision_count"
    ] == len(workspace_payload["planner_panel_state"]["pending_decisions"])
    assert (
        tool_outputs["refresh_inventory"]["output"]["bundle_count"]
        == workspace_payload["inventory_summary"]["bundle_count"]
    )
    assert (
        tool_outputs["refresh_scenarios"]["output"]["lead_scenario_id"]
        == workspace_payload["runtime_scenario_comparison"]["lead_scenario_id"]
    )
    assert (
        tool_outputs["read_budget_state"]["output"]["planned_total"]
        == budget_payload["summary"]["planned_total"]
    )
    assert (
        tool_outputs["read_policy_state"]["output"]["status"]
        == policy_payload["summary"]["status"]
    )
    assert (
        tool_outputs["read_proposal_state"]["output"]["status"]
        == proposal_payload["summary"]["status"]
    )


def test_planner_turn_executes_provider_rich_read_only_tools(
    client: TestClient,
) -> None:
    trip_id = _create_trip(client)

    response = client.post(
        f"/api/planner/{trip_id}/turns",
        json={
            "message": "Use richer tools to inspect sources, map status, and route refresh.",
            "tool_calls": [
                {"tool_name": "read_source_summary"},
                {"tool_name": "read_map_provider_status"},
                {"tool_name": "read_route_geometry"},
                {"tool_name": "refresh_route_comparison"},
                {"tool_name": "read_source_quality_summary"},
            ],
        },
    )

    assert response.status_code == 200
    planner_reply = response.json()["messages"][-1]
    tool_outputs = {item["tool_name"]: item for item in planner_reply["tool_calls"]}
    assert set(tool_outputs) == {
        "read_source_summary",
        "read_map_provider_status",
        "read_route_geometry",
        "refresh_route_comparison",
        "read_source_quality_summary",
    }
    assert tool_outputs["read_source_summary"]["status"] == "completed"
    assert tool_outputs["read_source_summary"]["mutates_state"] is False
    assert tool_outputs["read_source_summary"]["output"]["source_refs"]
    assert len(tool_outputs["read_source_summary"]["output"]["source_refs"]) <= 10
    assert tool_outputs["read_map_provider_status"]["output"]["provider"]["status"] in {
        "fallback",
        "loading",
        "provider-error",
        "sparse-route",
        "misconfigured",
    }
    assert tool_outputs["read_map_provider_status"]["output"]["route_state"] == "ready"
    assert tool_outputs["read_route_geometry"]["status"] == "completed"
    geometry_output = tool_outputs["read_route_geometry"]["output"]
    assert geometry_output["rough_route_geometry"]
    assert geometry_output["place_markers"]
    assert geometry_output["place_markers"][0]["description"].startswith("Route stop 1")
    assert geometry_output["place_markers"][0]["source_refs"]
    first_segment = geometry_output["rough_route_geometry"][0]
    assert first_segment["duration_minutes"] is not None
    assert first_segment["provider_distance_available"] is False
    assert first_segment["distance_verification_state"] == "duration_estimate_only"
    assert first_segment["unavailable_reason"]
    assert (
        first_segment["source_refs"]
        == geometry_output["place_markers"][0]["source_refs"]
    )
    assert tool_outputs["refresh_route_comparison"]["output"]["scenarios"]
    assert (
        tool_outputs["refresh_route_comparison"]["output"]["lead_scenario_id"]
        == response.json()["planner_panel_state"]["option_set"]["options"][0][
            "option_id"
        ]
    )
    quality_tool_output = tool_outputs["read_source_quality_summary"]
    assert quality_tool_output["status"] in {"completed", "partial"}
    assert quality_tool_output["output"]["quality_state"] != "not_available"
    quality_rows = quality_tool_output["output"]["rows"]
    assert quality_rows
    assert any(
        row["status"] == "completed"
        and row["score"] is not None
        and row["confidence_label"] in CONFIDENCE_LABELS
        and row["contributing_source_count"] > 0
        for row in quality_rows
    )

    with get_session_factory()() as db_session:
        stored = db_session.scalars(
            select(PersistedPlannerAction)
            .where(PersistedPlannerAction.trip_id == trip_id)
            .order_by(PersistedPlannerAction.occurred_at.asc())
        ).all()
        persisted_tool_names = {
            item["tool_name"] for item in stored[-1].payload["tool_calls"]
        }
        assert persisted_tool_names == set(tool_outputs)
        checkpoint = db_session.get(
            PersistedPlannerCheckpoint,
            response.json()["planner_memory"]["current_checkpoint_id"],
        )
        assert checkpoint is not None
        assert checkpoint.metadata_payload["tool_call_count"] == 5


def test_planner_turn_reuses_workspace_payload_for_provider_rich_read_only_tools(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trip_id = _create_trip(client)
    from trip_planner.app.services import planner_tools

    original_get_workspace_payload = planner_tools.get_workspace_payload
    workspace_payload_call_count = 0

    def counted_get_workspace_payload(
        *args: Any, **kwargs: Any
    ) -> dict[str, Any] | None:
        nonlocal workspace_payload_call_count
        workspace_payload_call_count += 1
        return original_get_workspace_payload(*args, **kwargs)

    monkeypatch.setattr(
        planner_tools,
        "get_workspace_payload",
        counted_get_workspace_payload,
    )

    response = client.post(
        f"/api/planner/{trip_id}/turns",
        json={
            "message": "Inspect source and route state without rebuilding payloads.",
            "tool_calls": [
                {"tool_name": "read_source_summary"},
                {"tool_name": "read_map_provider_status"},
                {"tool_name": "read_route_geometry"},
                {"tool_name": "refresh_route_comparison"},
                {"tool_name": "read_source_quality_summary"},
            ],
        },
    )

    assert response.status_code == 200
    assert workspace_payload_call_count == 1


def test_planner_turn_reports_sparse_provider_tool_state(client: TestClient) -> None:
    trip_id = _create_trip(client)

    response = client.post(
        f"/api/planner/{trip_id}/turns",
        json={
            "message": "Inspect a route option that does not exist.",
            "tool_calls": [
                {
                    "tool_name": "read_map_provider_status",
                    "arguments": {"route_option_id": "route-option:missing"},
                },
                {
                    "tool_name": "read_route_geometry",
                    "arguments": {"route_option_id": "route-option:missing"},
                },
            ],
        },
    )

    assert response.status_code == 200
    planner_reply = response.json()["messages"][-1]
    tool_outputs = {item["tool_name"]: item for item in planner_reply["tool_calls"]}
    assert tool_outputs["read_map_provider_status"]["status"] == "not_available"
    assert (
        tool_outputs["read_map_provider_status"]["output"]["route_state"] == "missing"
    )
    assert tool_outputs["read_route_geometry"]["status"] == "not_available"
    assert tool_outputs["read_route_geometry"]["output"]["rough_route_geometry"] == []


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
                "tool_calls": [
                    {"tool_name": "update_budget_plan", "arguments": "not-a-dict"}
                ],
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
                    "arguments": {
                        "total_amount": 1200,
                        "title": "Planner first-pass budget",
                    },
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
    assert "Tool results:" not in planner_reply["content"]

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


def test_planner_turn_handles_planning_notebook_commands(client: TestClient) -> None:
    trip_id = _create_trip(client)

    remembered = client.post(
        f"/api/planner/{trip_id}/turns",
        json={
            "message": (
                "Remember this for later: Compare fewer evening moves before the next checkpoint."
            )
        },
    )

    assert remembered.status_code == 200, remembered.text
    remembered_reply = remembered.json()["messages"][-1]
    capture_call = next(
        item
        for item in remembered_reply["tool_calls"]
        if item["tool_name"] == "capture_notebook_item"
    )
    assert capture_call["status"] == "completed"
    notebook_item_id = capture_call["output"]["notebook_item_id"]

    workspace = client.get(f"/api/workspace/{trip_id}")
    assert workspace.status_code == 200
    notebook_items = workspace.json()["planning_notebook"]["items"]
    assert notebook_items[0]["notebook_item_id"] == notebook_item_id
    assert notebook_items[0]["source"] == "planner"
    assert (
        notebook_items[0]["title"]
        == "Compare fewer evening moves before the next checkpoint."
    )

    focused = client.post(
        f"/api/planner/{trip_id}/turns",
        json={"message": "I was working on lodging."},
    )

    assert focused.status_code == 200, focused.text
    focused_reply = focused.json()["messages"][-1]
    focus_call = next(
        item
        for item in focused_reply["tool_calls"]
        if item["tool_name"] == "set_notebook_focus"
    )
    assert focus_call["output"] == {"category": "lodging", "notebook_item_id": None}

    completed_route = client.post(
        f"/api/planner/{trip_id}/turns",
        json={
            "message": "Create a completed route notebook item.",
            "tool_calls": [
                {
                    "tool_name": "capture_notebook_item",
                    "arguments": {
                        "title": "Compare airport train with taxi transfer.",
                        "category": "route",
                        "status": "completed",
                    },
                }
            ],
        },
    )
    assert completed_route.status_code == 200, completed_route.text

    read_completed = client.post(
        f"/api/planner/{trip_id}/turns",
        json={"message": "Show me completed route tasks."},
    )

    assert read_completed.status_code == 200, read_completed.text
    read_reply = read_completed.json()["messages"][-1]
    read_call = next(
        item
        for item in read_reply["tool_calls"]
        if item["tool_name"] == "read_planning_notebook"
    )
    assert read_call["output"]["completed_count"] == 1
    assert (
        read_call["output"]["items"][0]["title"]
        == "Compare airport train with taxi transfer."
    )


def test_planner_turn_matches_notebook_focus_synonyms_and_clarifies_ambiguity(
    client: TestClient,
) -> None:
    hotel_trip_id = _create_trip(client)
    hotel_focus = client.post(
        f"/api/planner/{hotel_trip_id}/turns",
        json={"message": "I was looking at hotel options."},
    )

    assert hotel_focus.status_code == 200, hotel_focus.text
    hotel_reply = hotel_focus.json()["messages"][-1]
    hotel_focus_call = next(
        item
        for item in hotel_reply["tool_calls"]
        if item["tool_name"] == "set_notebook_focus"
    )
    assert hotel_focus_call["output"] == {
        "category": "lodging",
        "notebook_item_id": None,
    }

    flight_trip_id = _create_trip(client)
    flight_focus = client.post(
        f"/api/planner/{flight_trip_id}/turns",
        json={"message": "I was checking on flights."},
    )

    assert flight_focus.status_code == 200, flight_focus.text
    flight_reply = flight_focus.json()["messages"][-1]
    flight_focus_call = next(
        item
        for item in flight_reply["tool_calls"]
        if item["tool_name"] == "set_notebook_focus"
    )
    assert flight_focus_call["output"] == {
        "category": "route",
        "notebook_item_id": None,
    }

    ambiguous_trip_id = _create_trip(client)
    ambiguous_focus = client.post(
        f"/api/planner/{ambiguous_trip_id}/turns",
        json={"message": "Put this aside for later."},
    )

    assert ambiguous_focus.status_code == 200, ambiguous_focus.text
    ambiguous_reply = ambiguous_focus.json()["messages"][-1]
    assert all(
        item["tool_name"] != "set_notebook_focus"
        for item in ambiguous_reply["tool_calls"]
    )
    assert "Which planning area did you mean" in ambiguous_reply["content"]
    question_blocks = [
        block
        for block in ambiguous_reply["structured_blocks"]
        if block["kind"] == "question"
    ]
    assert question_blocks
    assert any(
        "route, lodging, activities, budget, documents, or policy" in item
        for block in question_blocks
        for item in block["items"]
    )


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
        assert (
            stored[-1].payload["tool_calls"][0]["summary"]
            == "Updated the workspace budget plan to USD 900.00."
        )


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
    assert payload["messages"][1]["content"].startswith(
        "Planner API kickoff has a useful starting point"
    )
    assert payload["messages"][1]["turn_metadata"]["task_class"] == "first_turn_triage"
    assert payload["planner_memory"]["artifacts"][0]["title"] == "Planner checkpoint 1"


def test_planner_resume_regenerates_memory_from_raw_transcript(
    client: TestClient,
) -> None:
    trip_id = _create_trip(client)
    first_turn = client.post(
        f"/api/planner/{trip_id}/turns",
        json={
            "message": "Keep the baseline narrow and summarize the current direction."
        },
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
    assert payload["planner_memory"]["artifacts"][0]["summary"].startswith(
        "Turn 1 checkpoint"
    )
