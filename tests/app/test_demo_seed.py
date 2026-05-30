"""Acceptance tests for the opt-in synthetic demo seed (issue #1260)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from trip_planner.app.main import create_app
from trip_planner.persistence.db import (
    ensure_database_ready,
    get_session_factory,
    reset_database_state,
)
from trip_planner.persistence.models.account import UserAccount

from scripts.seed_demo_data import (
    DEMO_EMAIL,
    DEMO_PASSWORD,
    SEED_ENV_FLAG,
    seed_demo_data,
)


@pytest.fixture
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'seed.db'}")
    reset_database_state()
    ensure_database_ready()
    yield
    reset_database_state()


def test_demo_seed_populates_workspace(
    temp_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(SEED_ENV_FLAG, "1")

    result = seed_demo_data()
    assert result is not None
    assert result.leisure_trip_id and result.business_trip_id

    app = create_app()
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
        )
        assert login.status_code == 200, login.text

        response = client.get(f"/api/workspace/{result.leisure_trip_id}")
        assert response.status_code == 200, response.text
        payload = response.json()

        # Ranked scenario comparison must be populated, not a missing-* partial.
        comparison = payload["runtime_scenario_comparison"]
        assert comparison["scenarios"], "expected ranked scenarios, got empty comparison"
        assert comparison["lead_scenario_id"] == comparison["scenarios"][0]["scenario_id"]

        # At least one inventory bundle must be assembled.
        assert payload["inventory_summary"]["bundle_count"] >= 1
        assert payload["inventory_summary"]["bundles"]

        # Deterministic fallback planner -- no external LLM was invoked.
        assert payload["runtime_state"]["status"] == "ready"


def test_demo_seed_is_noop_when_flag_unset(
    temp_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(SEED_ENV_FLAG, raising=False)

    result = seed_demo_data()
    assert result is None

    with get_session_factory()() as db_session:
        users = db_session.scalars(select(UserAccount)).all()
    assert users == [], "seed must not create any account when the flag is unset"
