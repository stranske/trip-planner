from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.persistence.db import reset_database_state


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv(
        "TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'budget.db'}"
    )
    reset_database_state()
    app = create_app()

    with TestClient(app) as test_client:
        test_client.post(
            "/api/auth/signup",
            json={
                "email": "budget@example.com",
                "password": "password123",
                "display_name": "Budget Owner",
            },
        )
        yield test_client

    reset_database_state()


def test_workspace_budget_route_persists_plan_and_spend_events(client: TestClient) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Budgeted Kyoto",
            "summary": "Track the spend drift in the workspace.",
            "mode": "leisure",
            "trip_frame": {"duration_days": 4, "primary_regions": ["Kyoto"]},
        },
    )
    trip_id = created.json()["trip"]["trip_id"]

    saved_budget = client.put(
        f"/api/workspace/{trip_id}/budget",
        json={
            "title": "Kyoto spring guardrails",
            "currency": "USD",
            "scenario_budgets": [
                {
                    "title": "Baseline budget",
                    "allocations": [
                        {
                            "category_key": "lodging",
                            "label": "Lodging",
                            "planned_amount": 600,
                        },
                        {
                            "category_key": "food",
                            "label": "Food",
                            "planned_amount": 180,
                        },
                        {
                            "category_key": "activities",
                            "label": "Activities",
                            "planned_amount": 140,
                        },
                    ],
                }
            ],
            "summary": "Initial workspace budget",
        },
    )

    assert saved_budget.status_code == 200
    budget_payload = saved_budget.json()
    assert budget_payload["budget_plan"]["title"] == "Kyoto spring guardrails"
    assert budget_payload["summary"]["planned_total"] == 920
    assert budget_payload["summary"]["actual_total"] == 0
    assert budget_payload["versions"][0]["summary"] == "Initial workspace budget"

    recorded_spend = client.post(
        f"/api/workspace/{trip_id}/budget/spend-events",
        json={
            "category_key": "food",
            "amount": 42.5,
            "source_kind": "manual",
            "source_context": "Dinner near Gion",
            "merchant_name": "Kyoto Kitchen",
        },
    )

    assert recorded_spend.status_code == 200
    spend_payload = recorded_spend.json()
    assert spend_payload["summary"]["actual_total"] == 42.5
    assert spend_payload["summary"]["remaining_total"] == 877.5
    assert spend_payload["spend_events"][0]["merchant_name"] == "Kyoto Kitchen"

    workspace = client.get(f"/api/workspace/{trip_id}")

    assert workspace.status_code == 200
    workspace_payload = workspace.json()
    assert workspace_payload["budget_state"]["summary"]["planned_total"] == 920
    assert workspace_payload["budget_state"]["summary"]["actual_total"] == 42.5
    assert workspace_payload["trip_record"]["artifact_refs"]["budget_state_id"] == "budget-plan:" + trip_id
    assert workspace_payload["session"]["active_budget_plan_id"] == "budget-plan:" + trip_id


def test_workspace_budget_spend_event_can_be_updated(client: TestClient) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Client summit",
            "summary": "Exercise spend-event edits.",
            "mode": "business",
            "trip_frame": {"duration_days": 2, "primary_regions": ["Chicago"]},
        },
    )
    trip_id = created.json()["trip"]["trip_id"]

    client.put(
        f"/api/workspace/{trip_id}/budget",
        json={
            "title": "Client summit plan",
            "currency": "USD",
            "scenario_budgets": [
                {
                    "title": "Compliant budget",
                    "allocations": [
                        {
                            "category_key": "workspace",
                            "label": "Workspace",
                            "planned_amount": 200,
                        },
                        {
                            "category_key": "client_hospitality",
                            "label": "Client hospitality",
                            "planned_amount": 150,
                        },
                    ],
                }
            ],
        },
    )
    recorded = client.post(
        f"/api/workspace/{trip_id}/budget/spend-events",
        json={
            "category_key": "client_hospitality",
            "amount": 75,
            "source_kind": "manual",
            "source_context": "Team dinner",
        },
    )
    spend_event_id = recorded.json()["spend_events"][0]["spend_event_id"]

    updated = client.patch(
        f"/api/workspace/{trip_id}/budget/spend-events/{spend_event_id}",
        json={
            "category_key": "client_hospitality",
            "amount": 95,
            "source_kind": "receipt",
            "source_context": "Updated dinner receipt",
            "merchant_name": "The Delegate Room",
        },
    )

    assert updated.status_code == 200
    payload = updated.json()
    assert payload["spend_events"][0]["amount"] == 95
    assert payload["spend_events"][0]["source_kind"] == "receipt"
    assert payload["summary"]["actual_total"] == 95
    hospitality_row = next(
        item
        for item in payload["summary"]["category_summaries"]
        if item["category_key"] == "client_hospitality"
    )
    assert hospitality_row["remaining_amount"] == 55


