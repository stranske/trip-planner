"""SQLAlchemy models for persisted budget plans and actual-spend events."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from trip_planner.persistence.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class PersistedBudgetPlan(Base):
    __tablename__ = "persisted_budget_plans"

    budget_plan_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    trip_id: Mapped[str] = mapped_column(
        ForeignKey("persisted_trips.trip_id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_accounts.user_id", ondelete="CASCADE"),
        index=True,
    )
    owner_profile_id: Mapped[str] = mapped_column(String(96))
    title: Mapped[str] = mapped_column(String(160))
    mode: Mapped[str] = mapped_column(String(32))
    current_scenario_budget_id: Mapped[str] = mapped_column(String(96))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    schema_version: Mapped[str] = mapped_column(String(16), default="0.1.0")
    scenario_budgets: Mapped[list[dict]] = mapped_column(JSON, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    notes: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[str] = mapped_column(String(64))
    updated_at: Mapped[str] = mapped_column(String(64), index=True)
    created_at_ts: Mapped[datetime] = mapped_column(
        "created_at_ts", DateTime(timezone=True), default=_utcnow
    )
    updated_at_ts: Mapped[datetime] = mapped_column(
        "updated_at_ts",
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
    )


class PersistedBudgetPlanVersion(Base):
    __tablename__ = "persisted_budget_plan_versions"

    version_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    budget_plan_id: Mapped[str] = mapped_column(
        ForeignKey("persisted_budget_plans.budget_plan_id", ondelete="CASCADE"),
        index=True,
    )
    trip_id: Mapped[str] = mapped_column(
        ForeignKey("persisted_trips.trip_id", ondelete="CASCADE"),
        index=True,
    )
    recorded_at: Mapped[str] = mapped_column(String(64), index=True)
    summary: Mapped[str] = mapped_column(String(240), default="")
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class PersistedActualSpendEvent(Base):
    __tablename__ = "persisted_actual_spend_events"

    spend_event_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    trip_id: Mapped[str] = mapped_column(
        ForeignKey("persisted_trips.trip_id", ondelete="CASCADE"),
        index=True,
    )
    budget_plan_id: Mapped[str] = mapped_column(
        ForeignKey("persisted_budget_plans.budget_plan_id", ondelete="CASCADE"),
        index=True,
    )
    category_key: Mapped[str] = mapped_column(String(64), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    occurred_at: Mapped[str] = mapped_column(String(64), index=True)
    source_kind: Mapped[str] = mapped_column(String(32), index=True)
    source_context: Mapped[str] = mapped_column(String(240))
    scenario_budget_id: Mapped[str | None] = mapped_column(String(96), nullable=True, index=True)
    saved_scenario_id: Mapped[str | None] = mapped_column(String(96), nullable=True, index=True)
    merchant_name: Mapped[str] = mapped_column(String(160), default="")
    source_ref: Mapped[str | None] = mapped_column(String(160), nullable=True)
    notes: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
    )
