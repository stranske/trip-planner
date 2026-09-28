from __future__ import annotations

import pytest

from trip_planner.integrations.tpp.portal_handoff import (
    TPPPortalHandoffConfigurationError,
    build_portal_fields,
    portal_action_url,
    snapshot_hash,
)


def _snapshot() -> dict:
    return {
        "schema_version": "tpp-portal-handoff/v1",
        "trip_id": "trip-1",
        "proposal_id": "proposal-1",
        "proposal_version": "v1",
        "scenario_id": "scenario-1",
        "execution_id": "execution-1",
        "traveler_name": "Morgan Planner",
        "trip": {
            "title": "Client visit",
            "summary": "Meet the client team",
            "origin": "ORD",
            "primary_regions": ["Washington, DC"],
            "start_date": "2026-10-12",
            "end_date": "2026-10-14",
        },
        "prices": [
            {
                "component": "transport",
                "label": "Transportation",
                "amount": 430.0,
                "currency": "USD",
                "note": "United.com quote",
                "source": {
                    "attributed_to": "Morgan Planner",
                    "captured_at": "2026-09-28",
                },
                "lowest_amount": None,
                "evidence_attested": False,
                "cabin_class": None,
                "flight_hours": None,
            }
        ],
        "verdict": {
            "status": "compliant",
            "outcome": "accepted",
            "blocking_codes": [],
        },
    }


def test_portal_fields_map_truthful_facts_without_inventing_zip_or_airfare() -> None:
    fields = build_portal_fields(_snapshot())

    assert fields["traveler_name"] == "Morgan Planner"
    assert fields["city_state"] == "Washington, DC"
    assert fields["departure_city_airport"] == "ORD"
    assert "destination_zip" not in fields
    assert "flight_cost" not in fields
    assert "United.com quote" in fields["notes"]
    assert "TPP recalculates policy" in fields["notes"]


def test_snapshot_hash_changes_when_a_price_changes() -> None:
    original = _snapshot()
    changed = _snapshot()
    changed["prices"][0]["amount"] = 431.0

    assert snapshot_hash(original) != snapshot_hash(changed)


def test_portal_action_url_accepts_origin_only_and_uses_fixed_path(monkeypatch) -> None:
    monkeypatch.setenv("TRIP_PLANNER_ENV", "production")
    monkeypatch.setenv("TPP_PORTAL_BASE_URL", "https://tpp.example")

    assert portal_action_url() == "https://tpp.example/portal/handoff"

    monkeypatch.setenv("TPP_PORTAL_BASE_URL", "https://tpp.example/attacker-path")
    with pytest.raises(TPPPortalHandoffConfigurationError, match="origin only"):
        portal_action_url()
