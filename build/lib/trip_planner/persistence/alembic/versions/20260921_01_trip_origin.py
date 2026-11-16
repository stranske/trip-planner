"""add the trip origin the planner needs to measure a journey

A trip recorded only where the traveller was going, never where they were leaving
from, so no journey could be measured and every distance-derived figure collapsed to
the same value regardless of destination.

Revision ID: 20260921_01
Revises: 20260512_01
Create Date: 2026-09-21 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260921_01"
down_revision = "20260512_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("persisted_trips") as batch:
        batch.add_column(sa.Column("origin", sa.String(length=120), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("persisted_trips") as batch:
        batch.drop_column("origin")
