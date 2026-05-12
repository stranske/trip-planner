"""repair planning notebook schema for already-deployed databases

Revision ID: 20260512_01
Revises: 20260510_02
Create Date: 2026-05-12 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260512_01"
down_revision = "20260510_02"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return set()
    names: set[str] = set()
    for column in inspector.get_columns(table_name):
        name = column.get("name")
        if isinstance(name, str):
            names.add(name)
    return names


def _indexes(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return set()
    names: set[str] = set()
    for index in inspector.get_indexes(table_name):
        name = index.get("name")
        if isinstance(name, str):
            names.add(name)
    return names


def _add_index_if_missing(table_name: str, index_name: str, columns: list[str]) -> None:
    if index_name not in _indexes(table_name):
        op.create_index(index_name, table_name, columns, unique=False)


def _repair_planning_ledger() -> None:
    columns = _columns("persisted_planning_ledger_entries")
    if not columns:
        return

    if "item_type" not in columns:
        op.add_column(
            "persisted_planning_ledger_entries",
            sa.Column("item_type", sa.String(length=48), nullable=True),
        )
        if "entry_type" in columns:
            op.execute(
                "UPDATE persisted_planning_ledger_entries "
                "SET item_type = COALESCE(item_type, entry_type, 'note')"
            )
        else:
            op.execute(
                "UPDATE persisted_planning_ledger_entries "
                "SET item_type = COALESCE(item_type, 'note')"
            )

    _add_index_if_missing(
        "persisted_planning_ledger_entries",
        op.f("ix_persisted_planning_ledger_entries_item_type"),
        ["item_type"],
    )
    _add_index_if_missing(
        "persisted_planning_ledger_entries",
        op.f("ix_persisted_planning_ledger_entries_trip_updated_at"),
        ["trip_id", "updated_at"],
    )


def _create_notebook_table_if_missing() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("persisted_planning_notebook_items"):
        return

    op.create_table(
        "persisted_planning_notebook_items",
        sa.Column("notebook_item_id", sa.String(length=64), primary_key=True),
        sa.Column(
            "trip_id",
            sa.String(length=96),
            sa.ForeignKey("persisted_trips.trip_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_state_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("category", sa.String(length=48), nullable=False, server_default="other"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("priority", sa.String(length=16), nullable=False, server_default="normal"),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="user"),
        sa.Column("linked_ledger_entry_id", sa.String(length=96), nullable=True),
        sa.Column("source_message_ids", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def _repair_notebook_indexes() -> None:
    for index_name, columns in (
        (op.f("ix_persisted_planning_notebook_items_trip_id"), ["trip_id"]),
        (
            op.f("ix_persisted_planning_notebook_items_session_state_id"),
            ["session_state_id"],
        ),
        (op.f("ix_persisted_planning_notebook_items_category"), ["category"]),
        (op.f("ix_persisted_planning_notebook_items_status"), ["status"]),
        (
            op.f("ix_persisted_planning_notebook_items_trip_updated_at"),
            ["trip_id", "updated_at"],
        ),
    ):
        _add_index_if_missing("persisted_planning_notebook_items", index_name, columns)


def _repair_session_focus_columns() -> None:
    columns = _columns("persisted_planning_session_states")
    if "notebook_focus_category" not in columns:
        op.add_column(
            "persisted_planning_session_states",
            sa.Column("notebook_focus_category", sa.String(length=48), nullable=True),
        )
    if "notebook_focus_item_id" not in columns:
        op.add_column(
            "persisted_planning_session_states",
            sa.Column("notebook_focus_item_id", sa.String(length=96), nullable=True),
        )


def upgrade() -> None:
    _repair_planning_ledger()
    _create_notebook_table_if_missing()
    _repair_notebook_indexes()
    _repair_session_focus_columns()


def downgrade() -> None:
    pass
