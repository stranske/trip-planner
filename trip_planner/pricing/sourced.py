"""A price and the source that produced it, inseparable by construction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from typing import Any, Literal

#: The only things that may produce a price.
#:
#: ``provider`` — a quote obtained from an inventory or fare source.
#: ``manual``   — a figure a named human entered, which always overrides.
#:
#: There is deliberately no kind for "the software worked it out from rates it holds".
#: Such a figure is not a price and must not reach a traveller as one.
APPROVED_SOURCE_KINDS: tuple[str, ...] = ("provider", "manual")

SourceKind = Literal["provider", "manual"]


class UnsourcedPriceError(ValueError):
    """Raised when something tries to make a price without a source.

    This is the guard. If you are reading this in a traceback, the fix is to obtain a
    real quote or accept a human override — never to invent a rate to get past it.
    """


@dataclass(frozen=True)
class PriceSource:
    """Who said this price."""

    kind: SourceKind
    source_id: str
    #: Provider name, or the display name of the person who entered the override.
    attributed_to: str
    captured_at: str

    def __post_init__(self) -> None:
        if self.kind not in APPROVED_SOURCE_KINDS:
            msg = (
                f"{self.kind!r} is not an approved price source. "
                f"Approved kinds: {', '.join(APPROVED_SOURCE_KINDS)}."
            )
            raise UnsourcedPriceError(msg)
        if not str(self.source_id).strip():
            raise UnsourcedPriceError("a price source must identify itself")
        if not str(self.attributed_to).strip():
            raise UnsourcedPriceError("a price source must say who it is attributed to")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "source_id": self.source_id,
            "attributed_to": self.attributed_to,
            "captured_at": self.captured_at,
        }


@dataclass(frozen=True)
class SourcedPrice:
    """An amount that carries the source which produced it.

    There is no way to hold an amount here without a source, which is the whole point.
    """

    amount: float
    currency: str
    source: PriceSource

    def __post_init__(self) -> None:
        if not isinstance(self.source, PriceSource):
            raise UnsourcedPriceError("a price must carry an approved PriceSource")
        if not isfinite(self.amount):
            raise UnsourcedPriceError("a price must be a finite amount")
        if self.amount < 0:
            raise UnsourcedPriceError("a price may not be negative")
        if not str(self.currency).strip():
            raise UnsourcedPriceError("a price must name its currency")

    def to_dict(self) -> dict[str, Any]:
        return {
            "typical_amount": self.amount,
            "currency": self.currency,
            "price_source": self.source.to_dict(),
        }


def _now() -> str:
    return datetime.now(UTC).isoformat()


def provider_quote(
    amount: float, *, currency: str = "USD", provider: str, source_id: str, captured_at: str | None = None
) -> SourcedPrice:
    """A price a provider actually quoted."""

    return SourcedPrice(
        amount=amount,
        currency=currency,
        source=PriceSource(
            kind="provider",
            source_id=source_id,
            attributed_to=provider,
            captured_at=captured_at or _now(),
        ),
    )


def manual_override(
    amount: float, *, currency: str = "USD", entered_by: str, captured_at: str | None = None
) -> SourcedPrice:
    """A price a named human typed in. Always permitted, and always wins."""

    return SourcedPrice(
        amount=amount,
        currency=currency,
        source=PriceSource(
            kind="manual",
            source_id=f"manual:{entered_by}",
            attributed_to=entered_by,
            captured_at=captured_at or _now(),
        ),
    )
