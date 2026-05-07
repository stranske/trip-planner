"""add selected planning mode to session state

Revision ID: 20260507_01
Revises: 20260412_01
Create Date: 2026-05-07 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260507_01"
down_revision = "20260412_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "persisted_planning_session_states",
        sa.Column(
            "selected_planning_mode",
            sa.String(length=32),
            nullable=False,
            server_default="collaborative",
        ),
    )


def downgrade() -> None:
    op.drop_column("persisted_planning_session_states", "selected_planning_mode")
