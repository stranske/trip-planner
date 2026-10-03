"""Saved planner verdicts shared by local and optional TPP contract checks."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session

from trip_planner.app.routes.proposal import prepare_workspace_proposal_portal_handoff
from trip_planner.app.schemas.proposal import WorkspaceProposalHandoffRequest
from trip_planner.app.services.auth import AuthenticatedUser
from trip_planner.app.services.proposal import (
    save_workspace_proposal_evaluation,
    save_workspace_proposal_submission,
)
from trip_planner.app.services.trip_prices import save_trip_price
from trip_planner.app.services.trips import create_trip
from trip_planner.persistence.db import (
    ensure_database_ready,
    get_session_factory,
    reset_database_state,
)
from trip_planner.persistence.models.account import UserAccount


@pytest.fixture
def saved_portal_handoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[Session, AuthenticatedUser, str, dict[str, Any]]]:
    """Prepare the production route's form from a persisted trip, price and verdict.

    Only the policy evaluation uses the existing serialized TPP fixtures; the
    browser portal contract must still run against the real sibling application.
    """
    monkeypatch.setenv("TRIP_PLANNER_ENV", "test")
    monkeypatch.setenv("TPP_PORTAL_BASE_URL", "https://tpp.example")
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'handoff.db'}")
    ensure_database_ready()
    user = AuthenticatedUser("portal-contract-owner", "portal@example.test", "Morgan Planner")
    try:
        with get_session_factory()() as session:
            session.add(
                UserAccount(
                    user_id=user.user_id,
                    email=user.email,
                    display_name=user.display_name,
                    password_hash="unused",
                )
            )
            session.commit()
            trip = create_trip(
                session,
                user=user,
                title="Washington client visit",
                summary="Meet the client team",
                mode="business",
                origin="ORD",
                primary_regions=["Washington, DC"],
                start_date="2026-10-12",
                end_date="2026-10-14",
                duration_days=3,
                traveler_kind="solo",
                traveler_count=1,
                traveler_notes="",
            )
            trip_id = trip["trip_id"]
            proposal_id = f"proposal:{trip_id}"
            save_trip_price(
                session,
                user=user,
                trip_id=trip_id,
                component="transport",
                amount=430.0,
                note="United.com quote",
            )
            fixtures = Path(__file__).resolve().parents[1] / "fixtures" / "integrations" / "tpp"
            submission = json.loads((fixtures / "proposal_submit_deferred.json").read_text())
            submission["request"].update(trip_id=trip_id, proposal_id=proposal_id)
            submission["request"]["payload"]["proposal_ref"] = proposal_id
            proposal = {
                "proposal_id": proposal_id,
                "trip_id": trip_id,
                "mode": "business",
                "traveler_context": {
                    "employee_type": "employee",
                    "traveler_experience": "frequent",
                    "home_airport": "ORD",
                },
                "selected_options": [
                    {
                        "category": "airfare",
                        "option_id": "flight-1",
                        "label": "United flight",
                        "vendor": "United",
                        "booking_channel": "Navan",
                        "estimated_cost": {
                            "currency": "USD",
                            "typical_amount": 430.0,
                            "min_amount": 430.0,
                            "max_amount": 430.0,
                        },
                    }
                ],
                "cost_summary": {
                    "currency": "USD",
                    "total_estimated_cost": 430.0,
                    "category_estimates": {"airfare": 430.0},
                },
            }
            save_workspace_proposal_submission(
                session,
                user=user,
                trip_id=trip_id,
                proposal_payload=proposal,
                request_payload=submission["request"],
                response_payload=submission["response"],
                proposal_version="proposal-v3",
                scenario_id=None,
            )
            evaluation = json.loads((fixtures / "results" / "approved_evaluation.json").read_text())
            evaluation["request"].update(trip_id=trip_id, proposal_id=proposal_id)
            result = evaluation["response"]["result_payload"]
            result.update(trip_id=trip_id, proposal_id=proposal_id, scenario_id=None)
            result["evaluation_result"]["proposal_id"] = proposal_id
            save_workspace_proposal_evaluation(
                session,
                user=user,
                trip_id=trip_id,
                request_payload=evaluation["request"],
                response_payload=evaluation["response"],
                proposal_version="proposal-v3",
                scenario_id=None,
            )
            handoff = prepare_workspace_proposal_portal_handoff(
                trip_id, WorkspaceProposalHandoffRequest(), user, session
            ).model_dump()
            yield session, user, trip_id, handoff
    finally:
        reset_database_state()
