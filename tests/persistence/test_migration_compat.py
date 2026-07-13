from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from trip_planner.persistence.db import ensure_database_ready, reset_database_state


def test_current_migrations_repair_database_stamped_at_previous_20260510_02(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "deployed.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(text("INSERT INTO alembic_version (version_num) VALUES ('20260510_02')"))
        connection.execute(text("CREATE TABLE persisted_trips (trip_id VARCHAR(96) PRIMARY KEY)"))
        connection.execute(
            text(
                "CREATE TABLE persisted_planning_session_states ("
                "session_state_id VARCHAR(128) PRIMARY KEY, "
                "trip_id VARCHAR(96) NOT NULL"
                ")"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE persisted_planning_ledger_entries ("
                "ledger_entry_id VARCHAR(96) PRIMARY KEY, "
                "trip_id VARCHAR(96) NOT NULL, "
                "session_state_id VARCHAR(96) NOT NULL, "
                "entry_type VARCHAR(40) NOT NULL, "
                "status VARCHAR(32) NOT NULL, "
                "category VARCHAR(64) NOT NULL, "
                "summary VARCHAR(400) NOT NULL, "
                "detail TEXT NOT NULL, "
                "source_message_ids JSON NOT NULL, "
                "source_refs JSON NOT NULL, "
                "metadata JSON NOT NULL, "
                "created_at DATETIME NOT NULL, "
                "updated_at DATETIME NOT NULL"
                ")"
            )
        )
        connection.execute(
            text(
                "INSERT INTO persisted_planning_ledger_entries ("
                "ledger_entry_id, trip_id, session_state_id, entry_type, status, category, "
                "summary, detail, source_message_ids, source_refs, metadata, created_at, updated_at"
                ") VALUES ("
                "'ledger-1', 'trip-1', 'session-1', 'open_question', 'active', 'route', "
                "'Question', '', '[]', '[]', '{}', '2026-05-12 00:00:00', "
                "'2026-05-12 00:00:00'"
                ")"
            )
        )

    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{db_path}")
    reset_database_state()
    ensure_database_ready()

    inspector = inspect(engine)
    assert inspector.has_table("persisted_planning_notebook_items")
    assert "item_type" in {
        column["name"] for column in inspector.get_columns("persisted_planning_ledger_entries")
    }
    assert {
        "notebook_focus_category",
        "notebook_focus_item_id",
    } <= {column["name"] for column in inspector.get_columns("persisted_planning_session_states")}

    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
            "20260712_01"
        )
        assert (
            connection.execute(
                text(
                    "SELECT item_type FROM persisted_planning_ledger_entries "
                    "WHERE ledger_entry_id = 'ledger-1'"
                )
            ).scalar_one()
            == "open_question"
        )
    assert "cost_coverage_state" in {
        column["name"] for column in inspector.get_columns("persisted_trips")
    }
    if inspector.has_table("user_accounts"):
        assert "travel_profile_state" in {
            column["name"] for column in inspector.get_columns("user_accounts")
        }

    reset_database_state()
