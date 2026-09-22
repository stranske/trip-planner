"""Prices a traveller entered by hand.

`trip_planner.pricing` says a price may only come from an approved source, and names two:
a provider quote, and a figure a named human entered. No provider adapter exists yet, so
today this module is the product's only working source of a price.

That is not a stopgap dressed as a feature. A human override is a first-class source
precisely because the traveller frequently *does* hold real figures the software cannot
reach — a fare from their corporate booking tool, a negotiated hotel rate, a quote from an
agent — and the honest thing is to carry those through with attribution rather than to
invent something in their place.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from trip_planner.app.services.auth import AuthenticatedUser
from trip_planner.persistence.models.trip import PersistedTrip
from trip_planner.persistence.models.trip_price import PersistedTripPrice
from trip_planner.pricing import SourcedPrice, UnsourcedPriceError, manual_override

#: The cost components a traveller can price by hand. Deliberately a short, flat list that
#: matches how an approval packet is read, not the planner's internal option taxonomy.
PRICE_COMPONENTS: tuple[str, ...] = (
    "transport",
    "lodging",
    "activities",
    "other",
)

COMPONENT_LABELS: dict[str, str] = {
    "transport": "Flights and ground travel",
    "lodging": "Accommodation",
    "activities": "Meals and activities",
    "other": "Other costs",
}


class TripPriceNotFoundError(ValueError):
    """Raised when the trip does not exist for this user."""


class TripPriceInvalidError(ValueError):
    """Raised when a submitted price cannot be accepted."""


def _require_trip(db_session: Session, *, user: AuthenticatedUser, trip_id: str) -> PersistedTrip:
    record = db_session.execute(
        select(PersistedTrip).where(
            PersistedTrip.trip_id == trip_id,
            PersistedTrip.user_id == user.user_id,
        )
    ).scalar_one_or_none()
    if record is None:
        raise TripPriceNotFoundError(trip_id)
    return record


def _sourced(row: PersistedTripPrice) -> SourcedPrice:
    """Rebuild the price with its source attached.

    Going back through `manual_override` rather than constructing a bare amount is the
    point: a row that somehow lost its `entered_by` cannot become a price at all.
    """

    return manual_override(
        row.amount,
        currency=row.currency,
        entered_by=row.entered_by,
        captured_at=row.captured_at,
    )


def read_trip_prices_for_owner(
    db_session: Session, *, user_id: str, trip_id: str
) -> list[PersistedTripPrice]:
    """Read the prices without re-checking that the trip exists.

    For callers that already hold the trip record and have established ownership. The
    workspace payload is assembled under a query-count test, so an extra SELECT here is a
    real regression rather than a harmless one.
    """

    rows = (
        db_session.execute(
            select(PersistedTripPrice)
            .where(
                PersistedTripPrice.trip_id == trip_id,
                PersistedTripPrice.user_id == user_id,
            )
            .order_by(PersistedTripPrice.component)
        )
        .scalars()
        .all()
    )
    return list(rows)


def read_trip_prices(
    db_session: Session, *, user: AuthenticatedUser, trip_id: str
) -> list[PersistedTripPrice]:
    _require_trip(db_session, user=user, trip_id=trip_id)
    return read_trip_prices_for_owner(db_session, user_id=user.user_id, trip_id=trip_id)


def save_trip_price(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    component: str,
    amount: float | None,
    currency: str = "USD",
    note: str = "",
) -> list[PersistedTripPrice]:
    """Record, replace or clear one component's price. Returns every price on the trip.

    `amount=None` clears the component, which must stay possible: a traveller who realises
    a figure was wrong needs to be able to withdraw it, and leaving a stale number on an
    approval packet is the same defect as inventing one.
    """

    _require_trip(db_session, user=user, trip_id=trip_id)
    if component not in PRICE_COMPONENTS:
        raise TripPriceInvalidError(
            f"{component!r} is not a priceable component. "
            f"Expected one of: {', '.join(PRICE_COMPONENTS)}."
        )

    existing = db_session.execute(
        select(PersistedTripPrice).where(
            PersistedTripPrice.trip_id == trip_id,
            PersistedTripPrice.user_id == user.user_id,
            PersistedTripPrice.component == component,
        )
    ).scalar_one_or_none()

    if amount is None:
        if existing is not None:
            db_session.delete(existing)
            # The request-scoped session dependency does not commit, so a flush alone
            # would let the row reappear on the next read.
            db_session.commit()
        return read_trip_prices(db_session, user=user, trip_id=trip_id)

    # Validate by constructing the real thing. Every rule about what may be a price lives
    # in one place, and this path cannot drift away from it.
    try:
        price = manual_override(
            float(amount), currency=currency or "USD", entered_by=user.display_name or user.email
        )
    except (UnsourcedPriceError, TypeError, ValueError) as error:
        raise TripPriceInvalidError(str(error)) from error

    if existing is None:
        db_session.add(
            PersistedTripPrice(
                trip_price_id=f"trip-price:{trip_id}:{component}",
                trip_id=trip_id,
                user_id=user.user_id,
                component=component,
                amount=price.amount,
                currency=price.currency,
                entered_by=price.source.attributed_to,
                note=note.strip()[:400],
                captured_at=price.source.captured_at,
            )
        )
    else:
        existing.amount = price.amount
        existing.currency = price.currency
        existing.entered_by = price.source.attributed_to
        existing.note = note.strip()[:400]
        existing.captured_at = price.source.captured_at
    db_session.commit()
    return read_trip_prices(db_session, user=user, trip_id=trip_id)


def trip_price_total(rows: list[PersistedTripPrice]) -> SourcedPrice | None:
    """Sum the entered components into one sourced total, or None when nothing is priced.

    Returns None rather than 0.0 for an empty trip. Zero is a price — it says this trip is
    free — and nobody said that.
    """

    if not rows:
        return None
    currencies = {row.currency for row in rows}
    if len(currencies) > 1:
        # Refuse rather than pick. A packet must not add GBP to USD and print the result.
        return None
    total = sum(row.amount for row in rows)
    newest = max(rows, key=lambda row: row.captured_at)
    entered_by = (
        newest.entered_by
        if len({row.entered_by for row in rows}) == 1
        else f"{newest.entered_by} and others"
    )
    return manual_override(
        total,
        currency=currencies.pop(),
        entered_by=entered_by,
        captured_at=newest.captured_at,
    )


def build_trip_prices_payload(rows: list[PersistedTripPrice]) -> dict[str, Any]:
    """The serialisable shape the workspace and the packet both read."""

    total = trip_price_total(rows)
    entered = {row.component: row for row in rows}
    return {
        "components": [
            {
                "component": component,
                "label": COMPONENT_LABELS[component],
                "currency": entered[component].currency if component in entered else "USD",
                "typical_amount": entered[component].amount if component in entered else None,
                "note": entered[component].note if component in entered else "",
                "price_source": (
                    _sourced(entered[component]).source.to_dict()
                    if component in entered
                    else None
                ),
            }
            for component in PRICE_COMPONENTS
        ],
        "total": total.to_dict() if total is not None else None,
        "priced_component_count": len(rows),
        "unpriced_component_count": len(PRICE_COMPONENTS) - len(rows),
    }
