"""SQLAlchemy model for durable trip planning ledger entries."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from trip_planner.persistence.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class PersistedPlanningLedgerEntry(Base):
    __tablename__ = "persisted_planning_ledger_entries"

    ledger_entry_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    trip_id: Mapped[str] = mapped_column(
        ForeignKey("persisted_trips.trip_id", ondelete="CASCADE"),
        index=True,
    )
    session_state_id: Mapped[str] = mapped_column(String(96), index=True)
    item_type: Mapped[str] = mapped_column(String(48), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True, default="active")
    category: Mapped[str] = mapped_column(String(64), default="general")
    summary: Mapped[str] = mapped_column(String(280))
    detail: Mapped[str] = mapped_column(Text, default="")
    source_message_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_refs: Mapped[list[str]] = mapped_column(JSON, default=list)
    related_option_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    related_decision_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    supersedes_entry_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    metadata_payload: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
