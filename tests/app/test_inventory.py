from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.persistence.db import reset_database_state


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv(
        "TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'inventory.db'}"
    )
    reset_database_state()
    app = create_app()

    with TestClient(app) as test_client:
        test_client.post(
            "/api/auth/signup",
            json={
                "email": "inventory@example.com",
                "password": "password123",
                "display_name": "Inventory Owner",
            },
        )
        yield test_client

    reset_database_state()


def test_inventory_endpoint_returns_seeded_bundle_payload(client: TestClient) -> None:
    response = client.get("/api/inventory/trip-leisure-kyoto-draft")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trip_id"] == "trip-leisure-kyoto-draft"
    assert payload["bundle_count"] == 2
    assert payload["bundles"][0]["bundle_id"] == "bundle-osaka-gateway"
    assert payload["summary"]["bundles"][1]["title"] == "Kyoto cultural anchor"
    assert payload["summary"]["bundles"][1]["option_count"] == 3


def test_inventory_endpoint_returns_not_found_for_unknown_trip(client: TestClient) -> None:
    response = client.get("/api/inventory/trip-unknown")

    assert response.status_code == 404
