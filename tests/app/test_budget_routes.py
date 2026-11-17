import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from trip_planner.app.main import create_app
from trip_planner.persistence.db import get_session_factory, reset_database_state
from trip_planner.persistence.models.budget import (
    PersistedActualSpendEvent,
    PersistedBudgetPlan,
    PersistedBudgetPlanVersion,
)
from trip_planner.persistence.models.session import PersistedPlanningSessionState
from trip_planner.persistence.models.trip import PersistedTrip


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'budget.db'}")
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
    assert (
        workspace_payload["trip_record"]["artifact_refs"]["budget_state_id"]
        == "budget-plan:" + trip_id
    )
    assert workspace_payload["session"]["active_budget_plan_id"] == "budget-plan:" + trip_id


@pytest.mark.parametrize("amount", [float("nan"), float("inf"), float("-inf")])
def test_budget_route_rejects_non_finite_amounts(client: TestClient, amount: float) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Finite budget guard",
            "summary": "Reject non-finite budget inputs before persistence.",
            "mode": "leisure",
            "trip_frame": {"duration_days": 4, "primary_regions": ["Kyoto"]},
        },
    )
    trip_id = created.json()["trip"]["trip_id"]

    saved_budget = client.put(
        f"/api/workspace/{trip_id}/budget",
        content=json.dumps(
            {
                "title": "Invalid budget",
                "currency": "USD",
                "scenario_budgets": [
                    {
                        "title": "Non-finite allocation",
                        "allocations": [
                            {
                                "category_key": "food",
                                "label": "Food",
                                "planned_amount": amount,
                            }
                        ],
                    }
                ],
            }
        ),
        headers={"content-type": "application/json"},
    )

    assert saved_budget.status_code == 422
    assert client.get(f"/api/workspace/{trip_id}/budget").json()["budget_plan"] is None


