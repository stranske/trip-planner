"""Prices may only come from a source.

A price the product shows a traveller must be traceable to something that actually
quoted it: a provider, or a human who typed it. Nothing else is a price. A figure
derived from rates the software made up is not an estimate, it is an invention, and
presenting one on a screen whose purpose is an employer approval request is the
failure this module exists to make impossible.

The rule is enforced by construction: `SourcedPrice` cannot be built without an
approved source, so a code path with no source cannot produce a price at all. It
produces `None`, and the surface says it has no price rather than showing a number.
"""

from trip_planner.pricing.sourced import (
    APPROVED_SOURCE_KINDS,
    PriceSource,
    SourcedPrice,
    UnsourcedPriceError,
    manual_override,
    provider_quote,
)

__all__ = [
    "APPROVED_SOURCE_KINDS",
    "PriceSource",
    "SourcedPrice",
    "UnsourcedPriceError",
    "manual_override",
    "provider_quote",
]
