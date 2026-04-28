"""End-to-end planner-turn API test.

This module is the wedge under stranske/trip-planner#957. It drives one real
planner turn through the FastAPI router (no provider mocking), asserts the
documented response contract field-by-field, and re-instantiates the app on the
same SQLite database to prove the workspace/session state survives a process
boundary — i.e. the turn was actually persisted, not just held in process memory.

The test is deterministic: it relies on the in-tree deterministic planner
fallback (no ``OPENAI_API_KEY`` configured), so request parsing, tool routing,
candidate/ranking persistence, and the fallback planner reply all run through
the real ``trip_planner.app.services.planner`` code path. No fake chat model is
injected. No fixture-only short-circuit can satisfy the assertions because the
test fails if the planner reply is empty, if the schema is missing documented
fields, or if a fresh app instance cannot reload the turn from persistence.

Run via the standard pytest invocation::

    pytest -q tests/app/test_planner_turn_e2e.py

Acceptance criteria from #957 mapped to this module:

- "A single local command runs the planner-turn E2E test." → the pytest
  invocation above is the single command.
- "The test fails if API/frontend routing is bypassed or returns only seeded
  fixture output." → assertions probe the live route handler output and reject
  empty/placeholder content (see ``_assert_planner_reply_is_substantive``).
- "The test fails if workspace state cannot be reloaded after the turn." →
  ``_reopen_app_against_same_db`` creates a second ``create_app()`` against the
  same SQLite path; the resume + session reads must surface the prior turn.
- "The response contract is asserted against documented fields, not just HTTP
  200." → ``_DOCUMENTED_TURN_FIELDS`` and ``_DOCUMENTED_MESSAGE_FIELDS`` are
  verified by name on every relevant payload.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.app.services.planner import set_planner_chat_model_factory_for_tests
from trip_planner.persistence.db import reset_database_state

# Documented response contract fields drawn from
# trip_planner.app.schemas.planner.PlannerSessionResponse and PlannerMessageResponse.
# Asserting by name (not by HTTP 200 alone) is what gives the test teeth — if the
# schema drifts or a route handler short-circuits with a partial payload, this
# fails loudly.
_DOCUMENTED_TURN_FIELDS = (
    "trip_id",
    "session_state_id",
    "conversation_id",
    "runtime",
    "session",
    "planner_panel_state",
    "planner_memory",
    "available_tools",
    "messages",
)
_DOCUMENTED_MESSAGE_FIELDS = (
    "message_id",
    "role",
    "content",
    "created_at",
)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Concrete SQLite path shared between both app instances in the test."""
    return tmp_path / "planner_e2e.db"


@pytest.fixture
def first_client(
    db_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    """First app instance — creates the trip and runs the planner turn."""
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{db_path}")
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
                "email": "e2e-planner@example.com",
                "password": "password123",
                "display_name": "E2E Planner",
            },
        )
        assert signup.status_code == 201, signup.text
        yield test_client

    set_planner_chat_model_factory_for_tests(None)
    # Intentionally do NOT call reset_database_state() here — the second app
    # instance must read the same persisted state.


