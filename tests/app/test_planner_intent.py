from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.app.services.planner import (
    set_intent_classifier_factory_for_tests,
    set_planner_chat_model_factory_for_tests,
    set_planner_prompt_redactor_for_tests,
)
from trip_planner.app.services.planner_routing import IntentResult
from trip_planner.app.services.planner_runtime_config import (
    build_intent_classifier,
    build_planner_runtime_config,
)
from trip_planner.persistence.db import reset_database_state


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'planner.db'}")
    monkeypatch.delenv("TRIP_PLANNER_PLANNER_MODEL_PROVIDER", raising=False)
    monkeypatch.delenv("TRIP_PLANNER_PLANNER_PROVIDER", raising=False)
    monkeypatch.delenv("TRIP_PLANNER_PLANNER_MODEL", raising=False)
    monkeypatch.delenv("TRIP_PLANNER_DATA_ZONE", raising=False)
    monkeypatch.delenv("TRIP_PLANNER_OPENAI_AUTHORIZED_ENDPOINT", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    monkeypatch.delenv("LANGCHAIN_PROJECT", raising=False)
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    monkeypatch.delenv("TRIP_PLANNER_LANGSMITH_FLEET_PATH", raising=False)
    set_intent_classifier_factory_for_tests(None)
    set_planner_chat_model_factory_for_tests(None)
    set_planner_prompt_redactor_for_tests(None)
    reset_database_state()
    app = create_app()

    with TestClient(app) as test_client:
        signup = test_client.post(
            "/api/auth/signup",
            json={
                "email": "planner-intent@example.com",
                "password": "password123",
                "display_name": "Planner Intent Owner",
            },
        )
        assert signup.status_code == 201
        yield test_client

    set_intent_classifier_factory_for_tests(None)
    set_planner_chat_model_factory_for_tests(None)
    set_planner_prompt_redactor_for_tests(None)
    reset_database_state()


class StubIntentClassifier:
    def classify(self, message: str, context: Mapping[str, Any]) -> IntentResult:
        assert message == "let's lock it in"
        assert context["base_task_class"]
        return IntentResult(task_class="decision", intent="decision")


class InvalidTaskClassifier:
    def classify(self, message: str, context: Mapping[str, Any]) -> IntentResult:
        assert context["base_task_class"]
        return IntentResult(task_class="not_a_known_task", intent="not_a_known_task")


class StubPlannerIntentModel:
    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.payloads.append(payload)
        return {"task_class": "decision", "intent": "decision"}


def _create_trip(client: TestClient) -> str:
    response = client.post(
        "/api/trips",
        json={
            "title": "Intent classifier seam",
            "summary": "Need a persisted planner session.",
            "mode": "leisure",
            "trip_frame": {
                "start_date": "2026-05-04",
                "end_date": "2026-05-10",
                "duration_days": 7,
                "primary_regions": ["Kyoto"],
                "traveler_party": {
                    "kind": "solo",
                    "traveler_count": 1,
                    "notes": "Planner intent test",
                },
            },
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["trip"]["trip_id"])


def test_injected_classifier_routes_turn(client: TestClient) -> None:
    trip_id = _create_trip(client)
    set_intent_classifier_factory_for_tests(lambda _: StubIntentClassifier())

    response = client.post(
        f"/api/planner/{trip_id}/turns",
        json={"message": "let's lock it in"},
    )

    assert response.status_code == 200, response.text
    metadata = response.json()["messages"][-1]["turn_metadata"]
    assert metadata["task_class"] == "decision"
    assert metadata["intent"] == "decision"
    assert metadata["debug_routing_details"]["classifier_task_class"] == "decision"


def test_model_intent_classifier_uses_configured_model() -> None:
    runtime_config = build_planner_runtime_config(
        {
            "TRIP_PLANNER_PLANNER_PROVIDER": "fake",
            "TRIP_PLANNER_PLANNER_MODEL": "intent-test-model",
        }
    )
    model = StubPlannerIntentModel()
    classifier = build_intent_classifier(runtime_config, model=model)

    result = classifier.classify(
        "let's lock it in",
        {"base_task_class": "first_turn_triage", "planning_mode": "collaborative"},
    )

    assert result.task_class == "decision"
    assert result.intent == "decision"
    assert model.payloads
    assert model.payloads[-1]["task"] == "classify_planner_intent"


def test_invalid_classifier_task_class_falls_back_to_base_task(client: TestClient) -> None:
    trip_id = _create_trip(client)
    set_intent_classifier_factory_for_tests(lambda _: InvalidTaskClassifier())

    response = client.post(
        f"/api/planner/{trip_id}/turns",
        json={"message": "let's lock it in"},
    )

    assert response.status_code == 200, response.text
    metadata = response.json()["messages"][-1]["turn_metadata"]
    assert metadata["task_class"] == "first_turn_triage"
    assert metadata["intent"] == "first_turn_triage"
    assert metadata["debug_routing_details"]["classifier_task_class"] == "first_turn_triage"
