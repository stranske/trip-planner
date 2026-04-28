"""add persisted budget plan and actual-spend state

Revision ID: 20260408_02
Revises: 20260408_01
Create Date: 2026-04-08 00:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260408_02"
down_revision = "20260408_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "persisted_budget_plans",
        sa.Column("budget_plan_id", sa.String(length=96), primary_key=True),
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
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("current_scenario_budget_id", sa.String(length=96), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("scenario_budgets", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("notes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.String(length=64), nullable=False),
        sa.Column("created_at_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at_ts", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        op.f("ix_persisted_budget_plans_trip_id"),
        "persisted_budget_plans",
        ["trip_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_budget_plans_user_id"),
        "persisted_budget_plans",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_budget_plans_updated_at"),
        "persisted_budget_plans",
        ["updated_at"],
        unique=False,
    )

    op.create_table(
        "persisted_budget_plan_versions",
        sa.Column("version_id", sa.String(length=128), primary_key=True),
        sa.Column(
            "budget_plan_id",
            sa.String(length=96),
            sa.ForeignKey("persisted_budget_plans.budget_plan_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "trip_id",
            sa.String(length=96),
            sa.ForeignKey("persisted_trips.trip_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("recorded_at", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.String(length=240), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        op.f("ix_persisted_budget_plan_versions_budget_plan_id"),
        "persisted_budget_plan_versions",
        ["budget_plan_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_budget_plan_versions_trip_id"),
        "persisted_budget_plan_versions",
        ["trip_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_budget_plan_versions_recorded_at"),
        "persisted_budget_plan_versions",
        ["recorded_at"],
        unique=False,
    )

    op.create_table(
        "persisted_actual_spend_events",
        sa.Column("spend_event_id", sa.String(length=96), primary_key=True),
        sa.Column(
            "trip_id",
            sa.String(length=96),
            sa.ForeignKey("persisted_trips.trip_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "budget_plan_id",
            sa.String(length=96),
            sa.ForeignKey("persisted_budget_plans.budget_plan_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category_key", sa.String(length=64), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("occurred_at", sa.String(length=64), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("source_context", sa.String(length=240), nullable=False),
        sa.Column("scenario_budget_id", sa.String(length=96), nullable=True),
        sa.Column("saved_scenario_id", sa.String(length=96), nullable=True),
        sa.Column("merchant_name", sa.String(length=160), nullable=False),
        sa.Column("source_ref", sa.String(length=160), nullable=True),
        sa.Column("notes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        op.f("ix_persisted_actual_spend_events_trip_id"),
        "persisted_actual_spend_events",
        ["trip_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_actual_spend_events_budget_plan_id"),
        "persisted_actual_spend_events",
        ["budget_plan_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_actual_spend_events_category_key"),
        "persisted_actual_spend_events",
        ["category_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_actual_spend_events_occurred_at"),
        "persisted_actual_spend_events",
        ["occurred_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_actual_spend_events_source_kind"),
        "persisted_actual_spend_events",
        ["source_kind"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_actual_spend_events_scenario_budget_id"),
        "persisted_actual_spend_events",
        ["scenario_budget_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persisted_actual_spend_events_saved_scenario_id"),
        "persisted_actual_spend_events",
        ["saved_scenario_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_persisted_actual_spend_events_saved_scenario_id"),
        table_name="persisted_actual_spend_events",
    )
    op.drop_index(
        op.f("ix_persisted_actual_spend_events_scenario_budget_id"),
        table_name="persisted_actual_spend_events",
    )
    op.drop_index(
        op.f("ix_persisted_actual_spend_events_source_kind"),
        table_name="persisted_actual_spend_events",
    )
    op.drop_index(
        op.f("ix_persisted_actual_spend_events_occurred_at"),
        table_name="persisted_actual_spend_events",
    )
    op.drop_index(
        op.f("ix_persisted_actual_spend_events_category_key"),
        table_name="persisted_actual_spend_events",
    )
    op.drop_index(
        op.f("ix_persisted_actual_spend_events_budget_plan_id"),
        table_name="persisted_actual_spend_events",
    )
    op.drop_index(
        op.f("ix_persisted_actual_spend_events_trip_id"),
        table_name="persisted_actual_spend_events",
    )
    op.drop_table("persisted_actual_spend_events")

    op.drop_index(
        op.f("ix_persisted_budget_plan_versions_recorded_at"),
        table_name="persisted_budget_plan_versions",
    )
    op.drop_index(
        op.f("ix_persisted_budget_plan_versions_trip_id"),
        table_name="persisted_budget_plan_versions",
    )
    op.drop_index(
        op.f("ix_persisted_budget_plan_versions_budget_plan_id"),
        table_name="persisted_budget_plan_versions",
    )
    op.drop_table("persisted_budget_plan_versions")

    op.drop_index(
        op.f("ix_persisted_budget_plans_updated_at"),
        table_name="persisted_budget_plans",
    )
    op.drop_index(
        op.f("ix_persisted_budget_plans_user_id"),
        table_name="persisted_budget_plans",
    )
    op.drop_index(
        op.f("ix_persisted_budget_plans_trip_id"),
        table_name="persisted_budget_plans",
    )
    op.drop_table("persisted_budget_plans")
