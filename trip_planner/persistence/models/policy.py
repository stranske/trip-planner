"""SQLAlchemy model for persisted business policy imports."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from trip_planner.persistence.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class PersistedPolicyState(Base):
    __tablename__ = "persisted_policy_states"

    policy_state_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    trip_id: Mapped[str] = mapped_column(
        ForeignKey("persisted_trips.trip_id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_accounts.user_id", ondelete="CASCADE"),
        index=True,
    )
    owner_profile_id: Mapped[str] = mapped_column(String(96))
    source_kind: Mapped[str] = mapped_column(String(32), default="tpp_sync")
    source_request_id: Mapped[str] = mapped_column(String(96))
    source_correlation_id: Mapped[str] = mapped_column(String(96))
    policy_id: Mapped[str] = mapped_column(String(96), index=True)
    organization_id: Mapped[str] = mapped_column(String(96), index=True)
    policy_version: Mapped[str] = mapped_column(String(48))
    sync_status: Mapped[str] = mapped_column(String(32), default="current", index=True)
    imported_at: Mapped[str] = mapped_column(String(64), index=True)
    constraint_set: Mapped[dict] = mapped_column(JSON, default=dict)
    organization_context: Mapped[dict] = mapped_column(JSON, default=dict)
    freshness: Mapped[dict] = mapped_column(JSON, default=dict)
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    notes: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
    )
