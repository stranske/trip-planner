"""Integration test for the canonical state seam (issue #960).

Demonstrates the single trip-scoped persisted state model across a planner
turn, planner-memory checkpoint, and TPP proposal lifecycle (submission +
evaluation + follow-up). Asserts every artifact survives a ``create_app()``
boundary on the same SQLite database — i.e. the canonical seam genuinely
persists, not just an in-memory cache.

The test fails if:

- a planner turn does not produce both a user-role and planner-role
  ``PersistedPlannerAction`` row keyed on the trip id
- a planner-memory checkpoint id is not generated
- a TPP proposal submission/evaluation does not produce a
  ``PersistedProposalState`` row keyed on the trip id
- any of those rows are missing after re-binding ``create_app()`` to the same
  on-disk database

Run with::

    pytest -q tests/integrations/test_canonical_state_seam.py

This test is the executable contract referenced by
``docs/contracts/canonical-state-seam.md``.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

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
from trip_planner.persistence.models.proposal import PersistedProposalState
from trip_planner.persistence.models.session import PersistedPlanningSessionState


def _fixture_path(*parts: str) -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "integrations"
        / "tpp"
        / Path(*parts)
    )


def _load_fixture(*parts: str) -> dict:
    return json.loads(_fixture_path(*parts).read_text(encoding="utf-8"))


def _proposal_payload(trip_id: str) -> dict:
    return {
        "proposal_id": f"proposal:{trip_id}",
        "trip_id": trip_id,
        "mode": "business",
        "traveler_context": {
            "employee_type": "employee",
            "traveler_experience": "frequent",
            "home_airport": "ORD",
            "loyalty_programs": ["United"],
            "mobility_or_access_needs": [],
        },
        "selected_options": [
            {
                "category": "airfare",
                "option_id": "flight-1",
                "label": "United 123",
                "vendor": "United",
                "booking_channel": "Navan",
                "estimated_cost": {
                    "currency": "USD",
                    "typical_amount": 620.0,
                    "min_amount": 620.0,
                    "max_amount": 620.0,
                },
                "justification_refs": ["fare-policy"],
            }
        ],
        "cost_summary": {
            "currency": "USD",
            "total_estimated_cost": 620.0,
            "category_estimates": {"airfare": 620.0},
            "notes": ["Costs include taxes."],
        },
        "comparables": [
            {
                "category": "airfare",
                "label": "Flexible fare",
                "vendor": "United",
                "booking_channel": "Concur",
                "estimated_cost": {
                    "currency": "USD",
                    "typical_amount": 710.0,
                    "min_amount": 710.0,
                    "max_amount": 710.0,
                },
                "notes": ["Refundable alternative."],
            }
        ],
        "approval_notes": ["Manager review required before booking."],
        "constraint_set_id": "policy-standard-2026-02",
    }


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "canonical_state_seam.db"


@pytest.fixture
def first_client(
    db_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    """First app instance — exercises the seam end-to-end."""
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.delenv("TRIP_PLANNER_PLANNER_MODEL_PROVIDER", raising=False)
    monkeypatch.delenv("TRIP_PLANNER_PLANNER_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    set_planner_chat_model_factory_for_tests(None)
    reset_database_state()
    app = create_app()

    with TestClient(app) as client:
        signup = client.post(
            "/api/auth/signup",
            json={
                "email": "seam@example.com",
                "password": "password123",
                "display_name": "Canonical Seam Owner",
            },
        )
        assert signup.status_code == 201, signup.text
        yield client

    set_planner_chat_model_factory_for_tests(None)
    # Intentionally do NOT call reset_database_state() — the second instance
    # must read the same on-disk SQLite database.


@pytest.fixture
def second_client(
    db_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    """Second app instance — re-binds to the same SQLite path to verify reload."""
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.delenv("TRIP_PLANNER_PLANNER_MODEL_PROVIDER", raising=False)
    monkeypatch.delenv("TRIP_PLANNER_PLANNER_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    set_planner_chat_model_factory_for_tests(None)
    reset_database_state()
    app = create_app()

    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={"email": "seam@example.com", "password": "password123"},
        )
        if login.status_code == 404:
            login = client.post(
                "/api/auth/signin",
                json={"email": "seam@example.com", "password": "password123"},
            )
        assert login.status_code in (200, 201, 204), (
            f"Could not re-authenticate same user against persisted DB. "
            f"Either the auth route is misnamed or the user state did not "
            f"survive create_app(). status={login.status_code}, body={login.text}"
        )
        yield client

    set_planner_chat_model_factory_for_tests(None)
    reset_database_state()


def test_canonical_state_seam_persists_planner_turn_and_proposal_lifecycle(
    first_client: TestClient,
    second_client: TestClient,
) -> None:
    """One trip carries planner-turn + checkpoint + proposal lifecycle through one DB.

    Drives every layer the canonical seam covers and proves each row survives
    a process restart against the same SQLite file. This is the executable
    contract for ``docs/contracts/canonical-state-seam.md`` and the
    "no shortcut path bypasses persistence" acceptance criterion of #960.
    """
    # ---- Phase 1: create a business trip and run a planner turn ----
    created = first_client.post(
        "/api/trips",
        json={
            "title": "Canonical state seam trip",
            "summary": "One trip exercising every persisted seam layer.",
            "mode": "business",
            "trip_frame": {
                "start_date": "2026-05-04",
                "end_date": "2026-05-06",
                "duration_days": 3,
                "primary_regions": ["Chicago"],
                "traveler_party": {
                    "kind": "solo",
                    "traveler_count": 1,
                    "notes": "Seam test traveler",
                },
            },
        },
    )
    assert created.status_code == 201, created.text
    trip_id = created.json()["trip"]["trip_id"]
    proposal_id = f"proposal:{trip_id}"

    turn_message = (
        "Plan a compliant business trip from ORD to MSN and summarize the workspace state."
    )
    turn = first_client.post(
        f"/api/planner/{trip_id}/turns",
        json={"message": turn_message},
    )
    assert turn.status_code == 200, turn.text
    turn_payload = turn.json()
    first_checkpoint_id = turn_payload["planner_memory"]["current_checkpoint_id"]
    assert first_checkpoint_id is not None and first_checkpoint_id.startswith("planner-chk:"), (
        f"Planner turn did not produce a planner-memory checkpoint id. "
        f"Got {first_checkpoint_id!r}. Memory persistence is part of the "
        f"canonical seam."
    )

    # ---- Phase 2: TPP proposal submission and evaluation ----
    submission_fixture = _load_fixture("proposal_submit_deferred.json")
    submission_fixture["request"]["trip_id"] = trip_id
    submission_fixture["request"]["proposal_id"] = proposal_id
    submission_fixture["request"]["payload"]["proposal_ref"] = proposal_id

    submitted = first_client.put(
        f"/api/workspace/{trip_id}/proposal",
        json={
            "proposal": _proposal_payload(trip_id),
            "request": submission_fixture["request"],
            "response": submission_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["proposal_state"]["summary"]["submission_status"] == "deferred"

    evaluation_fixture = _load_fixture("results", "approved_evaluation.json")
    evaluation_fixture["request"]["trip_id"] = trip_id
    evaluation_fixture["request"]["proposal_id"] = proposal_id
    evaluation_fixture["response"]["result_payload"]["trip_id"] = trip_id
    evaluation_fixture["response"]["result_payload"]["proposal_id"] = proposal_id
    evaluation_fixture["response"]["result_payload"]["evaluation_result"][
        "proposal_id"
    ] = proposal_id

    evaluated = first_client.put(
        f"/api/workspace/{trip_id}/proposal/evaluation",
        json={
            "request": evaluation_fixture["request"],
            "response": evaluation_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )
    assert evaluated.status_code == 200, evaluated.text
    evaluated_state = evaluated.json()["proposal_state"]
    assert evaluated_state["summary"]["approval_ready"] is True
    assert evaluated_state["follow_up"]["status"] == "resolved"

    # ---- Phase 3: assert every persistence layer has the trip's rows ----
    # This is the "single state model" assertion: one trip_id ties together
    # session, planner action, activity event, planner-memory, and proposal
    # state. If any of these layers ends up keyed on something else, the
    # seam is broken.
    with get_session_factory()() as db:
        session_state = db.get(PersistedPlanningSessionState, f"session:{trip_id}")
        assert session_state is not None, (
            f"Canonical seam broken: no PersistedPlanningSessionState row for "
            f"trip {trip_id!r} after a planner turn."
        )

        planner_actions = db.scalars(
            select(PersistedPlannerAction)
            .where(PersistedPlannerAction.trip_id == trip_id)
            .order_by(PersistedPlannerAction.occurred_at.asc())
        ).all()
        action_types = [a.action_type for a in planner_actions]
        assert "planner_user_turn" in action_types and "planner_response" in action_types, (
            f"Canonical seam broken: planner turn did not produce both "
            f"user-role and planner-role action rows. Got types={action_types!r}."
        )

        activity_events = db.scalars(
            select(PersistedActivityLogEvent)
            .where(PersistedActivityLogEvent.trip_id == trip_id)
        ).all()
        assert activity_events, (
            f"Canonical seam broken: planner turn did not produce activity log "
            f"events for trip {trip_id!r}."
        )

        checkpoint = db.get(PersistedPlannerCheckpoint, first_checkpoint_id)
        assert checkpoint is not None, (
            f"Canonical seam broken: planner-memory checkpoint "
            f"{first_checkpoint_id!r} was not persisted."
        )
        memory_artifacts = db.scalars(
            select(PersistedPlannerMemoryArtifact).where(
                PersistedPlannerMemoryArtifact.trip_id == trip_id
            )
        ).all()
        assert memory_artifacts, (
            f"Canonical seam broken: planner turn did not produce a "
            f"PersistedPlannerMemoryArtifact for trip {trip_id!r}."
        )

        proposal_states = db.scalars(
            select(PersistedProposalState).where(
                PersistedProposalState.trip_id == trip_id
            )
        ).all()
        assert proposal_states, (
            f"Canonical seam broken: proposal submission did not produce a "
            f"PersistedProposalState for trip {trip_id!r}."
        )
        proposal_state = proposal_states[0]
        assert proposal_state.proposal_id == proposal_id
        assert proposal_state.submission_status == "deferred"
        # ``evaluation_status`` carries the TPP execution status (e.g.
        # "succeeded"); the policy compliance verdict ("compliant" /
        # "non_compliant") lives inside the evaluation_record JSON. Both must
        # have transitioned past their pre-evaluation null state for the seam
        # to be intact.
        assert proposal_state.evaluation_status is not None, (
            "Canonical seam broken: evaluation_status did not transition off "
            "null after PUT /proposal/evaluation; the proposal lifecycle row "
            "is not being updated by the evaluation handler."
        )
        evaluation_record = proposal_state.evaluation_record or {}
        evaluation_result = evaluation_record.get("evaluation_result") or {}
        assert evaluation_result.get("status") == "compliant", (
            f"Canonical seam broken: evaluation_record JSON does not carry the "
            f"compliant verdict. evaluation_record.evaluation_result.status="
            f"{evaluation_result.get('status')!r}."
        )

    # ---- Phase 4: re-bind a fresh app instance and assert every layer reloads ----
    # The same five-table seam must be visible to a freshly authenticated client
    # with no in-memory state carrying over.
    session_reload = second_client.get(f"/api/planner/{trip_id}/session")
    assert session_reload.status_code == 200, session_reload.text
    session_payload = session_reload.json()
    assert session_payload["session_state_id"] == f"session:{trip_id}"
    assert session_payload["planner_memory"]["current_checkpoint_id"] == first_checkpoint_id, (
        f"Canonical seam broken on reload: planner-memory checkpoint id did "
        f"not survive create_app(). First instance had {first_checkpoint_id!r}, "
        f"reload returned "
        f"{session_payload['planner_memory'].get('current_checkpoint_id')!r}."
    )
    reload_messages = session_payload["messages"]
    assert reload_messages, (
        "Canonical seam broken on reload: planner turn messages did not survive "
        "create_app() boundary."
    )
    persisted_user = next((m for m in reload_messages if m["role"] == "user"), None)
    assert persisted_user is not None and turn_message in persisted_user["content"], (
        f"Canonical seam broken on reload: user message content did not "
        f"survive. Got {persisted_user!r}."
    )

    proposal_reload = second_client.get(f"/api/workspace/{trip_id}/proposal")
    assert proposal_reload.status_code == 200, proposal_reload.text
    reloaded_proposal = proposal_reload.json()["proposal_state"]
    assert reloaded_proposal["proposal"]["proposal_id"] == proposal_id
    assert reloaded_proposal["summary"]["approval_ready"] is True
    assert reloaded_proposal["follow_up"]["status"] == "resolved"
    reloaded_eval = reloaded_proposal.get("evaluation") or {}
    assert reloaded_eval.get("evaluation_result", {}).get("evaluation_id") == "eval-approved-001", (
        f"Canonical seam broken on reload: proposal evaluation did not survive "
        f"create_app() boundary. Got {reloaded_eval!r}."
    )
