from trip_planner.persistence.db import get_database_url, normalize_database_url


def test_normalize_database_url_preserves_sqlite_urls() -> None:
    assert normalize_database_url("sqlite:////tmp/trip_planner.db") == "sqlite:////tmp/trip_planner.db"


def test_normalize_database_url_uses_psycopg_driver_for_render_postgres_urls() -> None:
    assert (
        normalize_database_url("postgresql://user:pass@host:5432/trip_planner")
        == "postgresql+psycopg://user:pass@host:5432/trip_planner"
    )
    assert (
        normalize_database_url("postgres://user:pass@host:5432/trip_planner")
        == "postgresql+psycopg://user:pass@host:5432/trip_planner"
    )


def test_normalize_database_url_keeps_explicit_psycopg_driver() -> None:
    assert (
        normalize_database_url("postgresql+psycopg://user:pass@host:5432/trip_planner")
        == "postgresql+psycopg://user:pass@host:5432/trip_planner"
    )


def test_get_database_url_normalizes_configured_postgres_url(monkeypatch) -> None:
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", "postgresql://user:pass@host:5432/trip_planner")

    assert get_database_url() == "postgresql+psycopg://user:pass@host:5432/trip_planner"
