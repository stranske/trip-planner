"""Create persisted saved-scenario and activity-history tables."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260407_03"
down_revision = "20260407_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "persisted_saved_scenarios",
        sa.Column("saved_scenario_id", sa.String(length=96), nullable=False),
        sa.Column("trip_id", sa.String(length=96), nullable=False),
        sa.Column("current_version_id", sa.String(length=96), nullable=False),
        sa.Column("versions", sa.JSON(), nullable=False),
        sa.Column("comparisons", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("notes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["trip_id"], ["persisted_trips.trip_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("saved_scenario_id"),
    )
    op.create_index(
        op.f("ix_persisted_saved_scenarios_trip_id"),
        "persisted_saved_scenarios",
        ["trip_id"],
        unique=False,
    )

    op.create_table(
        "persisted_activity_log_events",
        sa.Column("activity_event_id", sa.String(length=96), nullable=False),
        sa.Column("trip_id", sa.String(length=96), nullable=False),
        sa.Column("session_state_id", sa.String(length=96), nullable=False),
        sa.Column("occurred_at", sa.String(length=64), nullable=False),
        sa.Column("event_kind", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.String(length=600), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=False, server_default="system"),
        sa.Column("related_decision_id", sa.String(length=96), nullable=True),
        sa.Column("related_option_set_id", sa.String(length=96), nullable=True),
        sa.Column("saved_scenario_id", sa.String(length=96), nullable=True),
        sa.Column("budget_plan_id", sa.String(length=96), nullable=True),
        sa.Column("scenario_budget_id", sa.String(length=96), nullable=True),
        sa.Column("checkpoint_id", sa.String(length=96), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("notes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["trip_id"], ["persisted_trips.trip_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("activity_event_id"),
    )
    op.create_index(
        op.f("ix_persisted_activity_log_events_trip_id"),
        "persisted_activity_log_events",
        ["trip_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_activity_log_events_occurred_at"),
        "persisted_activity_log_events",
        ["occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_persisted_activity_log_events_occurred_at"),
        table_name="persisted_activity_log_events",
    )
    op.drop_index(
        op.f("ix_persisted_activity_log_events_trip_id"),
        table_name="persisted_activity_log_events",
    )
    op.drop_table("persisted_activity_log_events")
    op.drop_index(
        op.f("ix_persisted_saved_scenarios_trip_id"),
        table_name="persisted_saved_scenarios",
    )
    op.drop_table("persisted_saved_scenarios")
