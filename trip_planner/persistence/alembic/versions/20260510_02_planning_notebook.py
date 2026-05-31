"""add persisted planning notebook items and session focus columns

Revision ID: 20260510_02
Revises: 20260510_01
Create Date: 2026-05-10 00:00:01.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260510_02"
down_revision = "20260510_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "persisted_planning_notebook_items",
        sa.Column("notebook_item_id", sa.String(length=64), primary_key=True),
        sa.Column(
            "trip_id",
            sa.String(length=96),
            sa.ForeignKey("persisted_trips.trip_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_state_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("category", sa.String(length=48), nullable=False, server_default="other"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("priority", sa.String(length=16), nullable=False, server_default="normal"),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="user"),
        sa.Column("linked_ledger_entry_id", sa.String(length=96), nullable=True),
        sa.Column("source_message_ids", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        op.f("ix_persisted_planning_notebook_items_trip_id"),
        "persisted_planning_notebook_items",
        ["trip_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_planning_notebook_items_session_state_id"),
        "persisted_planning_notebook_items",
        ["session_state_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_planning_notebook_items_category"),
        "persisted_planning_notebook_items",
        ["category"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_planning_notebook_items_status"),
        "persisted_planning_notebook_items",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_planning_notebook_items_trip_updated_at"),
        "persisted_planning_notebook_items",
        ["trip_id", "updated_at"],
        unique=False,
    )

    op.add_column(
        "persisted_planning_session_states",
        sa.Column("notebook_focus_category", sa.String(length=48), nullable=True),
    )
    op.add_column(
        "persisted_planning_session_states",
        sa.Column("notebook_focus_item_id", sa.String(length=96), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("persisted_planning_session_states", "notebook_focus_item_id")
    op.drop_column("persisted_planning_session_states", "notebook_focus_category")
    op.drop_index(
        op.f("ix_persisted_planning_notebook_items_trip_updated_at"),
        table_name="persisted_planning_notebook_items",
    )
    op.drop_index(
        op.f("ix_persisted_planning_notebook_items_status"),
        table_name="persisted_planning_notebook_items",
    )
    op.drop_index(
        op.f("ix_persisted_planning_notebook_items_category"),
        table_name="persisted_planning_notebook_items",
    )
    op.drop_index(
        op.f("ix_persisted_planning_notebook_items_session_state_id"),
        table_name="persisted_planning_notebook_items",
    )
    op.drop_index(
        op.f("ix_persisted_planning_notebook_items_trip_id"),
        table_name="persisted_planning_notebook_items",
    )
    op.drop_table("persisted_planning_notebook_items")
