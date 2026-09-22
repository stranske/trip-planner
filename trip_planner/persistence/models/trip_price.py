"""A price a named human entered for one component of a trip.

Until a provider adapter exists, a human is the only approved source of a price in this
product (see `trip_planner.pricing`). This table is where those figures live. Every row
records who entered it and when, because a figure on an approval packet that cannot say
where it came from is the defect this whole area exists to prevent.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from trip_planner.persistence.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class PersistedTripPrice(Base):
    """One human-entered amount for one cost component of one trip."""

    __tablename__ = "persisted_trip_prices"
    __table_args__ = (
        UniqueConstraint("trip_id", "component", name="uq_persisted_trip_prices_trip_component"),
    )

    trip_price_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    trip_id: Mapped[str] = mapped_column(
        ForeignKey("persisted_trips.trip_id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_accounts.user_id", ondelete="CASCADE"),
        index=True,
    )
    #: One of trip_prices.PRICE_COMPONENTS.
    component: Mapped[str] = mapped_column(String(32))
    amount: Mapped[float] = mapped_column(Float())
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    #: Display name of the person who entered it, carried onto the packet verbatim.
    entered_by: Mapped[str] = mapped_column(String(160))
    #: Where they got it, in their own words: "United.com, 21 Sep" or "Concur quote".
    note: Mapped[str] = mapped_column(String(400), default="")
    captured_at: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
