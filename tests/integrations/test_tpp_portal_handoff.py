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


def test_combined_transport_amount_is_not_mapped_as_airfare() -> None:
    snapshot = _snapshot()
    transport = snapshot["prices"][0]
    transport.update(
        {
            "cabin_class": "economy",
            "flight_hours": 2.5,
            "lowest_amount": 350.0,
            "evidence_attested": True,
        }
    )

    fields = build_portal_fields(snapshot)

    assert "selected_fare" not in fields
    assert "flight_cost" not in fields
    assert "flight_pref_outbound.roundtrip_cost" not in fields
    assert fields["lowest_fare"] == "350.00"
    assert fields["cabin_class"] == "economy"
    assert fields["flight_duration_hours"] == "2.5"
    assert fields["fare_evidence_attached"] == "true"


def test_dedicated_flight_amount_is_mapped_as_airfare() -> None:
    snapshot = _snapshot()
    snapshot["prices"][0]["flight_amount"] = 280.0

    fields = build_portal_fields(snapshot)

    assert fields["selected_fare"] == "280.00"
    assert fields["flight_cost"] == "280.00"
    assert fields["flight_pref_outbound.roundtrip_cost"] == "280.00"


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


@pytest.mark.parametrize("origin", ["https://@tpp.example", "https://:@tpp.example"])
def test_portal_action_url_rejects_empty_userinfo(monkeypatch, origin) -> None:
    monkeypatch.setenv("TPP_PORTAL_BASE_URL", origin)

    with pytest.raises(TPPPortalHandoffConfigurationError, match="origin only"):
        portal_action_url()


@pytest.mark.parametrize(
    "origin",
    [
        "https://tpp.example:invalid",
        "https://tpp.example:65536",
        "https://[::1",
        "https://tpp.example\\portal",
        "https://tpp.example\n.attacker.example",
        "https://tpp.example\t.attacker.example",
        "https://tpp.example\x01.attacker.example",
        "https://tpp .example",
    ],
)
def test_portal_action_url_rejects_invalid_or_browser_normalized_origins(
    monkeypatch, origin
) -> None:
    monkeypatch.setenv("TPP_PORTAL_BASE_URL", origin)

    with pytest.raises(TPPPortalHandoffConfigurationError, match="origin"):
        portal_action_url()


@pytest.mark.parametrize("environment", ["production", "staging", "unknown"])
def test_portal_action_url_rejects_http_outside_local_environments(
    monkeypatch, environment
) -> None:
    monkeypatch.setenv("TRIP_PLANNER_ENV", environment)
    monkeypatch.setenv("TPP_PORTAL_BASE_URL", "http://tpp.example")
    with pytest.raises(TPPPortalHandoffConfigurationError, match="HTTPS"):
        portal_action_url()


@pytest.mark.parametrize("environment", ["local", "development", "dev", "test", "testing"])
def test_portal_action_url_allows_local_http(monkeypatch, environment) -> None:
    monkeypatch.setenv("TRIP_PLANNER_ENV", environment)
    monkeypatch.setenv("TPP_PORTAL_BASE_URL", "http://127.0.0.1:8000/")
    assert portal_action_url() == "http://127.0.0.1:8000/portal/handoff"


def test_fallback_portal_origin_enforces_https(monkeypatch) -> None:
    monkeypatch.delenv("TPP_PORTAL_BASE_URL", raising=False)
    monkeypatch.setenv("TRIP_PLANNER_ENV", "production")
    monkeypatch.setenv("TPP_BASE_URL", "http://tpp.example")
    with pytest.raises(TPPPortalHandoffConfigurationError, match="HTTPS"):
        portal_action_url()
    monkeypatch.setenv("TPP_BASE_URL", "https://tpp.example")
    assert portal_action_url() == "https://tpp.example/portal/handoff"


@pytest.mark.parametrize("setting", ["TPP_PORTAL_BASE_URL", "TPP_BASE_URL"])
@pytest.mark.parametrize("environment", [None, "local", "development", "dev", "test", "testing"])
@pytest.mark.parametrize(
    "hostname", ["tpp.example", "10.0.0.1", "192.168.1.1", "0.0.0.0", "localhost.example"]
)
def test_portal_action_url_rejects_remote_http_even_in_local_environments(
    monkeypatch, setting, environment, hostname
) -> None:
    monkeypatch.delenv("TPP_PORTAL_BASE_URL", raising=False)
    monkeypatch.delenv("TPP_BASE_URL", raising=False)
    if environment is None:
        monkeypatch.delenv("TRIP_PLANNER_ENV", raising=False)
    else:
        monkeypatch.setenv("TRIP_PLANNER_ENV", environment)
    monkeypatch.setenv(setting, f"http://{hostname}:8000")

    with pytest.raises(TPPPortalHandoffConfigurationError, match="HTTPS"):
        portal_action_url()


@pytest.mark.parametrize("setting", ["TPP_PORTAL_BASE_URL", "TPP_BASE_URL"])
@pytest.mark.parametrize("environment", ["local", "test", "production"])
@pytest.mark.parametrize("hostname", ["localhost", "127.0.0.1", "127.0.0.2", "[::1]"])
def test_portal_action_url_only_allows_loopback_http_in_local_environments(
    monkeypatch, setting, environment, hostname
) -> None:
    monkeypatch.delenv("TPP_PORTAL_BASE_URL", raising=False)
    monkeypatch.delenv("TPP_BASE_URL", raising=False)
    monkeypatch.setenv("TRIP_PLANNER_ENV", environment)
    monkeypatch.setenv(setting, f"http://{hostname}:8000/")

    if environment == "production":
        with pytest.raises(TPPPortalHandoffConfigurationError, match="HTTPS"):
            portal_action_url()
    else:
        assert portal_action_url() == f"http://{hostname}:8000/portal/handoff"


@pytest.mark.parametrize("environment", [None, "local", "test", "production"])
def test_portal_action_url_keeps_remote_https_available(monkeypatch, environment) -> None:
    if environment is None:
        monkeypatch.delenv("TRIP_PLANNER_ENV", raising=False)
    else:
        monkeypatch.setenv("TRIP_PLANNER_ENV", environment)
    monkeypatch.setenv("TPP_PORTAL_BASE_URL", "https://tpp.example")

    assert portal_action_url() == "https://tpp.example/portal/handoff"
