"""add human-entered trip prices

Revision ID: 20260921_02
Revises: 20260921_01
Create Date: 2026-09-21 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260921_02"
down_revision = "20260921_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "persisted_trip_prices",
        sa.Column("trip_price_id", sa.String(length=128), primary_key=True),
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
        sa.Column("component", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("entered_by", sa.String(length=160), nullable=False),
        sa.Column("note", sa.String(length=400), nullable=False, server_default=""),
        sa.Column("captured_at", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("trip_id", "component", name="uq_persisted_trip_prices_trip_component"),
    )
    op.create_index(
        op.f("ix_persisted_trip_prices_trip_id"),
        "persisted_trip_prices",
        ["trip_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_trip_prices_user_id"),
        "persisted_trip_prices",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_persisted_trip_prices_user_id"), table_name="persisted_trip_prices")
    op.drop_index(op.f("ix_persisted_trip_prices_trip_id"), table_name="persisted_trip_prices")
    op.drop_table("persisted_trip_prices")
