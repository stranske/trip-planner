from __future__ import annotations

import http.client
import io
import json
from collections.abc import Callable
from dataclasses import replace
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from trip_planner.sources import DuffelFlightAdapter
from trip_planner.sources.snapshots import SourceQuery

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "sources"
    / "raw"
    / "duffel_offer_request.json"
)


def _query() -> SourceQuery:
    return SourceQuery(
        query_id="duffel-ord-jfk-2026-11-10",
        entity_scope="transport",
        option_kind="flight",
        market="US",
        locale="en-US",
        currency="USD",
        origin="ORD",
        destination="JFK",
        requested_at="2026-10-15T12:00:00Z",
        filters={"departure_date": "2026-11-10", "cabin_class": "economy"},
    )


def test_emits_raw_snapshot() -> None:
    adapter = DuffelFlightAdapter(fixture_path=FIXTURE_PATH)

    snapshot = adapter.fetch_snapshot(_query())
    handoff = adapter.build_handoff(snapshot)

    assert snapshot.transport == "fixture"
    assert snapshot.payload_metadata == {
        "mode": "recorded-fixture",
        "offer_request_id": "orq_fixture_chicago_new_york",
        "offer_count": "1",
        "live_mode": "false",
    }
    assert snapshot.records
    assert snapshot.records[0].provider_entity_id == "off_fixture_ord_jfk"
    assert snapshot.records[0].payload["total_amount"] == "218.40"
    assert (
        snapshot.records[0].payload["slices"][0]["segments"][0]["operating_carrier"]["name"]
        == "Duffel Airways"
    )
    assert handoff.status == "ready"
    assert handoff.target_contract == "trip_planner/options/transport.py"
    assert handoff.provenance_refs[0].contribution_kind == "inventory"


def test_live_path_builds_documented_test_mode_request() -> None:
    captured: dict[str, object] = {}

    def transport(request: Request, timeout: float) -> bytes:
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        assert isinstance(request.data, bytes)
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FIXTURE_PATH.read_bytes()

    snapshot = DuffelFlightAdapter(
        api_token="duffel_test_example",
        timeout=12.0,
        transport=transport,
    ).fetch_snapshot(_query())

    assert captured["url"] == "https://api.duffel.com/air/offer_requests?supplier_timeout=10000"
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == "Bearer duffel_test_example"
    assert headers["Duffel-version"] == "v2"
    assert captured["body"] == {
        "data": {
            "cabin_class": "economy",
            "slices": [{"origin": "ORD", "destination": "JFK", "departure_date": "2026-11-10"}],
            "passengers": [{"type": "adult"}],
        }
    }
    assert captured["timeout"] == 12.0
    assert snapshot.transport == "api"


def test_provider_failure_is_preserved_as_blocked_snapshot() -> None:
    def unavailable(_request: Request, _timeout: float) -> bytes:
        raise URLError("test provider unavailable")

    adapter = DuffelFlightAdapter(
        api_token="duffel_test_example",
        transport=unavailable,
    )

    snapshot = adapter.fetch_snapshot(_query())
    handoff = adapter.build_handoff(snapshot)

    assert snapshot.snapshot_status == "failed"
    assert snapshot.records == []
    assert snapshot.issues[0].code == "duffel_unavailable"
    assert snapshot.issues[0].retriable is True
    assert handoff.status == "blocked"
    assert handoff.blocked_issue_ids == ["duffel-ord-jfk-2026-11-10-duffel_unavailable"]


@pytest.mark.parametrize(("status", "retriable"), [(429, True), (503, True), (422, False)])
def test_http_error_is_preserved_as_blocked_snapshot(status: int, retriable: bool) -> None:
    def failing(request: Request, _timeout: float) -> bytes:
        raise HTTPError(request.full_url, status, "error", Message(), io.BytesIO(b"{}"))

    snapshot = DuffelFlightAdapter(
        api_token="duffel_test_example", transport=failing
    ).fetch_snapshot(_query())

    assert snapshot.snapshot_status == "failed"
    assert snapshot.issues[0].code == "duffel_http_error"
    assert snapshot.issues[0].provider_status == str(status)
    assert snapshot.issues[0].retriable is retriable


