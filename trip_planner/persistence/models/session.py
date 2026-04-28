"""SQLAlchemy models for auth and persisted planning sessions."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from trip_planner.persistence.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("user_accounts.user_id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user = relationship("UserAccount", back_populates="sessions")


class PersistedPlanningSessionState(Base):
    __tablename__ = "persisted_planning_session_states"

    session_state_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    trip_id: Mapped[str] = mapped_column(
        ForeignKey("persisted_trips.trip_id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_accounts.user_id", ondelete="CASCADE"),
        index=True,
    )
    owner_profile_id: Mapped[str] = mapped_column(String(96))
    mode: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[str] = mapped_column(String(64))
    last_updated_at: Mapped[str] = mapped_column(String(64), index=True)
    interaction_state: Mapped[dict] = mapped_column(JSON, default=dict)
    recent_option_presentations: Mapped[list[dict]] = mapped_column(JSON, default=list)
    pending_decisions: Mapped[list[dict]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="active")
    current_checkpoint_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    current_saved_scenario_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    active_budget_plan_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    activity_log_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    schema_version: Mapped[str] = mapped_column(String(16), default="0.1.0")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    notes: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
    )
