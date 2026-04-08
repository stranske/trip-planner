"""SQLAlchemy models for persisted saved-scenario and planning-history state."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from trip_planner.persistence.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class PersistedSavedScenario(Base):
    __tablename__ = "persisted_saved_scenarios"

    saved_scenario_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    trip_id: Mapped[str] = mapped_column(
        ForeignKey("persisted_trips.trip_id", ondelete="CASCADE"),
        index=True,
    )
    current_version_id: Mapped[str] = mapped_column(String(96))
    versions: Mapped[list[dict]] = mapped_column(JSON, default=list)
    comparisons: Mapped[list[dict]] = mapped_column(JSON, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    notes: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
    )


class PersistedActivityLogEvent(Base):
    __tablename__ = "persisted_activity_log_events"

    activity_event_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    trip_id: Mapped[str] = mapped_column(
        ForeignKey("persisted_trips.trip_id", ondelete="CASCADE"),
        index=True,
    )
    session_state_id: Mapped[str] = mapped_column(String(96))
    occurred_at: Mapped[str] = mapped_column(String(64), index=True)
    event_kind: Mapped[str] = mapped_column(String(64))
    summary: Mapped[str] = mapped_column(String(600))
    actor: Mapped[str] = mapped_column(String(64), default="system")
    related_decision_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    related_option_set_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    saved_scenario_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    budget_plan_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    scenario_budget_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    checkpoint_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    metadata_payload: Mapped[dict[str, str]] = mapped_column("metadata", JSON, default=dict)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    notes: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
