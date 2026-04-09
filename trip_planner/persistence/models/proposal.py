"""SQLAlchemy model for persisted proposal submission and evaluation state."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from trip_planner.persistence.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class PersistedProposalState(Base):
    __tablename__ = "persisted_proposal_states"

    proposal_state_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    trip_id: Mapped[str] = mapped_column(
        ForeignKey("persisted_trips.trip_id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_accounts.user_id", ondelete="CASCADE"),
        index=True,
    )
    owner_profile_id: Mapped[str] = mapped_column(String(96))
    proposal_id: Mapped[str] = mapped_column(String(96), index=True)
    proposal_version: Mapped[str] = mapped_column(String(96))
    scenario_id: Mapped[str | None] = mapped_column(String(96), nullable=True, index=True)
    organization_id: Mapped[str | None] = mapped_column(String(96), nullable=True, index=True)
    execution_id: Mapped[str | None] = mapped_column(String(96), nullable=True, index=True)
    submission_status: Mapped[str] = mapped_column(String(32), index=True)
    evaluation_status: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    proposal_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    submission_record: Mapped[dict] = mapped_column(JSON, default=dict)
    evaluation_record: Mapped[dict] = mapped_column(JSON, default=dict)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
    )