@pytest.mark.parametrize(
    "failure",
    [ConnectionResetError("reset"), http.client.IncompleteRead(b"partial")],
)
def test_transport_failure_is_preserved_as_blocked_snapshot(failure: BaseException) -> None:
    def failing(_request: Request, _timeout: float) -> bytes:
        raise failure

    snapshot = DuffelFlightAdapter(
        api_token="duffel_test_example", transport=failing
    ).fetch_snapshot(_query())

    assert snapshot.snapshot_status == "failed"
    assert snapshot.issues[0].code == "duffel_unavailable"
    assert snapshot.issues[0].retriable is True


@pytest.mark.parametrize("body", [b"not json", b"[]"])
def test_invalid_live_body_is_preserved_as_blocked_snapshot(body: bytes) -> None:
    snapshot = DuffelFlightAdapter(
        api_token="duffel_test_example", transport=lambda _request, _timeout: body
    ).fetch_snapshot(_query())

    assert snapshot.snapshot_status == "failed"
    assert snapshot.issues[0].code == "duffel_invalid_json"
    assert snapshot.issues[0].stage == "decode"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.pop("data"),
        lambda payload: payload["data"].pop("offers"),
        lambda payload: payload["data"].pop("id"),
        lambda payload: payload["data"].__setitem__("live_mode", True),
    ],
)
def test_invalid_live_schema_is_preserved_as_blocked_snapshot(
    mutate: Callable[[dict[str, object]], object],
) -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    mutate(payload)

    snapshot = DuffelFlightAdapter(
        api_token="duffel_test_example",
        transport=lambda _request, _timeout: json.dumps(payload).encode("utf-8"),
    ).fetch_snapshot(_query())

    assert snapshot.snapshot_status == "failed"
    assert snapshot.issues[0].code == "duffel_invalid_response"
    assert snapshot.issues[0].stage == "decode"
    assert snapshot.issues[0].retriable is False


def test_empty_offer_response_produces_ready_zero_record_handoff() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["data"]["offers"] = []
    snapshot = DuffelFlightAdapter(
        api_token="duffel_test_example",
        transport=lambda _request, _timeout: json.dumps(payload).encode("utf-8"),
    ).fetch_snapshot(_query())

    handoff = DuffelFlightAdapter(fixture_path=FIXTURE_PATH).build_handoff(snapshot)

    assert snapshot.snapshot_status == "complete"
    assert handoff.status == "ready"
    assert handoff.record_count == 0
    assert handoff.blocked_issue_ids == []
    assert handoff.notes == ["Flight offers are ready for transport-option normalization."]


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda query: replace(query, entity_scope="lodging"), "entity_scope must be transport"),
        (lambda query: replace(query, option_kind="rail"), "option_kind must be flight"),
        (
            lambda query: replace(query, origin="Chicago"),
            "origin must be a three-letter IATA code",
        ),
        (
            lambda query: replace(query, filters={"departure_date": "tomorrow"}),
            "departure_date.*ISO date",
        ),
    ],
)
def test_rejects_invalid_queries(
    mutate: Callable[[SourceQuery], SourceQuery], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        DuffelFlightAdapter(fixture_path=FIXTURE_PATH).fetch_snapshot(mutate(_query()))


def test_rejects_live_mode_fixture(tmp_path: Path) -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["data"]["live_mode"] = True
    live_fixture = tmp_path / "live.json"
    live_fixture.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="test mode"):
        DuffelFlightAdapter(fixture_path=live_fixture).fetch_snapshot(_query())


def test_requires_test_token_or_fixture() -> None:
    with pytest.raises(ValueError, match="api_token or fixture_path"):
        DuffelFlightAdapter()
    with pytest.raises(ValueError, match="test-mode token"):
        DuffelFlightAdapter(api_token="duffel_live_not_allowed")
