"""add persisted planning session state

Revision ID: 20260408_01
Revises: 20260407_03
Create Date: 2026-04-08 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260408_01"
down_revision = "20260407_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "persisted_planning_session_states",
        sa.Column("session_state_id", sa.String(length=96), primary_key=True),
        sa.Column(
            "trip_id",
            sa.String(length=96),
            sa.ForeignKey("persisted_trips.trip_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(length=96),
            sa.ForeignKey("user_accounts.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("owner_profile_id", sa.String(length=96), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.String(length=64), nullable=False),
        sa.Column("last_updated_at", sa.String(length=64), nullable=False),
        sa.Column("interaction_state", sa.JSON(), nullable=False),
        sa.Column("recent_option_presentations", sa.JSON(), nullable=False),
        sa.Column("pending_decisions", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_checkpoint_id", sa.String(length=96), nullable=True),
        sa.Column("current_saved_scenario_id", sa.String(length=96), nullable=True),
        sa.Column("active_budget_plan_id", sa.String(length=96), nullable=True),
        sa.Column("activity_log_id", sa.String(length=96), nullable=True),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("notes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_persisted_planning_session_states_trip_id",
        "persisted_planning_session_states",
        ["trip_id"],
    )
    op.create_index(
        "ix_persisted_planning_session_states_user_id",
        "persisted_planning_session_states",
        ["user_id"],
    )
    op.create_index(
        "ix_persisted_planning_session_states_last_updated_at",
        "persisted_planning_session_states",
        ["last_updated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_persisted_planning_session_states_last_updated_at",
        table_name="persisted_planning_session_states",
    )
    op.drop_index(
        "ix_persisted_planning_session_states_user_id",
        table_name="persisted_planning_session_states",
    )
    op.drop_index(
        "ix_persisted_planning_session_states_trip_id",
        table_name="persisted_planning_session_states",
    )
    op.drop_table("persisted_planning_session_states")
