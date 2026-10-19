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
            "summary": "Two days on site with the client team.",
            "mode": "business",
            # The dates and destinations belong inside trip_frame. Sent flat they are
            # silently dropped and the API still answers 201, which produced a trip with
            # no destination and no dates while this gate looked like it was passing.
            "trip_frame": {
                "start_date": "2026-10-05",
                "end_date": "2026-10-07",
                "duration_days": 3,
                "primary_regions": ["Chicago"],
            },
        },
    )
    assert response.status_code == 201, response.text
    created = response.json()["trip"]
    assert created["trip_frame"]["primary_regions"] == [
        "Chicago"
    ], "the trip did not keep its destination, so this gate would be testing a blank trip"
    return str(created["trip_id"])


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


def test_omitted_currency_preserves_an_existing_eur_price_after_a_fresh_session(
    client: TestClient,
) -> None:
    trip_id = _create_trip(client)
    created = client.put(
        f"/api/workspace/{trip_id}/prices",
        json={"component": "lodging", "amount": 620.0, "currency": "EUR", "note": "Initial quote"},
    )
    assert created.status_code == 200, created.text
    assert created.json()["components"][1]["currency"] == "EUR"

    updated = client.put(
        f"/api/workspace/{trip_id}/prices",
        json={"component": "lodging", "amount": 620.0, "note": "Corrected hotel note"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["components"][1]["currency"] == "EUR"
    assert updated.json()["components"][1]["note"] == "Corrected hotel note"

    amount_edit = client.put(
        f"/api/workspace/{trip_id}/prices",
        json={"component": "lodging", "amount": 640.0, "note": "Revised amount"},
    )
    assert amount_edit.status_code == 200, amount_edit.text
    assert amount_edit.json()["components"][1]["currency"] == "EUR"

    client.post("/api/auth/logout")
    signed_in = client.post(
        "/api/auth/login",
        json={"email": "traveller@example.com", "password": "password123"},
    )
    assert signed_in.status_code == 200, signed_in.text
    reread = client.get(f"/api/workspace/{trip_id}/prices")
    assert reread.status_code == 200, reread.text
    lodging = next(item for item in reread.json()["components"] if item["component"] == "lodging")
    assert lodging["currency"] == "EUR"


def test_new_prices_default_to_usd_and_explicit_currency_changes_still_apply(
    client: TestClient,
) -> None:
    trip_id = _create_trip(client)
    created = client.put(
        f"/api/workspace/{trip_id}/prices", json={"component": "lodging", "amount": 620.0}
    )
    assert created.status_code == 200, created.text
    assert created.json()["components"][1]["currency"] == "USD"

    changed = client.put(
        f"/api/workspace/{trip_id}/prices",
        json={"component": "lodging", "amount": 620.0, "currency": "EUR"},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["components"][1]["currency"] == "EUR"


def test_mixed_currency_prices_still_refuse_to_sum(client: TestClient) -> None:
    trip_id = _create_trip(client)
    for component, amount, currency in (("transport", 486.0, "USD"), ("lodging", 620.0, "EUR")):
        response = client.put(
            f"/api/workspace/{trip_id}/prices",
            json={"component": component, "amount": amount, "currency": currency},
        )
        assert response.status_code == 200, response.text
    assert client.get(f"/api/workspace/{trip_id}/prices").json()["total"] is None


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
            "summary": "Supplier site visit.",
            "mode": "business",
            "trip_frame": {
                "start_date": "2026-10-05",
                "end_date": "2026-10-07",
                "duration_days": 3,
                "primary_regions": ["Reykjavik"],
            },
        },
    )
    assert second.status_code == 201, second.text
    assert second.json()["trip"]["trip_frame"]["primary_regions"] == ["Reykjavik"]
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


def test_the_workspace_header_advances_once_a_price_is_entered(client: TestClient) -> None:
    """Issue 1840: after pricing a trip the header still said nothing had been planned."""

    trip_id = _create_trip(client)
    before = client.get(f"/api/workspace/{trip_id}").json()["view_model"]
    assert before["next_step"]["title"] == "Enter the prices you have"

    saved = client.put(
        f"/api/workspace/{trip_id}/prices",
        json={"component": "transport", "amount": 486.0, "currency": "USD", "note": "United"},
    )
    assert saved.status_code == 200, saved.text

    after = client.get(f"/api/workspace/{trip_id}").json()["view_model"]
    assert after["next_step"]["title"] == "Submit for approval"
    assert after["user_summary"]["headline"].startswith("Prices entered for 1 item(s).")
    assert "Nothing has been planned" not in after["user_summary"]["headline"]


_PRICE_EVIDENCE = {
    "component": "transport",
    "amount": 620.0,
    "currency": "USD",
    "lowest_amount": 500.0,
    "evidence_attested": True,
    "cabin_class": "economy",
    "flight_hours": 4.0,
}


def _approved_price_verdict(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, trip_id: str
) -> dict:
    """Use the existing fixture response seam; this is not live TPP evidence."""
    from tests.app.test_proposal import _load_fixture, _proposal_payload

    monkeypatch.setenv("TRIP_PLANNER_ALLOW_FIXTURE_TPP_RESPONSES", "true")
    submission = _load_fixture("proposal_submit_deferred.json")
    submission["request"].update(trip_id=trip_id, proposal_id=f"proposal:{trip_id}")
    submission["request"]["payload"]["proposal_ref"] = f"proposal:{trip_id}"
    response = client.put(
        f"/api/workspace/{trip_id}/proposal",
        json={
            "proposal": _proposal_payload(trip_id),
            "request": submission["request"],
            "response": submission["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )
    assert response.status_code == 200, response.text
    evaluation = _load_fixture("results", "approved_evaluation.json")
    evaluation["request"].update(trip_id=trip_id, proposal_id=f"proposal:{trip_id}")
    result = evaluation["response"]["result_payload"]
    result.update(trip_id=trip_id, proposal_id=f"proposal:{trip_id}")
    result["evaluation_result"]["proposal_id"] = f"proposal:{trip_id}"
    response = client.put(
        f"/api/workspace/{trip_id}/proposal/evaluation",
        json={
            "request": evaluation["request"],
            "response": evaluation["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )
    assert response.status_code == 200, response.text
    state = client.get(f"/api/workspace/{trip_id}").json()["proposal_state"]
    assert state["summary"]["approval_ready"] is True
    return state


@pytest.mark.parametrize(
    "change",
    [
        {"amount": 6200.0},
        {"currency": "EUR"},
        {"lowest_amount": 450.0},
        {"evidence_attested": False},
        {"cabin_class": "first"},
        {"flight_hours": 9.0},
        {"amount": None},
        {"component": "lodging", "amount": 200.0},
    ],
)
def test_material_price_edit_invalidates_saved_verdict(client, monkeypatch, change):
    trip_id = _create_trip(client)
    assert client.put(f"/api/workspace/{trip_id}/prices", json=_PRICE_EVIDENCE).status_code == 200
    _approved_price_verdict(client, monkeypatch, trip_id)
    changed = client.put(f"/api/workspace/{trip_id}/prices", json={**_PRICE_EVIDENCE, **change})
    assert changed.status_code == 200, changed.text
    assert client.get(f"/api/workspace/{trip_id}").json()["proposal_state"] is None
    # Only a new policy evaluation for the changed evidence restores readiness.
    if change.get("amount", 1) is not None:
        _approved_price_verdict(client, monkeypatch, trip_id)


def test_noop_price_save_does_not_invalidate_verdict(client, monkeypatch):
    trip_id = _create_trip(client)
    client.put(f"/api/workspace/{trip_id}/prices", json=_PRICE_EVIDENCE)
    before = _approved_price_verdict(client, monkeypatch, trip_id)
    for extra in [{}, {"note": "same fare, clearer description"}]:
        assert (
            client.put(
                f"/api/workspace/{trip_id}/prices", json={**_PRICE_EVIDENCE, **extra}
            ).status_code
            == 200
        )
        after = client.get(f"/api/workspace/{trip_id}").json()["proposal_state"]
        assert after["summary"]["approval_ready"] is True
        assert after["evaluation"] == before["evaluation"]


def test_late_saved_verdict_is_stale_for_changed_price_evidence(client, monkeypatch):
    from trip_planner.persistence.db import get_session_factory
    from trip_planner.persistence.models.trip_price import PersistedTripPrice

    trip_id = _create_trip(client)
    client.put(f"/api/workspace/{trip_id}/prices", json=_PRICE_EVIDENCE)
    _approved_price_verdict(client, monkeypatch, trip_id)
    # Model a late proposal write that raced the edit's transactional deletion.
    with get_session_factory()() as session:
        price = session.query(PersistedTripPrice).filter_by(trip_id=trip_id).one()
        price.amount = 6200
        session.commit()
    state = client.get(f"/api/workspace/{trip_id}").json()["proposal_state"]
    assert state["summary"]["approval_ready"] is False
    assert state["summary"]["evaluation_result_status"] == "stale"
    assert state["evaluation"]["evaluation_result"] is None
    assert state["follow_up"]["status"] == "stale"
    assert state["summary"]["follow_up_status"] == "stale"
    assert "Re-run" in state["summary"]["highlights"][0]
    from trip_planner.persistence.models.proposal import PersistedProposalState

    with get_session_factory()() as session:
        saved = session.query(PersistedProposalState).filter_by(trip_id=trip_id).one()
        assert saved.summary["follow_up"]["status"] == "resolved"


def test_price_invalidation_rolls_back_with_a_failed_commit(client, monkeypatch):
    from sqlalchemy.orm import Session

    trip_id = _create_trip(client)
    client.put(f"/api/workspace/{trip_id}/prices", json=_PRICE_EVIDENCE)
    _approved_price_verdict(client, monkeypatch, trip_id)

    def fail_commit(self):
        raise RuntimeError("injected price commit failure")

    with monkeypatch.context() as failure:
        failure.setattr(Session, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="injected price commit failure"):
            client.put(f"/api/workspace/{trip_id}/prices", json={**_PRICE_EVIDENCE, "amount": 7000})
    state = client.get(f"/api/workspace/{trip_id}").json()["proposal_state"]
    assert state["summary"]["approval_ready"] is True
    assert client.get(f"/api/workspace/{trip_id}/prices").json()["total"]["typical_amount"] == 620
