from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.app.services.planner import (
    set_intent_classifier_factory_for_tests,
    set_planner_chat_model_factory_for_tests,
    set_planner_prompt_redactor_for_tests,
)
from trip_planner.persistence.db import reset_database_state


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'planner-fallback.db'}")
    monkeypatch.delenv("TRIP_PLANNER_PLANNER_MODEL_PROVIDER", raising=False)
    monkeypatch.delenv("TRIP_PLANNER_PLANNER_PROVIDER", raising=False)
    monkeypatch.delenv("TRIP_PLANNER_PLANNER_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    set_intent_classifier_factory_for_tests(None)
    set_planner_chat_model_factory_for_tests(None)
    set_planner_prompt_redactor_for_tests(None)
    reset_database_state()
    app = create_app()

    with TestClient(app) as test_client:
        signup = test_client.post(
            "/api/auth/signup",
            json={
                "email": "planner-fallback@example.com",
                "password": "password123",
                "display_name": "Planner Fallback Owner",
            },
        )
        assert signup.status_code == 201
        yield test_client

    set_intent_classifier_factory_for_tests(None)
    set_planner_chat_model_factory_for_tests(None)
    set_planner_prompt_redactor_for_tests(None)
    reset_database_state()


def _create_business_trip(client: TestClient) -> str:
    response = client.post(
        "/api/trips",
        json={
            "title": "Client summit fallback test",
            "summary": "Business trip for fallback planner coverage.",
            "mode": "business",
            "trip_frame": {
                "start_date": "2026-09-08",
                "end_date": "2026-09-12",
                "duration_days": 5,
                "primary_regions": ["Chicago"],
                "traveler_party": {
                    "kind": "solo",
                    "traveler_count": 1,
                    "notes": "Fallback planner test",
                },
            },
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["trip"]["trip_id"])


def _planner_reply(client: TestClient, trip_id: str, message: str) -> str:
    response = client.post(
        f"/api/planner/{trip_id}/turns",
        json={"message": message},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["runtime"]["mode"] == "fallback"
    return str(payload["messages"][-1]["content"])


def test_fallback_replies_differ_for_materially_different_messages(client: TestClient) -> None:
    trip_id = _create_business_trip(client)
    cancel_reply = _planner_reply(client, trip_id, "Cancel this trip. I do not want to travel at all.")
    nonsense_reply = _planner_reply(
        client,
        trip_id,
        "zzzz qqqq wwww nonsense tokens 12345",
    )
    assert cancel_reply != nonsense_reply
    assert "cancel" in cancel_reply.lower() or "stop" in cancel_reply.lower()
    assert "could not extract" in nonsense_reply.lower() or "keyword matching" in nonsense_reply.lower()
