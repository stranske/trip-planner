"""Acceptance tests for the opt-in synthetic demo seed (issue #1260)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from scripts.seed_demo_data import (
    DEMO_BUSINESS_TITLE,
    DEMO_EMAIL,
    DEMO_LEISURE_TITLE,
    DEMO_PASSWORD,
    SEED_ENV_FLAG,
    _ensure_demo_user,
    main,
    seed_demo_data,
)
from trip_planner.app.main import create_app
from trip_planner.persistence.db import (
    ensure_database_ready,
    get_session_factory,
    reset_database_state,
)
from trip_planner.persistence.models.account import UserAccount


@pytest.fixture
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'seed.db'}")
    reset_database_state()
    ensure_database_ready()
    yield
    reset_database_state()


def test_demo_seed_populates_workspace(temp_db: None, monkeypatch: pytest.MonkeyPatch) -> None:
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

        leisure_response = client.get(f"/api/workspace/{result.leisure_trip_id}")
        assert leisure_response.status_code == 200, leisure_response.text
        payload = leisure_response.json()

        # Ranked scenario comparison must be populated, not a missing-* partial.
        comparison = payload["runtime_scenario_comparison"]
        assert comparison["scenarios"], "expected ranked scenarios, got empty comparison"
        assert comparison["lead_scenario_id"] == comparison["scenarios"][0]["scenario_id"]

        # At least one inventory bundle must be assembled.
        assert payload["inventory_summary"]["bundle_count"] >= 1
        assert payload["inventory_summary"]["bundles"]

        # Deterministic fallback planner -- no external LLM was invoked.
        assert payload["runtime_state"]["status"] == "ready"
        leisure_trip = payload["trip_record"]["trip"]
        assert leisure_trip["title"] == DEMO_LEISURE_TITLE
        assert leisure_trip["trip_frame"]["primary_regions"] == ["Kyoto", "Osaka"]
        assert leisure_trip["trip_frame"]["duration_days"] == 7
        assert any(
            scenario["title"] == "Kyoto runtime bundle"
            for scenario in comparison["scenarios"]
        )

        business_response = client.get(f"/api/workspace/{result.business_trip_id}")
        assert business_response.status_code == 200, business_response.text
        business_payload = business_response.json()
        business_trip = business_payload["trip_record"]["trip"]
        assert business_trip["title"] == DEMO_BUSINESS_TITLE
        assert business_trip["trip_frame"]["primary_regions"] == ["Washington DC"]
        assert business_trip["trip_frame"]["duration_days"] == 3
        assert business_payload["runtime_scenario_comparison"]["scenarios"]
        assert any(
            scenario["title"] == "Washington DC runtime bundle"
            for scenario in business_payload["runtime_scenario_comparison"]["scenarios"]
        )


def test_demo_seed_is_noop_when_flag_unset(temp_db: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SEED_ENV_FLAG, raising=False)

    result = seed_demo_data()
    assert result is None

    with get_session_factory()() as db_session:
        users = db_session.scalars(select(UserAccount)).all()
    assert users == [], "seed must not create any account when the flag is unset"


def test_demo_seed_is_idempotent(temp_db: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Re-running the seed reuses the existing account and trips (no duplicates)."""
    monkeypatch.setenv(SEED_ENV_FLAG, "1")

    first = seed_demo_data()
    assert first is not None

    second = seed_demo_data()
    assert second is not None

    # Same trip IDs on re-run — idempotent.
    assert second.leisure_trip_id == first.leisure_trip_id
    assert second.business_trip_id == first.business_trip_id

    # Still only one account.
    with get_session_factory()() as db_session:
        users = db_session.scalars(select(UserAccount)).all()
    assert len(users) == 1


def test_workspace_urls(temp_db: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SEED_ENV_FLAG, "1")
    result = seed_demo_data()
    assert result is not None

    urls = result.workspace_urls()
    assert len(urls) == 2
    assert urls[0] == f"/workspace/{result.leisure_trip_id}"
    assert urls[1] == f"/workspace/{result.business_trip_id}"


def test_main_without_flag(
    temp_db: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.delenv(SEED_ENV_FLAG, raising=False)

    exit_code = main()
    assert exit_code == 0
    out = capsys.readouterr().out
    assert SEED_ENV_FLAG in out


def test_main_with_flag(
    temp_db: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setenv(SEED_ENV_FLAG, "1")

    exit_code = main()
    assert exit_code == 0
    out = capsys.readouterr().out
    assert DEMO_EMAIL in out
    assert DEMO_PASSWORD in out
    assert "/workspace/" in out


def test_ensure_demo_user_reuses_existing_account(temp_db: None) -> None:
    """_ensure_demo_user returns the same user on second call via the 409 path."""
    with get_session_factory()() as session:
        first = _ensure_demo_user(session)
        second = _ensure_demo_user(session)
    assert first.user_id == second.user_id
    assert first.email == second.email
