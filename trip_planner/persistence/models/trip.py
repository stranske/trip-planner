"""SQLAlchemy model for persisted trip containers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from trip_planner.persistence.db import Base

if TYPE_CHECKING:
    from trip_planner.persistence.models.account import UserAccount


def _utcnow() -> datetime:
    return datetime.now(UTC)


class PersistedTrip(Base):
    __tablename__ = "persisted_trips"

    trip_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_accounts.user_id", ondelete="CASCADE"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(160))
    summary: Mapped[str] = mapped_column(String(600), default="")
    mode: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="draft")
    start_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    primary_regions: Mapped[list[str]] = mapped_column(JSON, default=list)
    traveler_party_kind: Mapped[str] = mapped_column(String(32), default="solo")
    traveler_count: Mapped[int] = mapped_column(Integer, default=1)
    traveler_notes: Mapped[str] = mapped_column(String(240), default="")
    leisure_profile_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    business_profile_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    objective_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    option_set_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    itinerary_state_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    budget_state_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    policy_state_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
    )

    user: Mapped["UserAccount"] = relationship(back_populates="trips")

    def profile_refs_payload(self) -> dict[str, str | None]:
        return {
            "leisure_profile_id": self.leisure_profile_id,
            "business_profile_id": self.business_profile_id,
        }

    def artifacts_payload(self) -> dict[str, Any]:
        return {
            "objective_id": self.objective_id,
            "option_set_ids": list(self.option_set_ids),
            "itinerary_state_id": self.itinerary_state_id,
            "budget_state_id": self.budget_state_id,
            "policy_state_id": self.policy_state_id,
        }