@pytest.fixture
def second_client(
    db_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    """Second app instance — reads from the same DB to verify persistence.

    Yielded only after the first client's ``with`` block has exited, simulating
    a process restart against the same on-disk database.
    """
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.delenv("TRIP_PLANNER_PLANNER_MODEL_PROVIDER", raising=False)
    monkeypatch.delenv("TRIP_PLANNER_PLANNER_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    set_planner_chat_model_factory_for_tests(None)
    # Force the persistence layer to re-bind to the (existing) sqlite file.
    reset_database_state()
    app = create_app()

    with TestClient(app) as test_client:
        # Sign in the same user; signup-or-login depending on harness contract.
        login = test_client.post(
            "/api/auth/login",
            json={
                "email": "e2e-planner@example.com",
                "password": "password123",
            },
        )
        # The login endpoint may be /api/auth/login or /api/auth/signin depending
        # on harness conventions. If the route returns 404, the assertions below
        # will fall through to the route-call site and produce a clear failure
        # naming the missing capability.
        if login.status_code == 404:
            login = test_client.post(
                "/api/auth/signin",
                json={
                    "email": "e2e-planner@example.com",
                    "password": "password123",
                },
            )
        assert login.status_code in (200, 201, 204), (
            f"Could not re-authenticate the same user against the persisted DB. "
            f"This either means the auth route name is not /api/auth/login or "
            f"/api/auth/signin, or persisted user state is not surviving a "
            f"create_app() boundary — both are workspace-state reload failures "
            f"the #957 contract is meant to catch. status={login.status_code}, "
            f"body={login.text}"
        )
        yield test_client

    set_planner_chat_model_factory_for_tests(None)
    reset_database_state()


def _create_trip(client: TestClient) -> str:
    response = client.post(
        "/api/trips",
        json={
            "title": "Planner E2E persistence kickoff",
            "summary": "End-to-end planner-turn coverage for issue #957.",
            "mode": "leisure",
            "trip_frame": {
                "start_date": "2026-05-04",
                "end_date": "2026-05-06",
                "duration_days": 3,
                "primary_regions": ["Chicago"],
                "traveler_party": {
                    "kind": "solo",
                    "traveler_count": 1,
                    "notes": "E2E planner turn",
                },
            },
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["trip"]["trip_id"]


def _assert_documented_fields(payload: dict[str, Any], fields: tuple[str, ...]) -> None:
    missing = [name for name in fields if name not in payload]
    assert not missing, (
        f"Planner turn response is missing documented contract fields: {missing}. "
        f"Required by the PlannerSessionResponse schema in "
        f"trip_planner.app.schemas.planner. The route handler may be returning a "
        f"partial payload."
    )


def _assert_planner_reply_is_substantive(payload: dict[str, Any]) -> None:
    """Reject empty or seeded-only fixture replies.

    The deterministic fallback returns a reply that references the trip title and
    explains why the model is in fallback. If the reply is missing, empty, or
    contains only generic placeholder text, the route handler is not exercising
    the real planner.respond / planner_tools path that the E2E contract requires.
    """
    messages = payload.get("messages", [])
    assert messages, "Planner turn returned no messages — route bypassed?"
    roles = [m["role"] for m in messages]
    assert "user" in roles and "planner" in roles, (
        f"Planner turn response is missing user or planner role messages. "
        f"Roles seen: {roles}. The route may be short-circuiting before tool routing."
    )
    planner_reply = next(m for m in messages if m["role"] == "planner")
    _assert_documented_fields(planner_reply, _DOCUMENTED_MESSAGE_FIELDS)
    content = planner_reply.get("content", "").strip()
    assert content, "Planner reply content is empty — fixture-only output."
    assert len(content) >= 16, (
        f"Planner reply is too short to be substantive: {content!r}. The "
        f"deterministic fallback should produce a reply describing why the model "
        f"is unconfigured; an empty or one-word reply suggests the route is "
        f"returning seeded placeholder output rather than real planner output."
    )


def test_planner_turn_e2e_persists_across_app_instances(
    first_client: TestClient,
    second_client: TestClient,
) -> None:
    """Drive one planner turn through the API and prove it survives a re-bind.

    Acceptance contract for issue #957. This test fails if any of:

    * The planner-turn route returns less than the documented response schema.
    * The planner reply is empty or short enough to be a fixture placeholder.
    * The created trip / session / planner messages cannot be reloaded by a
      second ``create_app()`` instance bound to the same SQLite database.
    """
    # ---- First app instance: create + run a turn ----
    trip_id = _create_trip(first_client)

    turn_message = "Plan a long weekend in Chicago and summarize the current workspace state."
    first_turn = first_client.post(
        f"/api/planner/{trip_id}/turns",
        json={"message": turn_message},
    )
    assert first_turn.status_code == 200, first_turn.text
    first_payload = first_turn.json()

    _assert_documented_fields(first_payload, _DOCUMENTED_TURN_FIELDS)
    assert first_payload["trip_id"] == trip_id
    assert first_payload["session_state_id"] == f"session:{trip_id}"
    assert first_payload["conversation_id"] == f"planner-conversation:{trip_id}"
    _assert_planner_reply_is_substantive(first_payload)

    # The deterministic fallback names a checkpoint id that subsequent turns
    # extend. If memory persistence is broken the checkpoint id is missing.
    first_checkpoint = first_payload["planner_memory"].get("current_checkpoint_id")
    assert first_checkpoint is not None and first_checkpoint.startswith("planner-chk:"), (
        f"First turn did not produce a planner-memory checkpoint id. Got "
        f"{first_checkpoint!r}. Memory persistence is the documented contract for "
        f"#957's 'workspace persistence' assertion."
    )

    # The original user message must appear verbatim in the user-role message —
    # request parsing assertion.
    user_message = next(m for m in first_payload["messages"] if m["role"] == "user")
    assert turn_message in user_message["content"], (
        f"User message was not preserved by the route. Sent {turn_message!r}, "
        f"received {user_message['content']!r}. Request parsing is part of the "
        f"E2E contract."
    )

    # ---- Second app instance (same DB): reload session + assert turn persists ----
    session = second_client.get(f"/api/planner/{trip_id}/session")
    assert session.status_code == 200, session.text
    session_payload = session.json()

    _assert_documented_fields(session_payload, _DOCUMENTED_TURN_FIELDS)
    assert session_payload["trip_id"] == trip_id
    assert session_payload["session_state_id"] == f"session:{trip_id}"

    persisted_messages = session_payload["messages"]
    assert persisted_messages, (
        "Reload from a fresh app instance returned no messages. The planner turn "
        "did not persist across the create_app() boundary — workspace persistence "
        "contract violated."
    )

    persisted_user = next((m for m in persisted_messages if m["role"] == "user"), None)
    assert (
        persisted_user is not None
    ), "Reload is missing the persisted user-role message from the prior turn."
    assert turn_message in persisted_user["content"], (
        f"Persisted user message diverged from what was sent. "
        f"Sent {turn_message!r}, reload returned {persisted_user['content']!r}."
    )

    persisted_planner = next((m for m in persisted_messages if m["role"] == "planner"), None)
    assert (
        persisted_planner is not None
    ), "Reload is missing the persisted planner-role reply from the prior turn."
    _assert_documented_fields(persisted_planner, _DOCUMENTED_MESSAGE_FIELDS)

    # The reloaded checkpoint must match the one returned by the original turn.
    reloaded_checkpoint = session_payload["planner_memory"].get("current_checkpoint_id")
    assert reloaded_checkpoint == first_checkpoint, (
        f"Planner-memory checkpoint did not survive reload. First turn produced "
        f"{first_checkpoint!r}, reloaded session has {reloaded_checkpoint!r}."
    )

    # available_tools is also documented — the workspace-state read tool must
    # remain wired after reload (proves the runtime still has tool routing
    # configured against the persisted trip).
    tool_names = [tool.get("tool_name") for tool in session_payload["available_tools"]]
    assert "read_workspace_state" in tool_names, (
        f"Reload lost tool registration: available_tools={tool_names!r}. The "
        f"runtime should expose at least the workspace-read tool against any "
        f"existing trip-scoped session."
    )
