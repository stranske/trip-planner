"""A price may only come from a source.

The planner invented its prices for months: `240 + 230 x days`, then per-km rates the
software held. Both were presented to a business traveller as costs, on the screen
whose purpose is an employer approval request. This is the rule that makes that
impossible to do again by accident.
"""

from __future__ import annotations

import json
import re
import pytest

from trip_planner.app.services.inventory import (
    PersistedTripSourceInventoryAdapter,
)
from trip_planner.pricing import (
    APPROVED_SOURCE_KINDS,
    PriceSource,
    SourcedPrice,
    UnsourcedPriceError,
    manual_override,
    provider_quote,
)


def test_only_provider_and_manual_are_approved_sources() -> None:
    assert set(APPROVED_SOURCE_KINDS) == {"provider", "manual"}


def test_a_price_cannot_be_built_without_a_source() -> None:
    with pytest.raises(TypeError):
        SourcedPrice(amount=100.0, currency="USD")  # type: ignore[call-arg]


@pytest.mark.parametrize("kind", ["estimate", "assumption", "modelled", "derived", ""])
def test_invented_rate_kinds_are_refused(kind: str) -> None:
    """There is deliberately no source kind meaning 'the software worked it out'."""
    with pytest.raises(UnsourcedPriceError):
        PriceSource(
            kind=kind,  # type: ignore[arg-type]
            source_id="s",
            attributed_to="someone",
            captured_at="2026-09-21T00:00:00Z",
        )


def test_a_source_must_identify_itself_and_its_author() -> None:
    for source_id, attributed_to in (("", "Provider"), ("s", "")):
        with pytest.raises(UnsourcedPriceError):
            PriceSource(
                kind="provider",
                source_id=source_id,
                attributed_to=attributed_to,
                captured_at="2026-09-21T00:00:00Z",
            )


def test_a_provider_quote_is_a_price() -> None:
    price = provider_quote(412.55, provider="Duffel", source_id="duffel:offer-1")
    assert price.amount == 412.55
    assert price.source.kind == "provider"
    assert price.to_dict()["price_source"]["attributed_to"] == "Duffel"


def test_a_human_override_is_always_a_price() -> None:
    """A human may always enter a figure directly, and it is properly sourced."""
    price = manual_override(999.0, entered_by="Tim Stranske")
    assert price.source.kind == "manual"
    assert price.source.attributed_to == "Tim Stranske"
    assert price.to_dict()["typical_amount"] == 999.0


def test_non_finite_and_negative_amounts_are_refused() -> None:
    for bad in (float("nan"), float("inf"), -1.0):
        with pytest.raises(UnsourcedPriceError):
            provider_quote(bad, provider="P", source_id="p:1")


def test_the_planner_emits_no_price_because_it_quotes_nothing() -> None:
    """The adapter measures distance and duration. It must price nothing at all."""
    adapter = PersistedTripSourceInventoryAdapter(
        trip_id="trip-guard",
        trip_mode="business",
        primary_regions=["Chicago"],
        origin="Seattle",
        duration_days=4,
    )
    bundle = json.dumps(adapter._build_runtime_bundle_payload())
    amounts = re.findall(r'"typical_amount":\s*([^,}\s]+)', bundle)

    assert amounts, "the cost shape must still be present so a source can fill it"
    assert set(amounts) == {"null"}, f"unsourced prices emitted: {sorted(set(amounts))}"


def test_no_money_rate_constants_remain_in_the_adapter() -> None:
    """The specific regression: per-km and per-night rates the software held."""
    from trip_planner.app.services import inventory

    banned = [
        name
        for name in dir(inventory)
        if name.isupper() and ("COST" in name or "RATE" in name or "ALLOWANCE" in name)
    ]
    assert banned == [], f"money rates must not live in the planner: {banned}"
