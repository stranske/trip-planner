"""add persisted planning ledger entries

Revision ID: 20260510_01
Revises: 20260507_01
Create Date: 2026-05-10 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260510_01"
down_revision = "20260507_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "persisted_planning_ledger_entries",
        sa.Column("ledger_entry_id", sa.String(length=64), primary_key=True),
        sa.Column(
            "trip_id",
            sa.String(length=96),
            sa.ForeignKey("persisted_trips.trip_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_state_id", sa.String(length=128), nullable=False),
        sa.Column("item_type", sa.String(length=48), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.String(length=280), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("source_message_ids", sa.JSON(), nullable=False),
        sa.Column("source_refs", sa.JSON(), nullable=False),
        sa.Column("related_option_id", sa.String(length=128), nullable=True),
        sa.Column("related_decision_id", sa.String(length=96), nullable=True),
        sa.Column("supersedes_entry_id", sa.String(length=96), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        op.f("ix_persisted_planning_ledger_entries_trip_id"),
        "persisted_planning_ledger_entries",
        ["trip_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_planning_ledger_entries_session_state_id"),
        "persisted_planning_ledger_entries",
        ["session_state_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_planning_ledger_entries_item_type"),
        "persisted_planning_ledger_entries",
        ["item_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_planning_ledger_entries_status"),
        "persisted_planning_ledger_entries",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_planning_ledger_entries_trip_updated_at"),
        "persisted_planning_ledger_entries",
        ["trip_id", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_persisted_planning_ledger_entries_trip_updated_at"),
        table_name="persisted_planning_ledger_entries",
    )
    op.drop_index(
        op.f("ix_persisted_planning_ledger_entries_status"),
        table_name="persisted_planning_ledger_entries",
    )
    op.drop_index(
        op.f("ix_persisted_planning_ledger_entries_item_type"),
        table_name="persisted_planning_ledger_entries",
    )
    op.drop_index(
        op.f("ix_persisted_planning_ledger_entries_session_state_id"),
        table_name="persisted_planning_ledger_entries",
    )
    op.drop_index(
        op.f("ix_persisted_planning_ledger_entries_trip_id"),
        table_name="persisted_planning_ledger_entries",
    )
    op.drop_table("persisted_planning_ledger_entries")
