"""The planner's figures must follow from the trip it is planning.

For at least four months every trip returned the same numbers: cost was
`240 + 230 x days`, travel was always 45 minutes, transfers always 0/1/2, and the
destination reached no computation at all because anything outside a six-city lookup
resolved to latitude 0.0 / longitude 0.0. Ten audit rounds missed it because nobody
varied an input and diffed the output. These tests are that diff.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime

import geonamescache
import pytest

from trip_planner.app.services.inventory import (
    PersistedTripSourceInventoryAdapter,
    UnsupportedDestinationError,
    _build_inventory_assembly_input,
    assemble_inventory_bundles_for_trip,
)
from trip_planner.geo import ResolvedPlace, distance_km, resolve_place
from trip_planner.geo import resolver as geo_resolver


def _journey(
    origin: str | None, regions: list[str], *, days: int = 4, travellers: int = 1
):
    adapter = PersistedTripSourceInventoryAdapter(
        trip_id="trip-probe",
        trip_mode="business",
        primary_regions=regions,
        origin=origin,
        duration_days=days,
    )
    adapter.traveler_count = travellers
    return adapter._journey_profile()


def _place(name: str) -> ResolvedPlace:
    """Resolve a place the planner must know, failing loudly if it does not."""
    resolved = resolve_place(name)
    assert resolved is not None, f"{name} must resolve"
    return resolved


def test_distance_follows_real_geography() -> None:
    seattle = _place("Seattle")
    assert distance_km(seattle, _place("Chicago")) == pytest.approx(2789, abs=40)
    assert distance_km(seattle, _place("Tokyo")) == pytest.approx(7696, abs=80)
    # Accents and administrative qualifiers resolve to the same real place.
    assert _place("Reykjavík").name == _place("Reykjavik, Iceland").name
    assert _place("Chicago, IL").country_code == "US"


def test_travel_time_moves_with_the_destination() -> None:
    near = _journey("Seattle", ["Chicago"])
    far = _journey("Seattle", ["Tokyo"])

    assert far.total_distance_km > near.total_distance_km * 2
    assert far.travel_minutes > near.travel_minutes


def test_the_journey_carries_no_price() -> None:
    """Distance and duration are measurements; a fare is not derivable from them.

    An earlier version computed a transport cost from per-km rates the software held.
    That was an invention presented as an estimate.
    """
    journey = _journey("Seattle", ["Tokyo"])
    assert not hasattr(journey, "transport_cost_usd")


def test_a_longer_leg_is_never_quicker() -> None:
    previous = None
    for destination in ("Austin", "Chicago", "Reykjavik, Iceland", "Tokyo", "Nairobi"):
        current = _journey("Seattle", [destination])
        if previous is not None and current.total_distance_km > previous.total_distance_km:
            assert current.travel_minutes >= previous.travel_minutes
        previous = current


def test_a_multi_stop_trip_measures_every_leg() -> None:
    single = _journey("Seattle", ["Chicago"])
    multi = _journey("Seattle", ["Chicago", "Austin"])

    assert len(multi.legs) == 2
    assert multi.total_distance_km > single.total_distance_km
    assert any("Chicago to Austin" in note for note in multi.assumptions)


def test_an_unresolvable_destination_is_refused_not_invented() -> None:
    with pytest.raises(UnsupportedDestinationError):
        _journey("Seattle", ["Zzqxwv Nonexistent Place"])


def test_an_unresolvable_origin_is_refused_too() -> None:
    with pytest.raises(UnsupportedDestinationError):
        _journey("Qqzzxx Nowhere", ["Chicago"])


# --- The gate that matters: the figures the WORKSPACE emits, not the helper ----------
# An earlier version of this file tested `_journey_profile()` only. Reverting the bundle
# to flat constants left every one of those tests green, so they guarded nothing. These
# assert the payload the product actually serves.


def _bundle_dict(
    origin: str, destination: str, *, days: int = 4, travellers: int = 1
) -> dict:
    assembly = _build_inventory_assembly_input(
        trip_id=f"trip-{destination.lower().replace(' ', '-').replace(',', '')}-{travellers}",
        trip_mode="business",
        primary_regions=[destination],
        origin=origin,
        duration_days=days,
        traveler_count=travellers,
        allow_fixture_fallback=False,
    )
    bundles = assemble_inventory_bundles_for_trip(assembly_input=assembly)
    return bundles[0].to_dict()


def _totals(bundle: dict) -> tuple[float, int]:
    """Every priced amount, and the transport duration, as the bundle carries them."""
    amounts = re.findall(r'"typical_amount":\s*([0-9.]+)', json.dumps(bundle))
    minutes = re.findall(r'"duration_minutes":\s*([0-9]+)', json.dumps(bundle))
    return round(sum(float(a) for a in amounts), 2), int(minutes[0])


def _emitted(origin: str, destination: str, *, days: int = 4) -> tuple[float, int]:
    return _totals(_bundle_dict(origin, destination, days=days))


def test_emitted_duration_differs_by_destination() -> None:
    _, near_minutes = _emitted("Seattle", "Chicago")
    _, far_minutes = _emitted("Seattle", "Tokyo")

    assert far_minutes != near_minutes, "the served duration must move with the destination"
    assert far_minutes > near_minutes


def test_party_size_cannot_be_priced_without_a_source() -> None:
    """Scaling an invented rate by the party size still produces an invented price."""
    solo, _ = _totals(_bundle_dict("Seattle", "Chicago", travellers=1))
    team, _ = _totals(_bundle_dict("Seattle", "Chicago", travellers=8))

    assert solo == 0.0 and team == 0.0, "no priced amounts may be emitted at all"


def test_origin_is_not_charged_a_destination_gateway_transfer() -> None:
    journey = _journey("Seattle", ["Chicago"])
    assert any("1 local gateway transfer" in note for note in journey.assumptions)


def test_long_journey_arrival_timestamp_stays_valid() -> None:
    adapter = PersistedTripSourceInventoryAdapter(
        trip_id="trip-long",
        trip_mode="business",
        primary_regions=["Nairobi"],
        origin="Seattle",
        duration_days=4,
        start_date="2026-06-01",
    )
    adapter.traveler_count = 1
    bundle = adapter._build_runtime_bundle_payload()
    timing = bundle["transport_options"][0]["timing_summary"]
    arrival = datetime.fromisoformat(timing["arrival_local"])
    assert arrival.date() == date(2026, 6, 2)


def test_emitted_transport_mode_follows_air_leg() -> None:
    bundle = _bundle_dict("Seattle", "Tokyo")
    transport = bundle["transport_options"][0]
    assert transport["transport_kind"] == "flight"
    assert transport["segments"][0]["mode"] == "flight"


def test_qualified_cambridge_resolves_to_massachusetts_not_uk() -> None:
    resolved = resolve_place("Cambridge, MA")
    assert resolved is not None
    assert resolved.country_code == "US"


def test_qualified_city_resolves_full_country_name_outside_explicit_aliases() -> None:
    resolved = resolve_place("Paris, France")
    assert resolved is not None
    assert resolved.country_code == "FR"


@pytest.mark.parametrize(
    ("latitude", "longitude", "message"),
    [
        (float("nan"), 0.0, "invalid latitude"),
        (0.0, float("inf"), "invalid longitude"),
        (90.1, 0.0, "invalid latitude"),
        (0.0, -180.1, "invalid longitude"),
    ],
)
def test_resolved_place_rejects_nonfinite_and_out_of_range_coordinates(
    latitude: float, longitude: float, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        ResolvedPlace(
            query="invalid",
            name="invalid",
            latitude=latitude,
            longitude=longitude,
            country_code="ZZ",
            population=0,
        )


def test_coordinate_validation_applies_to_both_city_indexes(monkeypatch) -> None:
    monkeypatch.setattr(
        geo_resolver,
        "_city_index",
        lambda: {"bad unqualified": ("Bad", float("nan"), 0.0, "ZZ", 0)},
    )
    with pytest.raises(ValueError, match="invalid latitude"):
        resolve_place("Bad Unqualified")

    monkeypatch.setattr(
        geo_resolver,
        "_qualified_city_index",
        lambda: {
            ("bad qualified", "FR", ""): {
                "name": "Bad",
                "latitude": 0.0,
                "longitude": 181.0,
                "countrycode": "FR",
                "population": 0,
            }
        },
    )
    with pytest.raises(ValueError, match="invalid longitude"):
        resolve_place("Bad Qualified, France")


def test_qualified_city_resolution_builds_geonames_index_once(monkeypatch) -> None:
    original = geonamescache.GeonamesCache
    constructor_calls = 0

    class CountingGeonamesCache:
        def __init__(self):
            nonlocal constructor_calls
            constructor_calls += 1
            self._delegate = original()

        def get_cities(self):
            return self._delegate.get_cities()

    geo_resolver._qualified_city_index.cache_clear()
    monkeypatch.setattr(geonamescache, "GeonamesCache", CountingGeonamesCache)

    assert resolve_place("Cambridge, MA") is not None
    assert resolve_place("Chicago, IL") is not None
    assert constructor_calls == 1
