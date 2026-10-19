"""Shared sequential shutdown/rebind contract for persistence gates."""

from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.app.services.planner import set_planner_chat_model_factory_for_tests
from trip_planner.persistence import db as persistence_db
from trip_planner.persistence.db import reset_database_state


def assert_restart_caches_cleared() -> None:
    assert not persistence_db._ENGINE_CACHE
    assert not persistence_db._SESSION_FACTORY_CACHE
    assert not persistence_db._MIGRATED_URLS


@contextmanager
def sequential_restart_clients(db_path: Path, monkeypatch: pytest.MonkeyPatch, *, email: str):
    """Open each app sequentially against one file, with fresh authentication."""
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{db_path}")
    for name in (
        "TRIP_PLANNER_PLANNER_PROVIDER",
        "TRIP_PLANNER_PLANNER_MODEL_PROVIDER",
        "TRIP_PLANNER_PLANNER_MODEL",
        "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    set_planner_chat_model_factory_for_tests(None)
    reset_database_state()
    events: list[str] = []
    original_user = None

    @contextmanager
    def open_client(*, reload=False):
        nonlocal original_user
        expected = ["first_started", "first_closed", "caches_cleared"] if reload else []
        assert events == expected, "clients must not overlap or reuse pre-write caches"
        if reload:
            assert_restart_caches_cleared()
        with TestClient(create_app()) as client:
            events.append("second_started" if reload else "first_started")
            if reload:
                auth = client.post(
                    "/api/auth/login", json={"email": email, "password": "password123"}
                )
                assert auth.status_code == 200, auth.text
                assert auth.json()["user"] == original_user
            else:
                auth = client.post(
                    "/api/auth/signup",
                    json={
                        "email": email,
                        "password": "password123",
                        "display_name": "Persistence test owner",
                    },
                )
                assert auth.status_code == 201, auth.text
                original_user = auth.json()["user"]
            yield client
        events.append("second_closed" if reload else "first_closed")

    try:
        yield open_client, events
    finally:
        set_planner_chat_model_factory_for_tests(None)
        reset_database_state()
