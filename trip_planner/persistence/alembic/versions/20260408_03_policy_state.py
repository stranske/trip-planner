"""add persisted policy import state

Revision ID: 20260408_03
Revises: 20260408_02
Create Date: 2026-04-08 22:05:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260408_03"
down_revision = "20260408_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "persisted_policy_states",
        sa.Column("policy_state_id", sa.String(length=96), primary_key=True),
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
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("source_request_id", sa.String(length=96), nullable=False),
        sa.Column("source_correlation_id", sa.String(length=96), nullable=False),
        sa.Column("policy_id", sa.String(length=96), nullable=False),
        sa.Column("organization_id", sa.String(length=96), nullable=False),
        sa.Column("policy_version", sa.String(length=48), nullable=False),
        sa.Column("sync_status", sa.String(length=32), nullable=False),
        sa.Column("imported_at", sa.String(length=64), nullable=False),
        sa.Column("constraint_set", sa.JSON(), nullable=False),
        sa.Column("organization_context", sa.JSON(), nullable=False),
        sa.Column("freshness", sa.JSON(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("notes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        op.f("ix_persisted_policy_states_trip_id"),
        "persisted_policy_states",
        ["trip_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_policy_states_user_id"),
        "persisted_policy_states",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_policy_states_policy_id"),
        "persisted_policy_states",
        ["policy_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_policy_states_organization_id"),
        "persisted_policy_states",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_policy_states_sync_status"),
        "persisted_policy_states",
        ["sync_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_policy_states_imported_at"),
        "persisted_policy_states",
        ["imported_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_persisted_policy_states_imported_at"),
        table_name="persisted_policy_states",
    )
    op.drop_index(
        op.f("ix_persisted_policy_states_sync_status"),
        table_name="persisted_policy_states",
    )
    op.drop_index(
        op.f("ix_persisted_policy_states_organization_id"),
        table_name="persisted_policy_states",
    )
    op.drop_index(
        op.f("ix_persisted_policy_states_policy_id"),
        table_name="persisted_policy_states",
    )
    op.drop_index(
        op.f("ix_persisted_policy_states_user_id"),
        table_name="persisted_policy_states",
    )
    op.drop_index(
        op.f("ix_persisted_policy_states_trip_id"),
        table_name="persisted_policy_states",
    )
    op.drop_table("persisted_policy_states")
