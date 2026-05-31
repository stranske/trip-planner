"""Create persisted trip table."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260407_02"
down_revision = "20260407_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "persisted_trips",
        sa.Column("trip_id", sa.String(length=96), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("summary", sa.String(length=600), nullable=False, server_default=""),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("start_date", sa.String(length=32), nullable=True),
        sa.Column("end_date", sa.String(length=32), nullable=True),
        sa.Column("duration_days", sa.Integer(), nullable=True),
        sa.Column("primary_regions", sa.JSON(), nullable=False),
        sa.Column(
            "traveler_party_kind",
            sa.String(length=32),
            nullable=False,
            server_default="solo",
        ),
        sa.Column("traveler_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("traveler_notes", sa.String(length=240), nullable=False, server_default=""),
        sa.Column("leisure_profile_id", sa.String(length=96), nullable=True),
        sa.Column("business_profile_id", sa.String(length=96), nullable=True),
        sa.Column("objective_id", sa.String(length=96), nullable=True),
        sa.Column("option_set_ids", sa.JSON(), nullable=False),
        sa.Column("itinerary_state_id", sa.String(length=96), nullable=True),
        sa.Column("budget_state_id", sa.String(length=96), nullable=True),
        sa.Column("policy_state_id", sa.String(length=96), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user_accounts.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("trip_id"),
    )
    op.create_index(
        op.f("ix_persisted_trips_user_id"),
        "persisted_trips",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_persisted_trips_user_id"), table_name="persisted_trips")
    op.drop_table("persisted_trips")
