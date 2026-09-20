from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.app.services.planner import (
    _fallback_content_from_metadata,
    _format_choice_list,
    _format_estimated_total,
    _scenario_cost_summary,
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


def test_fallback_one_word_cost_and_policy_intents_are_not_gibberish(client: TestClient) -> None:
    trip_id = _create_business_trip(client)
    cost_reply = _planner_reply(client, trip_id, "cost")
    policy_reply = _planner_reply(client, trip_id, "policy")
    assert "no priced scenarios" in cost_reply.lower() or "scenario costs" in cost_reply.lower()
    assert "policy" in policy_reply.lower()
    assert "could not extract" not in cost_reply.lower()
    assert "could not extract" not in policy_reply.lower()


def test_format_estimated_total_rejects_malformed_and_non_finite_values() -> None:
    assert _format_estimated_total({"typical_amount": 1200, "currency": "USD"}) == "USD 1,200"
    assert _format_estimated_total({"typical_amount": "not-a-number", "currency": "USD"}) is None
    assert _format_estimated_total({"typical_amount": float("nan"), "currency": "USD"}) is None
    assert _format_estimated_total({"typical_amount": float("inf"), "currency": "USD"}) is None


def test_scenario_cost_summary_requires_at_least_one_priced_scenario() -> None:
    assert _scenario_cost_summary(
        [
            {
                "title": "Scenario",
                "metrics": {"transfers": 2},
            }
        ]
    ) is None
    summary = _scenario_cost_summary(
        [
            {
                "title": "Direct",
                "metrics": {
                    "estimated_total": {"typical_amount": 900, "currency": "USD"},
                    "transfers": 1,
                },
            },
            {
                "title": "Saver",
                "metrics": {
                    "estimated_total": {"typical_amount": 650, "currency": "USD"},
                    "transfers": 2,
                },
            },
        ]
    )
    assert summary is not None
    assert "USD 900" in summary
    assert "1 transfer" in summary
    assert "2 transfers" in summary


def test_format_choice_list_uses_human_readable_punctuation() -> None:
    assert _format_choice_list(["Keep"]) == "Keep."
    assert _format_choice_list(["Keep", "Compare"]) == "Keep or Compare."
    assert _format_choice_list(["Keep", "Compare", "Revise"]) == "Keep, Compare, or Revise."


def test_fallback_content_cost_branch_with_priced_scenarios() -> None:
    content = _fallback_content_from_metadata(
        trip_title="Summit trip",
        message="how much will this cost?",
        metadata={"plan_maturity": "open_ended"},
        scenarios=[
            {
                "title": "Option A",
                "metrics": {
                    "estimated_total": {"typical_amount": 500, "currency": "EUR"},
                    "transfers": 1,
                },
            }
        ],
    )
    assert "Scenario costs" in content
    assert "EUR 500" in content
    assert "1 transfer" in content
