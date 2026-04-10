"""SQLAlchemy models for persisted activity-trail and planner-action state."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from trip_planner.persistence.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


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


class PersistedPlannerAction(Base):
    __tablename__ = "persisted_planner_actions"

    planner_action_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    trip_id: Mapped[str] = mapped_column(
        ForeignKey("persisted_trips.trip_id", ondelete="CASCADE"),
        index=True,
    )
    session_state_id: Mapped[str] = mapped_column(String(96), index=True)
    activity_event_id: Mapped[str | None] = mapped_column(
        ForeignKey("persisted_activity_log_events.activity_event_id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    occurred_at: Mapped[str] = mapped_column(String(64), index=True)
    action_type: Mapped[str] = mapped_column(String(64))
    decision_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    option_set_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    option_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    choice: Mapped[str | None] = mapped_column(String(160), nullable=True)
    payload: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