@pytest.mark.parametrize("amount", [float("nan"), float("inf"), float("-inf")])
def test_budget_spend_routes_reject_non_finite_amounts_without_mutating_state(
    client: TestClient, amount: float
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Finite spend guard",
            "summary": "Reject non-finite spend inputs before persistence.",
            "mode": "leisure",
            "trip_frame": {"duration_days": 4, "primary_regions": ["Kyoto"]},
        },
    )
    trip_id = created.json()["trip"]["trip_id"]
    client.put(
        f"/api/workspace/{trip_id}/budget",
        json={
            "title": "Finite spend plan",
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

    rejected_create = client.post(
        f"/api/workspace/{trip_id}/budget/spend-events",
        content=json.dumps(
            {
                "category_key": "food",
                "amount": amount,
                "source_kind": "manual",
                "source_context": "Invalid spend",
            }
        ),
        headers={"content-type": "application/json"},
    )
    assert rejected_create.status_code == 422
    assert client.get(f"/api/workspace/{trip_id}/budget").json()["spend_events"] == []

    recorded = client.post(
        f"/api/workspace/{trip_id}/budget/spend-events",
        json={
            "category_key": "food",
            "amount": 25,
            "source_kind": "manual",
            "source_context": "Valid spend",
        },
    )
    spend_event_id = recorded.json()["spend_events"][0]["spend_event_id"]
    original_event = client.get(f"/api/workspace/{trip_id}/budget").json()["spend_events"][0]
    rejected_update = client.patch(
        f"/api/workspace/{trip_id}/budget/spend-events/{spend_event_id}",
        content=json.dumps(
            {
                "category_key": "food",
                "amount": amount,
                "source_kind": "manual",
                "source_context": "Invalid replacement",
            }
        ),
        headers={"content-type": "application/json"},
    )
    assert rejected_update.status_code == 422
    assert (
        client.get(f"/api/workspace/{trip_id}/budget").json()["spend_events"][0] == original_event
    )


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
    assert recorded.json()["detail"].startswith("The workspace budget request was invalid.")
    budget_url = f"/api/workspace/{trip_id}/budget"
    assert client.get(budget_url).json()["spend_events"] == []

    spend = {"category_key": "food", "amount": 30, "source_context": "Lunch", "currency": "usd"}
    accepted = client.post(f"{budget_url}/spend-events", json=spend)
    assert accepted.status_code == 200
    before = accepted.json()
    event = before["spend_events"][0]
    assert event["currency"] == "USD"

    rejected_edit = client.patch(
        f"{budget_url}/spend-events/{event['spend_event_id']}",
        json={**spend, "amount": 40, "currency": "eur"},
    )
    assert rejected_edit.status_code == 400
    assert client.get(budget_url).json() == before

    accepted_edit = client.patch(
        f"{budget_url}/spend-events/{event['spend_event_id']}",
        json={**spend, "amount": 40},
    )
    assert accepted_edit.status_code == 200
    after = accepted_edit.json()
    assert after["spend_events"][0]["currency"] == "USD"
    assert after["summary"]["actual_total"] == 40
    assert after["summary"]["version_count"] == before["summary"]["version_count"]
    assert client.get(budget_url).json() == after


def _persisted_budget_state(trip_id: str) -> dict[str, list[dict[str, Any]]]:
    """Read persisted rows directly, without invoking the read-side currency guard."""
    models = (
        PersistedBudgetPlan,
        PersistedBudgetPlanVersion,
        PersistedActualSpendEvent,
        PersistedPlanningSessionState,
        PersistedTrip,
    )
    with get_session_factory()() as db_session:
        return {
            model.__tablename__: [
                dict(row)
                for row in db_session.execute(
                    select(model.__table__)
                    .where(model.trip_id == trip_id)
                    .order_by(*model.__table__.primary_key)
                ).mappings()
            ]
            for model in models
        }


def _budget_in_currency(currency: str, *, planned_amount: int = 150) -> dict[str, Any]:
    return {
        "title": f"{currency} budget",
        "currency": currency,
        "scenario_budgets": [
            {
                "title": "Baseline",
                "allocations": [
                    {
                        "category_key": "food",
                        "label": "Food",
                        "planned_amount": planned_amount,
                        "currency": currency,
                    }
                ],
            }
        ],
    }


@pytest.fixture
def budget_url(client: TestClient) -> str:
    created = client.post(
        "/api/trips",
        json={
            "title": "Lisbon budget",
            "mode": "leisure",
            "trip_frame": {"duration_days": 3, "primary_regions": ["Lisbon"]},
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]
    url = f"/api/workspace/{trip_id}/budget"
    assert client.put(url, json=_budget_in_currency("USD")).status_code == 200
    return url


@pytest.mark.parametrize(
    "food_amount,lodging_amount,actual_total",
    [(30, 45.5, 75.5), (0.01, 0.01, 0.02)],
    ids=["ordinary-spend", "one-cent-spend"],
)
def test_plan_currency_change_rejected_when_spend_in_other_currency(
    client: TestClient,
    budget_url: str,
    food_amount: float,
    lodging_amount: float,
    actual_total: float,
) -> None:
    recorded = client.post(
        f"{budget_url}/spend-events",
        json={"category_key": "food", "amount": food_amount, "source_context": "Lunch"},
    )
    assert recorded.status_code == 200
    recorded = client.post(
        f"{budget_url}/spend-events",
        json={
            "category_key": "lodging",
            "amount": lodging_amount,
            "source_context": "Hotel deposit",
        },
    )
    assert recorded.status_code == 200
    before = recorded.json()
    plan_id = before["budget_plan"]["budget_plan_id"]
    assert len(before["spend_events"]) == 2
    assert before["summary"]["planned_total"] == 150
    assert before["summary"]["actual_total"] == actual_total
    assert before["summary"]["remaining_total"] == 150 - actual_total
    assert before["summary"]["version_count"] == 1
    trip_id = before["budget_plan"]["trip_id"]
    persisted_before = _persisted_budget_state(trip_id)

    rejected = client.put(budget_url, json=_budget_in_currency("EUR", planned_amount=200))

    persisted_after = _persisted_budget_state(trip_id)
    assert persisted_after == persisted_before
    with get_session_factory()() as db_session:
        plan = db_session.get(PersistedBudgetPlan, plan_id)
        assert plan is not None
        version_ids = db_session.scalars(
            select(PersistedBudgetPlanVersion.version_id).where(
                PersistedBudgetPlanVersion.budget_plan_id == plan_id
            )
        ).all()
        assert rejected.status_code == 422, (rejected.text, plan.currency, len(version_ids))
        assert plan.currency == "USD"
        assert plan.scenario_budgets == before["budget_plan"]["scenario_budgets"]
        assert list(version_ids) == [before["versions"][0]["version_id"]]
    assert rejected.json()["detail"].startswith(
        "The budget plan currency must match all recorded spend currencies."
    )

    reread = client.get(budget_url)
    assert reread.status_code == 200
    assert reread.json() == before


@pytest.mark.parametrize("currency", ["USD", "EUR", "GBP"])
def test_plan_update_checks_all_legacy_spend_currencies(
    client: TestClient, budget_url: str, currency: str
) -> None:
    spend_url = f"{budget_url}/spend-events"
    spend = {"category_key": "food", "amount": 30, "source_context": "Lunch"}
    first = client.post(spend_url, json=spend)
    assert first.status_code == 200
    second = client.post(spend_url, json={**spend, "source_context": "Dinner"})
    assert second.status_code == 200
    payload = second.json()
    trip_id = payload["budget_plan"]["trip_id"]
    with get_session_factory()() as db_session:
        event = db_session.get(
            PersistedActualSpendEvent, payload["spend_events"][0]["spend_event_id"]
        )
        assert event is not None
        event.currency = "EUR"
        db_session.commit()
    persisted_before = _persisted_budget_state(trip_id)

    rejected = client.put(budget_url, json=_budget_in_currency(currency, planned_amount=200))

    assert rejected.status_code == 422
    assert rejected.json()["detail"].startswith(
        "The budget plan currency must match all recorded spend currencies."
    )
    assert _persisted_budget_state(trip_id) == persisted_before


def test_plan_currency_change_allowed_without_spend(client: TestClient, budget_url: str) -> None:
    updated = client.put(budget_url, json=_budget_in_currency("EUR", planned_amount=200))

    assert updated.status_code == 200
    payload = updated.json()
    plan = payload["budget_plan"]
    scenario = plan["scenario_budgets"][0]
    allocation = scenario["allocations"][0]
    assert plan["currency"] == scenario["currency"] == allocation["currency"] == "EUR"
    assert payload["summary"]["currency"] == "EUR"
    assert payload["summary"]["planned_total"] == 200
    assert payload["summary"]["actual_total"] == 0
    assert payload["summary"]["version_count"] == 2
    assert payload["spend_events"] == []
    assert client.get(budget_url).json() == payload


def test_legacy_mixed_currency_read_returns_conflict(client: TestClient, budget_url: str) -> None:
    spend_url = f"{budget_url}/spend-events"
    spend = {"category_key": "food", "amount": 30, "source_context": "Lunch"}
    first = client.post(spend_url, json=spend)
    assert first.status_code == 200
    second = client.post(spend_url, json={**spend, "source_context": "Dinner"})
    assert second.status_code == 200
    event_ids = [event["spend_event_id"] for event in second.json()["spend_events"]]

    with get_session_factory()() as db_session:
        event = db_session.get(PersistedActualSpendEvent, event_ids[0])
        assert event is not None
        event.currency = "EUR"
        db_session.commit()

    for url in (budget_url, budget_url.removesuffix("/budget")):
        response = client.get(url)
        assert response.status_code == 409
        assert response.json()["detail"].startswith(
            "Recorded spend currencies conflict with the workspace budget currency."
        )

    rejected = client.post(spend_url, json={**spend, "source_context": "Breakfast"})
    assert rejected.status_code == 409
    with get_session_factory()() as db_session:
        stored_ids = db_session.scalars(select(PersistedActualSpendEvent.spend_event_id)).all()
    assert sorted(stored_ids) == sorted(event_ids)


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


def test_unallocated_category_spend_counts_in_actual_total(client: TestClient) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Unallocated spend",
            "summary": "Spend outside allocations should still appear in summaries.",
            "mode": "leisure",
            "trip_frame": {"duration_days": 3, "primary_regions": ["Kyoto"]},
        },
    )
    trip_id = created.json()["trip"]["trip_id"]

    client.put(
        f"/api/workspace/{trip_id}/budget",
        json={
            "title": "Kyoto guardrails",
            "currency": "USD",
            "scenario_budgets": [
                {
                    "title": "Baseline",
                    "allocations": [
                        {
                            "category_key": "food",
                            "label": "Food",
                            "planned_amount": 100,
                        },
                    ],
                }
            ],
        },
    )

    payload = client.post(
        f"/api/workspace/{trip_id}/budget/spend-events",
        json={
            "category_key": "lodging",
            "amount": 50,
            "source_kind": "manual",
            "source_context": "Hotel deposit",
        },
    ).json()

    assert payload["summary"]["actual_total"] == 50
    assert payload["summary"]["remaining_total"] == 50
    lodging_row = next(
        item
        for item in payload["summary"]["category_summaries"]
        if item["category_key"] == "lodging"
    )
    assert lodging_row["planned_amount"] == 0
    assert lodging_row["actual_amount"] == 50
    assert lodging_row["remaining_amount"] == -50
    assert lodging_row["flexibility"] == "flexible"
