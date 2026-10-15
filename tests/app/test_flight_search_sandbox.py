"""Gate §9.2 of docs/provider-sources-plan.md: a test credential cannot price.

Duffel's test mode answers with offers from a fictional airline. The flight search is
wired end to end (place codes, offer request, snapshot), and every assertion reads the
served payload: the search reports what it got, names the sandbox, and no fare from it
reaches the response, the trip's prices or the workspace.
"""

import json
from collections.abc import Iterator
from http.client import IncompleteRead
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.app.services import flight_search
from trip_planner.persistence.db import ensure_database_ready, reset_database_state

OFFERS = Path(__file__).resolve().parents[1] / "fixtures/sources/raw/duffel_offer_request.json"
OFFER_AMOUNTS = [
    offer["total_amount"] for offer in json.loads(OFFERS.read_text())["data"]["offers"]
]
CODES = {"Chicago": "CHI", "New York, NY": "NYC", "Portland, ME": "PWM", "Portland, OR": "PDX"}


class RecordedDuffel:
    def __init__(self, *, fail_offers: bool = False) -> None:
        self.calls: list[str] = []
        self.fail_offers = fail_offers

    def __call__(self, request: Request, timeout: float) -> bytes:
        self.calls.append(request.full_url)
        url = urlparse(request.full_url)
        if url.path.endswith("/places/suggestions"):
            query = parse_qs(url.query)["query"][0]
            code = CODES.get(query)
            data = [{"type": "city", "iata_code": code, "name": query}] if code else []
            return json.dumps({"data": data}).encode()
        if self.fail_offers:
            raise HTTPError(request.full_url, 503, "unavailable", None, None)  # type: ignore[arg-type]
        return OFFERS.read_bytes()


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'flights.db'}")
    monkeypatch.delenv(flight_search.TOKEN_ENV, raising=False)
    reset_database_state()
    ensure_database_ready()
    with TestClient(create_app()) as test_client:
        test_client.post(
            "/api/auth/signup",
            json={"email": "f@example.com", "password": "password123", "display_name": "Fay"},
        )
        yield test_client
    reset_database_state()


def _trip(client: TestClient, *, origin: str = "Chicago") -> str:
    created = client.post(
        "/api/trips",
        json={
            "title": "Client visit",
            "summary": "Quarterly review.",
            "mode": "business",
            "trip_frame": {
                "origin": origin,
                "start_date": "2026-11-10",
                "end_date": "2026-11-11",
                "duration_days": 2,
                "primary_regions": ["New York, NY"],
            },
        },
    )
    return str(created.json()["trip"]["trip_id"])


def _provider_sourced(value: Any) -> list[Any]:
    """Every price source in a payload that claims a provider."""

    if isinstance(value, dict):
        own = [value] if value.get("kind") == "provider" else []
        return own + [found for item in value.values() for found in _provider_sourced(item)]
    if isinstance(value, list):
        return [found for item in value for found in _provider_sourced(item)]
    return []


def _search(client: TestClient, trip_id: str) -> dict[str, Any]:
    response = client.post(f"/api/workspace/{trip_id}/flights/search")
    assert response.status_code == 200, response.text
    return dict(response.json())


def test_a_test_credential_searches_but_cannot_price(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(flight_search.TOKEN_ENV, "duffel_test_fixture")
    duffel = RecordedDuffel()
    monkeypatch.setattr(flight_search, "transport", duffel)
    trip_id = _trip(client)

    result = _search(client, trip_id)

    assert result["status"] == flight_search.TEST_MODE
    assert (result["origin_code"], result["destination_code"]) == ("CHI", "NYC")
    assert result["offer_count"] == len(OFFER_AMOUNTS)
    assert result["prices_shown"] is False
    assert "sandbox_credential" in [issue["code"] for issue in result["issues"]]
    assert any("/air/offer_requests" in call for call in duffel.calls)
    # No fare from the sandbox anywhere a traveller or an approver could read it.
    served = [
        json.dumps(result),
        client.get(f"/api/workspace/{trip_id}/prices").text,
        client.get(f"/api/workspace/{trip_id}").text,
    ]
    for amount in OFFER_AMOUNTS:
        assert all(amount not in text for text in served), amount
    prices = client.get(f"/api/workspace/{trip_id}/prices").json()
    assert prices["priced_component_count"] == 0
    assert _provider_sourced(client.get(f"/api/workspace/{trip_id}").json()) == []


def test_without_a_token_it_says_fares_are_not_connected(client: TestClient) -> None:
    result = _search(client, _trip(client))

    assert result["status"] == flight_search.NOT_CONFIGURED
    assert "Budget tab" in result["summary"]


def test_a_live_token_is_not_used(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(flight_search.TOKEN_ENV, "duffel_live_0000")
    duffel = RecordedDuffel()
    monkeypatch.setattr(flight_search, "transport", duffel)

    result = _search(client, _trip(client))

    assert result["status"] == flight_search.LIVE_NOT_ENABLED
    assert duffel.calls == []


def test_a_provider_failure_is_reported_not_hidden(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(flight_search.TOKEN_ENV, "duffel_test_fixture")
    monkeypatch.setattr(flight_search, "transport", RecordedDuffel(fail_offers=True))

    result = _search(client, _trip(client))

    assert result["status"] == flight_search.PROVIDER_ERROR
    assert "HTTP 503" in result["summary"]


@pytest.mark.parametrize("failed_place", ["Chicago", "New York, NY"])
def test_a_truncated_places_response_is_reported_as_provider_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, failed_place: str
) -> None:
    monkeypatch.setenv(flight_search.TOKEN_ENV, "duffel_test_fixture")
    duffel = RecordedDuffel()

    def truncated_places(request: Request, timeout: float) -> bytes:
        url = urlparse(request.full_url)
        if url.path.endswith("/places/suggestions"):
            if parse_qs(url.query)["query"][0] == failed_place:
                raise IncompleteRead(b'{"data":', 20)
        return duffel(request, timeout)

    monkeypatch.setattr(flight_search, "transport", truncated_places)
    trip_id = _trip(client)

    result = _search(client, trip_id)

    assert result["status"] == flight_search.PROVIDER_ERROR
    assert "IncompleteRead" in result["summary"]
    assert result["prices_shown"] is False
    assert not any("/air/offer_requests" in call for call in duffel.calls)
    assert client.get(f"/api/workspace/{trip_id}/prices").json()["priced_component_count"] == 0


@pytest.mark.parametrize("origin, code", [("Portland, ME", "PWM"), ("Portland, OR", "PDX")])
def test_places_search_keeps_the_region_for_same_named_cities(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, origin: str, code: str
) -> None:
    monkeypatch.setenv(flight_search.TOKEN_ENV, "duffel_test_fixture")
    duffel = RecordedDuffel()
    monkeypatch.setattr(flight_search, "transport", duffel)

    result = _search(client, _trip(client, origin=origin))

    assert result["status"] == flight_search.TEST_MODE
    assert result["origin_code"] == code
    assert result["destination_code"] == "NYC"
    assert result["prices_shown"] is False
    place_queries = [
        parse_qs(urlparse(call).query)["query"][0]
        for call in duffel.calls
        if urlparse(call).path.endswith("/places/suggestions")
    ]
    assert place_queries == [origin, "New York, NY"]
