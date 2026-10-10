"""persist truthful TPP portal handoff preparation state

Revision ID: 20260928_01
Revises: 20260922_01
Create Date: 2026-09-28 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260928_01"
down_revision = "20260922_01"
branch_labels = None
depends_on = None


def _columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("persisted_proposal_states"):
        return set()
    return {
        str(column["name"])
        for column in inspector.get_columns("persisted_proposal_states")
        if column.get("name")
    }


def upgrade() -> None:
    columns = _columns()
    if columns and "portal_handoff" not in columns:
        op.add_column(
            "persisted_proposal_states",
            sa.Column("portal_handoff", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    if "portal_handoff" in _columns():
        op.drop_column("persisted_proposal_states", "portal_handoff")