def test_workspace_budget_spend_event_rejects_currency_drift(client: TestClient) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Budget guardrails",
            "summary": "Reject cross-currency spend capture.",
            "mode": "leisure",
            "trip_frame": {"duration_days": 3, "primary_regions": ["Lisbon"]},
        },
    )
    trip_id = created.json()["trip"]["trip_id"]

    client.put(
        f"/api/workspace/{trip_id}/budget",
        json={
            "title": "Lisbon budget",
            "currency": "USD",
            "scenario_budgets": [
                {
                    "title": "Baseline",
                    "allocations": [
                        {
                            "category_key": "food",
                            "label": "Food",
                            "planned_amount": 150,
                        }
                    ],
                }
            ],
        },
    )

    recorded = client.post(
        f"/api/workspace/{trip_id}/budget/spend-events",
        json={
            "category_key": "food",
            "amount": 30,
            "currency": "eur",
            "source_kind": "manual",
            "source_context": "Lunch",
        },
    )

    assert recorded.status_code == 400
    assert recorded.json()["detail"] == "currency must match the persisted budget plan currency"


def test_workspace_budget_spend_event_updates_session_timestamp(client: TestClient) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Timestamp guardrails",
            "summary": "Budget spend updates should refresh workspace session state.",
            "mode": "business",
            "trip_frame": {"duration_days": 2, "primary_regions": ["Austin"]},
        },
    )
    trip_id = created.json()["trip"]["trip_id"]

    client.put(
        f"/api/workspace/{trip_id}/budget",
        json={
            "title": "Austin budget",
            "currency": "USD",
            "scenario_budgets": [
                {
                    "title": "Baseline",
                    "allocations": [
                        {
                            "category_key": "workspace",
                            "label": "Workspace",
                            "planned_amount": 120,
                        }
                    ],
                }
            ],
        },
    )
    workspace_before = client.get(f"/api/workspace/{trip_id}").json()
    before_timestamp = workspace_before["session"]["updated_at"]

    recorded = client.post(
        f"/api/workspace/{trip_id}/budget/spend-events",
        json={
            "category_key": "workspace",
            "amount": 45,
            "source_kind": "manual",
            "source_context": "Coworking day pass",
        },
    )

    assert recorded.status_code == 200
    workspace_after_create = client.get(f"/api/workspace/{trip_id}").json()
    after_create_timestamp = workspace_after_create["session"]["updated_at"]
    assert after_create_timestamp > before_timestamp

    spend_event_id = recorded.json()["spend_events"][0]["spend_event_id"]
    updated = client.patch(
        f"/api/workspace/{trip_id}/budget/spend-events/{spend_event_id}",
        json={
            "category_key": "workspace",
            "amount": 55,
            "source_kind": "receipt",
            "source_context": "Final receipt",
            "currency": "USD",
        },
    )

    assert updated.status_code == 200
    workspace_after_update = client.get(f"/api/workspace/{trip_id}").json()
    assert workspace_after_update["session"]["updated_at"] > after_create_timestamp
