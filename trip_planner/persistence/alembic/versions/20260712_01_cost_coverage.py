"""add persisted trip cost and evidence coverage state

Revision ID: 20260712_01
Revises: 20260512_01
Create Date: 2026-07-12 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260712_01"
down_revision = "20260512_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    table_names = set(inspector.get_table_names())
    if "user_accounts" in table_names:
        account_columns = {column["name"] for column in inspector.get_columns("user_accounts")}
        if "travel_profile_state" not in account_columns:
            op.add_column(
                "user_accounts",
                sa.Column(
                    "travel_profile_state",
                    sa.JSON(),
                    nullable=False,
                    server_default=sa.text("'{}'"),
                ),
            )
    trip_columns = {column["name"] for column in inspector.get_columns("persisted_trips")}
    if "cost_coverage_state" not in trip_columns:
        op.add_column(
            "persisted_trips",
            sa.Column(
                "cost_coverage_state",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'"),
            ),
        )


def downgrade() -> None:
    op.drop_column("persisted_trips", "cost_coverage_state")
    op.drop_column("user_accounts", "travel_profile_state")
