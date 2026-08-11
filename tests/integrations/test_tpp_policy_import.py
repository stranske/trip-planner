"""End-to-end contract checks for importing authoritative TPP policy verdicts."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.persistence.db import reset_database_state


def _load_policy_fixture(name: str) -> dict[str, object]:
    path = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "integrations"
        / "tpp"
        / "policy"
        / name
    )
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def workspace_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    monkeypatch.setenv(
        "TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'policy-import.db'}"
    )
    reset_database_state()
    with TestClient(create_app()) as client:
        signup = client.post(
            "/api/auth/signup",
            json={
                "email": "policy-import@example.test",
                "password": "password123",
                "display_name": "TPP policy import",
            },
        )
        assert signup.status_code == 201, signup.text
        yield client
    reset_database_state()


def test_failing_policy_status_is_not_compliant(workspace_client: TestClient) -> None:
    """A current TPP denial remains non-compliant with its rule-level explanation."""

    trip = workspace_client.post(
        "/api/trips",
        json={
            "title": "Denied TPP policy import",
            "summary": "Verify the authoritative TPP denial is preserved.",
            "mode": "business",
            "trip_frame": {
                "start_date": "2026-05-04",
                "end_date": "2026-05-06",
                "duration_days": 2,
                "primary_regions": ["Chicago"],
            },
        },
    )
    assert trip.status_code == 201, trip.text
    trip_id = trip.json()["trip"]["trip_id"]
    fixture = _load_policy_fixture("standard_policy_sync.json")
    response = fixture["response"]
    assert isinstance(response, dict)
    result_payload = response["result_payload"]
    assert isinstance(result_payload, dict)
    context = result_payload["organization_context"]
    assert isinstance(context, dict)
    context["policy_status"] = "fail"
    context["blocking_issues"] = [
        {
            "code": "BUD-001",
            "summary": "Trip cost exceeds the approved budget cap.",
            "severity": "blocking",
        }
    ]

    imported = workspace_client.put(
        f"/api/workspace/{trip_id}/policy",
        json={"request": fixture["request"], "response": response},
    )

    assert imported.status_code == 200
    evaluation = imported.json()["policy_evaluation"]
    assert evaluation["status"] == "non_compliant"
    assert evaluation["failure_reasons"] == [
        {
            "code": "BUD-001",
            "message": "Trip cost exceeds the approved budget cap.",
            "severity": "blocking",
            "related_category": "policy_sync",
        }
    ]
