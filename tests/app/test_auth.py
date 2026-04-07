from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.persistence.db import reset_database_state


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv(
        "TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'trip-planner.db'}"
    )
    reset_database_state()
    app = create_app()

    with TestClient(app) as test_client:
        yield test_client

    reset_database_state()


def test_signup_creates_account_sets_cookie_and_restores_session(
    client: TestClient,
) -> None:
    signup = client.post(
        "/api/auth/signup",
        json={
            "email": "owner@example.com",
            "password": "password123",
            "display_name": "Owner",
        },
    )

    assert signup.status_code == 201
    assert signup.json()["user"] == {
        "user_id": signup.json()["user"]["user_id"],
        "email": "owner@example.com",
        "display_name": "Owner",
    }
    assert "trip_planner_session" in signup.cookies

    session = client.get("/api/auth/session")

    assert session.status_code == 200
    assert session.json()["user"]["email"] == "owner@example.com"


def test_login_logout_and_workspace_auth_gate(client: TestClient) -> None:
    assert client.get("/api/workspace/trip-leisure-kyoto-draft").status_code == 401

    client.post(
        "/api/auth/signup",
        json={
            "email": "traveler@example.com",
            "password": "password123",
            "display_name": "Traveler",
        },
    )
    client.post("/api/auth/logout")

    login = client.post(
        "/api/auth/login",
        json={
            "email": "traveler@example.com",
            "password": "password123",
        },
    )
    assert login.status_code == 200

    workspace = client.get("/api/workspace/trip-leisure-kyoto-draft")
    assert workspace.status_code == 200
    assert (
        workspace.json()["trip_record"]["trip"]["trip_id"] == "trip-leisure-kyoto-draft"
    )

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 200
    assert logout.json() == {"signed_out": True}
    assert client.get("/api/auth/session").status_code == 401
