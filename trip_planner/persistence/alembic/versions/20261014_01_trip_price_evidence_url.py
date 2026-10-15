"""record a link to the fare a traveller chose, as fare evidence

Revision ID: 20261014_01
Revises: 20260928_01
Create Date: 2026-10-14 00:00:00.000000

A traveller finds fares on Google Flights (or an airline site) through the link the Budget
tab builds for the trip, and pastes back the fare they chose and the page's link. The link
is printed on the approval packet and sent with the airfare to Travel-Plan-Permission.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261014_01"
down_revision = "20260928_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("persisted_trip_prices", sa.Column("evidence_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("persisted_trip_prices", "evidence_url")
