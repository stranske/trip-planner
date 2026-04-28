"""add persisted planner actions

Revision ID: 20260410_01
Revises: 20260409_01
Create Date: 2026-04-10 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260410_01"
down_revision = "20260409_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "persisted_planner_actions",
        sa.Column("planner_action_id", sa.String(length=96), primary_key=True),
        sa.Column(
            "trip_id",
            sa.String(length=96),
            sa.ForeignKey("persisted_trips.trip_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_state_id", sa.String(length=96), nullable=False),
        sa.Column(
            "activity_event_id",
            sa.String(length=96),
            sa.ForeignKey("persisted_activity_log_events.activity_event_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("occurred_at", sa.String(length=64), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("decision_id", sa.String(length=96), nullable=True),
        sa.Column("option_set_id", sa.String(length=96), nullable=True),
        sa.Column("option_id", sa.String(length=96), nullable=True),
        sa.Column("choice", sa.String(length=160), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        op.f("ix_persisted_planner_actions_trip_id"),
        "persisted_planner_actions",
        ["trip_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_planner_actions_session_state_id"),
        "persisted_planner_actions",
        ["session_state_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_planner_actions_activity_event_id"),
        "persisted_planner_actions",
        ["activity_event_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_planner_actions_occurred_at"),
        "persisted_planner_actions",
        ["occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_persisted_planner_actions_activity_event_id"),
        table_name="persisted_planner_actions",
    )
    op.drop_index(
        op.f("ix_persisted_planner_actions_occurred_at"),
        table_name="persisted_planner_actions",
    )
    op.drop_index(
        op.f("ix_persisted_planner_actions_session_state_id"),
        table_name="persisted_planner_actions",
    )
    op.drop_index(
        op.f("ix_persisted_planner_actions_trip_id"),
        table_name="persisted_planner_actions",
    )
    op.drop_table("persisted_planner_actions")
