"""SQLAlchemy model for trip planning notebook items."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from trip_planner.persistence.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class PersistedPlanningNotebookItem(Base):
    __tablename__ = "persisted_planning_notebook_items"

    notebook_item_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    trip_id: Mapped[str] = mapped_column(
        ForeignKey("persisted_trips.trip_id", ondelete="CASCADE"),
        index=True,
    )
    session_state_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(240))
    note: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(48), index=True, default="other")
    status: Mapped[str] = mapped_column(String(32), index=True, default="active")
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    source: Mapped[str] = mapped_column(String(32), default="user")
    linked_ledger_entry_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    source_message_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    metadata_payload: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
