"""add planner checkpoints and user-visible memory artifacts

Revision ID: 20260412_01
Revises: 20260410_01
Create Date: 2026-04-12 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260412_01"
down_revision = "20260410_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "persisted_planner_checkpoints",
        sa.Column("checkpoint_id", sa.String(length=96), primary_key=True),
        sa.Column(
            "trip_id",
            sa.String(length=96),
            sa.ForeignKey("persisted_trips.trip_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_state_id", sa.String(length=96), nullable=False),
        sa.Column("checkpoint_kind", sa.String(length=32), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.Column("summary", sa.String(length=600), nullable=False),
        sa.Column("source_message_ids", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        op.f("ix_persisted_planner_checkpoints_trip_id"),
        "persisted_planner_checkpoints",
        ["trip_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_planner_checkpoints_session_state_id"),
        "persisted_planner_checkpoints",
        ["session_state_id"],
        unique=False,
    )

    op.create_table(
        "persisted_planner_memory_artifacts",
        sa.Column("memory_artifact_id", sa.String(length=96), primary_key=True),
        sa.Column(
            "trip_id",
            sa.String(length=96),
            sa.ForeignKey("persisted_trips.trip_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_state_id", sa.String(length=96), nullable=False),
        sa.Column(
            "checkpoint_id",
            sa.String(length=96),
            sa.ForeignKey("persisted_planner_checkpoints.checkpoint_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("artifact_kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("summary", sa.String(length=600), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("source_message_ids", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        op.f("ix_persisted_planner_memory_artifacts_trip_id"),
        "persisted_planner_memory_artifacts",
        ["trip_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_planner_memory_artifacts_session_state_id"),
        "persisted_planner_memory_artifacts",
        ["session_state_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_planner_memory_artifacts_checkpoint_id"),
        "persisted_planner_memory_artifacts",
        ["checkpoint_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_persisted_planner_memory_artifacts_checkpoint_id"),
        table_name="persisted_planner_memory_artifacts",
    )
    op.drop_index(
        op.f("ix_persisted_planner_memory_artifacts_session_state_id"),
        table_name="persisted_planner_memory_artifacts",
    )
    op.drop_index(
        op.f("ix_persisted_planner_memory_artifacts_trip_id"),
        table_name="persisted_planner_memory_artifacts",
    )
    op.drop_table("persisted_planner_memory_artifacts")

    op.drop_index(
        op.f("ix_persisted_planner_checkpoints_session_state_id"),
        table_name="persisted_planner_checkpoints",
    )
    op.drop_index(
        op.f("ix_persisted_planner_checkpoints_trip_id"),
        table_name="persisted_planner_checkpoints",
    )
    op.drop_table("persisted_planner_checkpoints")
