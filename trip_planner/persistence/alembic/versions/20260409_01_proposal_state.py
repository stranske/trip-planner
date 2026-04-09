"""add persisted proposal lifecycle state

Revision ID: 20260409_01
Revises: 20260408_03
Create Date: 2026-04-09 00:25:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260409_01"
down_revision = "20260408_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "persisted_proposal_states",
        sa.Column("proposal_state_id", sa.String(length=96), primary_key=True),
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
        sa.Column("proposal_id", sa.String(length=96), nullable=False),
        sa.Column("proposal_version", sa.String(length=96), nullable=False),
        sa.Column("scenario_id", sa.String(length=96), nullable=True),
        sa.Column("organization_id", sa.String(length=96), nullable=True),
        sa.Column("execution_id", sa.String(length=96), nullable=True),
        sa.Column("submission_status", sa.String(length=32), nullable=False),
        sa.Column("evaluation_status", sa.String(length=32), nullable=True),
        sa.Column("proposal_payload", sa.JSON(), nullable=False),
        sa.Column("submission_record", sa.JSON(), nullable=False),
        sa.Column("evaluation_record", sa.JSON(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in (
        "trip_id",
        "user_id",
        "proposal_id",
        "scenario_id",
        "organization_id",
        "execution_id",
        "submission_status",
        "evaluation_status",
    ):
        op.create_index(
            op.f(f"ix_persisted_proposal_states_{column}"),
            "persisted_proposal_states",
            [column],
            unique=False,
        )


def downgrade() -> None:
    for column in (
        "evaluation_status",
        "submission_status",
        "execution_id",
        "organization_id",
        "scenario_id",
        "proposal_id",
        "user_id",
        "trip_id",
    ):
        op.drop_index(
            op.f(f"ix_persisted_proposal_states_{column}"),
            table_name="persisted_proposal_states",
        )
    op.drop_table("persisted_proposal_states")
