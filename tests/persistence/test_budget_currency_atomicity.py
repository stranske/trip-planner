"""Exercise currency rejection against SQLite without an HTTP transport."""

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from trip_planner.app.routes.budget import save_workspace_budget
from trip_planner.app.schemas.budget import BudgetPlanUpsertRequest
from trip_planner.app.services.auth import AuthenticatedUser
from trip_planner.app.services.budget import get_workspace_budget_payload
from trip_planner.persistence.db import Base
from trip_planner.persistence.models.account import UserAccount
from trip_planner.persistence.models.budget import (
    PersistedActualSpendEvent,
    PersistedBudgetPlan,
    PersistedBudgetPlanVersion,
)
from trip_planner.persistence.models.session import PersistedPlanningSessionState
from trip_planner.persistence.models.trip import PersistedTrip


@pytest.fixture
def budget_session(tmp_path: Path) -> Iterator[Session]:
    engine = create_engine(f"sqlite:///{tmp_path / 'budget.db'}")
    Base.metadata.create_all(engine)
    try:
        with Session(engine, expire_on_commit=False) as session:
            session.add(
                UserAccount(
                    user_id="owner",
                    email="owner@example.com",
                    display_name="Owner",
                    password_hash="",
                )
            )
            session.flush()
            session.add(
                PersistedTrip(trip_id="trip", user_id="owner", title="Trip", mode="leisure")
            )
            session.commit()
            yield session
    finally:
        engine.dispose()


def _request(currency: str, amount: float) -> BudgetPlanUpsertRequest:
    return BudgetPlanUpsertRequest.model_validate(
        {
            "title": f"{currency} plan",
            "currency": currency,
            "scenario_budgets": [
                {
                    "title": "Baseline",
                    "allocations": [
                        {
                            "category_key": "food",
                            "label": "Food",
                            "planned_amount": amount,
                            "currency": currency,
                        }
                    ],
                }
            ],
        }
    )


def _snapshot(session: Session) -> dict[str, list[dict]]:
    return {
        model.__tablename__: [
            dict(row)
            for row in session.execute(
                select(model.__table__).order_by(*model.__table__.primary_key)
            ).mappings()
        ]
        for model in (
            PersistedBudgetPlan,
            PersistedBudgetPlanVersion,
            PersistedActualSpendEvent,
            PersistedTrip,
            PersistedPlanningSessionState,
        )
    }


def test_currency_rejection_precedes_any_sql_mutation(budget_session: Session) -> None:
    user = AuthenticatedUser(user_id="owner", email="owner@example.com", display_name="Owner")
    initial = save_workspace_budget("trip", _request("USD", 150), user, budget_session)
    assert initial.budget_plan is not None
    budget_session.add(
        PersistedActualSpendEvent(
            spend_event_id="lunch",
            trip_id="trip",
            budget_plan_id="budget-plan:trip",
            category_key="food",
            amount=Decimal("30.50"),
            currency="USD",
            occurred_at="2026-11-17T00:00:00Z",
            source_kind="manual",
            source_context="Lunch",
        )
    )
    budget_session.commit()
    before = _snapshot(budget_session)
    statements: list[str] = []

    def record_statement(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement.strip().split()[0].upper())

    engine = budget_session.get_bind()
    event.listen(engine, "before_cursor_execute", record_statement)
    try:
        with pytest.raises(HTTPException) as rejected:
            save_workspace_budget("trip", _request("EUR", 200), user, budget_session)
        assert rejected.value.status_code == 422
        assert "must match all recorded spend currencies" in rejected.value.detail
        assert not budget_session.new
        assert not budget_session.dirty
        assert not {"INSERT", "UPDATE", "DELETE"}.intersection(statements)
    finally:
        event.remove(engine, "before_cursor_execute", record_statement)

    # A separate session checks persisted rows without the summary guard or a rollback.
    with Session(engine) as reader:
        assert _snapshot(reader) == before
        payload = get_workspace_budget_payload(reader, user=user, trip_id="trip")
        assert payload["spend_events"][0]["spend_event_id"] == "lunch"
        assert payload["summary"]["planned_total"] == 150
        assert payload["summary"]["actual_total"] == 30.5
        assert payload["summary"]["remaining_total"] == 119.5
        assert payload["summary"]["version_count"] == 1
