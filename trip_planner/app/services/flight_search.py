"""Search Duffel for a trip's flight, on request. Test mode only: no fare is ever shown.

Wired from `docs/provider-sources-plan.md` Phase 2, with §5 in force: Duffel's test mode
returns offers from a fictional airline, so this module reports what the search returned
and builds no price from it. It does not construct a `SourcedPrice` anywhere, which is the
guarantee gate §9.2 tests. A live token is recognised and refused here: enabling live fares
is an account decision (verification, commercial terms), not a code change to slip in.

Runs only when asked (POST /api/workspace/{trip_id}/flights/search). A Duffel offer
request takes 10-25 seconds, too slow for every workspace load.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from trip_planner.persistence.models.trip import PersistedTrip
from trip_planner.sources.adapters import duffel_flight
from trip_planner.sources.adapters.duffel_flight import DuffelFlightAdapter, JsonTransport
from trip_planner.sources.snapshots import SourceQuery

TOKEN_ENV = "TRIP_PLANNER_DUFFEL_TOKEN"
TEST_TOKEN_PREFIX = "duffel_test_"

#: FlightSearchResult.status values.
NOT_CONFIGURED = "not_configured"
LIVE_NOT_ENABLED = "live_not_enabled"
MISSING_TRIP_DETAILS = "missing_trip_details"
NO_AIRPORT_CODE = "no_airport_code"
PROVIDER_ERROR = "provider_error"
NO_OFFERS = "no_offers"
TEST_MODE = "test_mode"

#: Replaced in tests with a recorded-response transport.
transport: JsonTransport = duffel_flight._default_transport


@dataclass(frozen=True)
class FlightSearchResult:
    status: str
    summary: str
    offer_count: int = 0
    origin_code: str = ""
    destination_code: str = ""
    #: Always False today: no fare from this search reaches a traveller.
    prices_shown: bool = False
    issues: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_ENTER_IT = "Enter the fare you hold on the Budget tab."


def search_trip_flights(record: PersistedTrip, *, token: str | None = None) -> FlightSearchResult:
    token = (token if token is not None else os.getenv(TOKEN_ENV, "")).strip()
    if not token:
        return FlightSearchResult(
            NOT_CONFIGURED,
            f"Flight fares are not connected on this server (no Duffel token). {_ENTER_IT}",
        )
    if not token.startswith(TEST_TOKEN_PREFIX):
        return FlightSearchResult(
            LIVE_NOT_ENABLED,
            "A Duffel live token is configured, but live fares are not enabled: that needs a "
            "Duffel live account decision (docs/provider-sources-plan.md, Phase 2). "
            f"{_ENTER_IT}",
        )
    regions = [region for region in record.primary_regions if region]
    if not record.origin or len(regions) != 1 or not record.start_date:
        return FlightSearchResult(
            MISSING_TRIP_DETAILS,
            "Flight search needs a starting point, one destination and a departure date.",
        )

    adapter = DuffelFlightAdapter(api_token=token, transport=transport)
    try:
        origin_code = adapter.suggest_iata_code(record.origin)
        destination_code = adapter.suggest_iata_code(regions[0])
    except (OSError, ValueError, TypeError) as error:
        return FlightSearchResult(
            PROVIDER_ERROR, f"Duffel's place search failed ({type(error).__name__}). {_ENTER_IT}"
        )
    missing = [
        name
        for name, code in ((record.origin, origin_code), (regions[0], destination_code))
        if not code
    ]
    if missing:
        return FlightSearchResult(
            NO_AIRPORT_CODE, f"Duffel found no airport for {', '.join(missing)}. {_ENTER_IT}"
        )
    assert origin_code is not None and destination_code is not None

    snapshot = adapter.fetch_snapshot(
        SourceQuery(
            query_id=f"flights:{record.trip_id}",
            entity_scope="transport",
            option_kind="flight",
            requested_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            origin=origin_code,
            destination=destination_code,
            filters={"departure_date": record.start_date, "cabin_class": "economy"},
        )
    )
    issues = [issue.to_dict() for issue in snapshot.issues]
    route = f"{origin_code} → {destination_code} on {record.start_date}"
    if snapshot.snapshot_status == "failed":
        detail = snapshot.issues[0].message if snapshot.issues else "no detail"
        return FlightSearchResult(
            PROVIDER_ERROR,
            f"Duffel's flight search failed: {detail}. {_ENTER_IT}",
            origin_code=origin_code,
            destination_code=destination_code,
            issues=issues,
        )
    count = len(snapshot.records)
    if count == 0:
        return FlightSearchResult(
            NO_OFFERS,
            f"Duffel (test mode) returned no offers for {route}.",
            origin_code=origin_code,
            destination_code=destination_code,
            issues=issues,
        )
    return FlightSearchResult(
        TEST_MODE,
        (
            f"Flight search is connected to Duffel in test mode: {count} offer(s) for {route}. "
            "Test-mode offers come from a fictional airline, so none is shown as a price; "
            f"live fares need a Duffel live account. {_ENTER_IT}"
        ),
        offer_count=count,
        origin_code=origin_code,
        destination_code=destination_code,
        issues=issues,
    )
