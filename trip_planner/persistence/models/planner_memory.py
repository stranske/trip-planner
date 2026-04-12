"""SQLAlchemy models for persisted planner checkpoints and user-visible memory."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from trip_planner.persistence.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class PersistedPlannerCheckpoint(Base):
    __tablename__ = "persisted_planner_checkpoints"

    checkpoint_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    trip_id: Mapped[str] = mapped_column(
        ForeignKey("persisted_trips.trip_id", ondelete="CASCADE"),
        index=True,
    )
    session_state_id: Mapped[str] = mapped_column(String(96), index=True)
    checkpoint_kind: Mapped[str] = mapped_column(String(32), default="conversation_summary")
    turn_index: Mapped[int] = mapped_column(Integer)
    message_count: Mapped[int] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(String(600))
    source_message_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    metadata_payload: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
    )


class PersistedPlannerMemoryArtifact(Base):
    __tablename__ = "persisted_planner_memory_artifacts"

    memory_artifact_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    trip_id: Mapped[str] = mapped_column(
        ForeignKey("persisted_trips.trip_id", ondelete="CASCADE"),
        index=True,
    )
    session_state_id: Mapped[str] = mapped_column(String(96), index=True)
    checkpoint_id: Mapped[str | None] = mapped_column(
        ForeignKey("persisted_planner_checkpoints.checkpoint_id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    artifact_kind: Mapped[str] = mapped_column(String(32), default="conversation_summary")
    title: Mapped[str] = mapped_column(String(160))
    summary: Mapped[str] = mapped_column(String(600))
    detail: Mapped[str] = mapped_column(Text, default="")
    source_message_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
    )
