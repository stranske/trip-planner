"""record the flight details TPP's fare and cabin rules read on a price

Revision ID: 20260922_01
Revises: 20260921_02
Create Date: 2026-09-22 00:00:00.000000

Travel-Plan-Permission's fare and cabin rules read `lowest_fare`, `fare_evidence_attached`,
`cabin_class` and `flight_duration_hours`, and fail when they are absent. Without them every
submission was blocked whatever the trip. All four are the traveller's own entries.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260922_01"
down_revision = "20260921_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("persisted_trip_prices", sa.Column("lowest_amount", sa.Float(), nullable=True))
    op.add_column(
        "persisted_trip_prices",
        sa.Column("evidence_attested", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("persisted_trip_prices", sa.Column("cabin_class", sa.String(32), nullable=True))
    op.add_column("persisted_trip_prices", sa.Column("flight_hours", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("persisted_trip_prices", "flight_hours")
    op.drop_column("persisted_trip_prices", "cabin_class")
    op.drop_column("persisted_trip_prices", "evidence_attested")
    op.drop_column("persisted_trip_prices", "lowest_amount")
