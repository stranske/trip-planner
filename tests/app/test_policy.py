import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.persistence.db import reset_database_state


def _fixture_path(name: str) -> Path:
    return (
        Path(__file__).resolve().parents[1] / "fixtures" / "integrations" / "tpp" / "policy" / name
    )


def _load_fixture(name: str) -> dict:
    return json.loads(_fixture_path(name).read_text(encoding="utf-8"))


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'policy.db'}")
    reset_database_state()
    app = create_app()

    with TestClient(app) as test_client:
        test_client.post(
            "/api/auth/signup",
            json={
                "email": "policy@example.com",
                "password": "password123",
                "display_name": "Policy Owner",
            },
        )
        yield test_client

    reset_database_state()


def test_workspace_policy_import_persists_constraint_set_and_readiness(client: TestClient) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Client policy sync",
            "summary": "Import policy inputs for the workspace.",
            "mode": "business",
            "trip_frame": {
                "start_date": "2026-05-04",
                "end_date": "2026-05-06",
                "duration_days": 3,
                "primary_regions": ["Chicago"],
            },
        },
    )
    trip_id = created.json()["trip"]["trip_id"]
    fixture = _load_fixture("standard_policy_sync.json")

    imported = client.put(
        f"/api/workspace/{trip_id}/policy",
        json={
            "request": fixture["request"],
            "response": fixture["response"],
            "source_kind": "tpp_sync",
            "tags": ["business-policy"],
            "notes": ["Imported from TPP fixture for workspace readiness."],
        },
    )

    assert imported.status_code == 200
    payload = imported.json()
    assert payload["policy_state"]["trip_id"] == trip_id
    assert payload["policy_state"]["policy_id"] == "policy-standard-2026-02"
    assert payload["summary"]["required_booking_channels"] == ["Navan", "Concur"]
    assert payload["policy_evaluation"]["status"] == "compliant"
    assert payload["proposal"]["constraint_set_id"] == "policy-standard-2026-02"

    reloaded = client.get(f"/api/workspace/{trip_id}/policy")
    assert reloaded.status_code == 200
    reloaded_payload = reloaded.json()
    assert reloaded_payload["policy_state"]["policy_state_id"] == f"policy-state:{trip_id}"
    assert "Persisted policy storage is limited" in reloaded_payload["policy_state"]["notes"][-2]


def test_workspace_policy_import_rejects_leisure_trip(client: TestClient) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Leisure trip",
            "summary": "Should not accept policy imports.",
            "mode": "leisure",
            "trip_frame": {"duration_days": 2, "primary_regions": ["Kyoto"]},
        },
    )
    trip_id = created.json()["trip"]["trip_id"]
    fixture = _load_fixture("standard_policy_sync.json")

    response = client.put(
        f"/api/workspace/{trip_id}/policy",
        json={
            "request": fixture["request"],
            "response": fixture["response"],
        },
    )

    assert response.status_code == 400
    assert "business trips" in response.json()["detail"]
