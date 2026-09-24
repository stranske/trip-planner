"""The planner must not invent a location for a destination it does not cover.

Before this guard `_geo_payload` returned latitude 0.0 / longitude 0.0 / country "ZZ" —
Null Island — for every destination outside a six-entry lookup, and the planner then
produced confident route, timing and cost figures for a trip it knew nothing about.
"""

from __future__ import annotations

import pytest

from trip_planner.app.services.inventory import (
    PersistedTripSourceInventoryAdapter,
    UnsupportedDestinationError,
    _build_inventory_assembly_input,
    assemble_inventory_bundles_for_trip,
    build_inventory_summary_payload,
    curated_destination_examples,
    supported_destinations,
)


def _summary(*regions: str) -> dict:
    """Assemble inventory exactly as the workspace does."""
    assembly = _build_inventory_assembly_input(
        trip_id="trip-"
        + "-".join(region.lower().replace(" ", "-").replace(",", "") for region in regions),
        trip_mode="business",
        primary_regions=list(regions),
        duration_days=4,
        allow_fixture_fallback=False,
    )
    bundles = assemble_inventory_bundles_for_trip(assembly_input=assembly)
    return build_inventory_summary_payload(bundles, assembly_input=assembly)


def test_curated_destination_examples_is_not_empty_and_is_sorted() -> None:
    names = curated_destination_examples()
    assert names, "the planner must declare curated destination examples"
    assert names == sorted(names)
    assert supported_destinations() == names


def test_covered_destination_still_assembles() -> None:
    payload = _summary("Chicago")
    assert payload["runtime_state"]["status"] == "ready"
    assert payload["bundle_count"] >= 1


def test_real_destination_outside_the_curated_six_now_resolves() -> None:
    """Coverage comes from the GeoNames dataset, not a six-entry lookup."""
    payload = _summary("Reykjavik, Iceland")
    assert payload["runtime_state"]["status"] == "ready"
    assert payload["bundle_count"] >= 1


def test_uncovered_destination_produces_no_bundles_and_says_so() -> None:
    payload = _summary("Zzqxwv Nonexistent Place")
    runtime = payload["runtime_state"]

    # No invented inventory for a place the planner cannot plan.
    assert payload["bundle_count"] == 0
    assert runtime["status"] == "empty"
    # And the limit is stated, naming the destination and what is covered.
    assert "Zzqxwv Nonexistent Place" in runtime["title"] + runtime["summary"]
    # Says what to do next: fix the place name, or carry on with the prices you hold.
    assert "Check the spelling" in runtime["summary"]
    assert "enter the prices you hold" in runtime["summary"]


def test_any_unsupported_primary_region_blocks_bundle_assembly() -> None:
    # One unresolvable stop blocks the whole trip, even alongside a resolvable one.
    # (This originally used "Reykjavik, Iceland", which the GeoNames dataset now
    # resolves; a genuinely unresolvable name is needed to exercise the guard.)
    payload = _summary("Chicago", "Zzqxwv Nonexistent Place")
    runtime = payload["runtime_state"]

    assert payload["bundle_count"] == 0
    assert runtime["status"] == "empty"
    assert runtime["issues"]
    assert runtime["issues"][0]["code"] == "unsupported_inventory_destination"
    assert runtime["issues"][0]["details"]["region"] == "Zzqxwv Nonexistent Place"


def test_geo_payload_raises_rather_than_returning_null_island() -> None:
    adapter = PersistedTripSourceInventoryAdapter(
        trip_id="trip-null-island",
        trip_mode="business",
        primary_regions=["Nowhere-at-all"],
        duration_days=3,
    )
    with pytest.raises(UnsupportedDestinationError) as excinfo:
        adapter._geo_payload("Nowhere-at-all")
    assert excinfo.value.region == "Nowhere-at-all"
