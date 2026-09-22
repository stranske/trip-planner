"""The gate: a traveller can supply a price, and only a supplied price appears.

Every assertion here reads the **served payload**, not an internal helper. An earlier gate
on this work asserted against a private function and stayed green while the product was
reverted to invented constants.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.persistence.db import ensure_database_ready, reset_database_state


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'prices.db'}")
    reset_database_state()
    ensure_database_ready()
    with TestClient(create_app()) as test_client:
        test_client.post(
            "/api/auth/signup",
            json={
                "email": "traveller@example.com",
                "password": "password123",
                "display_name": "Dana Chen",
            },
        )
        yield test_client
    reset_database_state()


def _create_trip(client: TestClient) -> str:
    response = client.post(
        "/api/trips",
        json={
            "title": "Chicago client review",
            "mode": "business",
            "start_date": "2026-10-05",
            "end_date": "2026-10-07",
            "primary_regions": ["Chicago"],
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["trip"]["trip_id"])


def _scenario_totals(client: TestClient, trip_id: str) -> list[dict[str, Any] | None]:
    workspace = client.get(f"/api/workspace/{trip_id}")
    assert workspace.status_code == 200, workspace.text
    comparison = workspace.json()["runtime_scenario_comparison"]
    return [row["metrics"]["estimated_total"] for row in comparison["scenarios"]]


def test_a_new_trip_has_no_price_at_all(client: TestClient) -> None:
    trip_id = _create_trip(client)

    payload = client.get(f"/api/workspace/{trip_id}/prices").json()
    assert payload["total"] is None
    assert payload["priced_component_count"] == 0
    assert all(component["typical_amount"] is None for component in payload["components"])
    # Zero is a price: it says the trip is free. Absent is not zero.
    assert all(component["typical_amount"] != 0 for component in payload["components"])


def test_an_entered_price_reaches_the_workspace_with_its_source(client: TestClient) -> None:
    trip_id = _create_trip(client)

    saved = client.put(
        f"/api/workspace/{trip_id}/prices",
        json={
            "component": "transport",
            "amount": 486.0,
            "currency": "USD",
            "note": "United.com, booked class economy",
        },
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["total"]["typical_amount"] == 486.0
    source = body["total"]["price_source"]
    assert source["kind"] == "manual"
    assert source["attributed_to"] == "Dana Chen"
    assert source["captured_at"]

    # The figure must reach the surface a traveller and an approver actually read.
    totals = _scenario_totals(client, trip_id)
    assert totals, "the workspace served no scenarios"
    for total in totals:
        assert isinstance(total, dict)
        assert total["typical_amount"] == 486.0
        assert total["price_source"]["attributed_to"] == "Dana Chen"


def test_components_sum_and_the_total_names_who_entered_it(client: TestClient) -> None:
    trip_id = _create_trip(client)
    for component, amount in (("transport", 486.0), ("lodging", 612.0), ("activities", 140.0)):
        response = client.put(
            f"/api/workspace/{trip_id}/prices",
            json={"component": component, "amount": amount},
        )
        assert response.status_code == 200, response.text

    payload = client.get(f"/api/workspace/{trip_id}/prices").json()
    assert payload["total"]["typical_amount"] == pytest.approx(1238.0)
    assert payload["priced_component_count"] == 3
    assert payload["unpriced_component_count"] == 1
    assert payload["total"]["price_source"]["attributed_to"] == "Dana Chen"


def test_a_withdrawn_price_leaves_nothing_behind(client: TestClient) -> None:
    trip_id = _create_trip(client)
    client.put(f"/api/workspace/{trip_id}/prices", json={"component": "lodging", "amount": 612.0})

    cleared = client.put(
        f"/api/workspace/{trip_id}/prices", json={"component": "lodging", "amount": None}
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["total"] is None

    # A stale figure left on an approval packet is the same defect as an invented one.
    for total in _scenario_totals(client, trip_id):
        assert total is None or total.get("typical_amount") is None


def test_the_planner_never_supplies_a_price_on_its_own(client: TestClient) -> None:
    """The regression that started all of this: figures appearing with no source.

    Two trips differing only in destination. Neither has an entered price, so neither may
    carry an amount — and in particular they must not carry the *same* invented amount,
    which is what a flat per-day rate produces.
    """

    first = _create_trip(client)
    second = client.post(
        "/api/trips",
        json={
            "title": "Reykjavik supplier visit",
            "mode": "business",
            "start_date": "2026-10-05",
            "end_date": "2026-10-07",
            "primary_regions": ["Reykjavik"],
        },
    )
    assert second.status_code == 201, second.text
    second_id = str(second.json()["trip"]["trip_id"])

    for trip_id in (first, second_id):
        for total in _scenario_totals(client, trip_id):
            amount = total.get("typical_amount") if isinstance(total, dict) else None
            assert amount is None, f"{trip_id} carried an unsourced amount: {amount!r}"


def test_an_unknown_component_is_refused(client: TestClient) -> None:
    trip_id = _create_trip(client)
    response = client.put(
        f"/api/workspace/{trip_id}/prices",
        json={"component": "bribes", "amount": 100.0},
    )
    assert response.status_code == 422


def test_a_negative_price_is_refused(client: TestClient) -> None:
    trip_id = _create_trip(client)
    response = client.put(
        f"/api/workspace/{trip_id}/prices",
        json={"component": "transport", "amount": -5.0},
    )
    assert response.status_code == 422


def test_another_users_trip_is_not_priceable(client: TestClient) -> None:
    trip_id = _create_trip(client)
    client.post("/api/auth/logout")
    client.post(
        "/api/auth/signup",
        json={
            "email": "someone-else@example.com",
            "password": "password123",
            "display_name": "Someone Else",
        },
    )
    response = client.put(
        f"/api/workspace/{trip_id}/prices",
        json={"component": "transport", "amount": 486.0},
    )
    assert response.status_code == 404
