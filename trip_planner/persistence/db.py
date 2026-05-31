"""Database and migration helpers for runtime-backed persistence."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

_DEFAULT_SQLITE_PATH = Path(__file__).resolve().parents[2] / ".tmp" / "trip_planner.db"
_ENGINE_CACHE: dict[str, Engine] = {}
_SESSION_FACTORY_CACHE: dict[str, sessionmaker[Session]] = {}
_MIGRATED_URLS: set[str] = set()
_POSTGRESQL_URL_PREFIX = "postgresql://"
_POSTGRES_URL_PREFIX = "postgres://"
_POSTGRESQL_PSYCOPG_URL_PREFIX = "postgresql+psycopg://"


class Base(DeclarativeBase):
    """Base SQLAlchemy model for persistence tables."""


def get_database_url() -> str:
    return normalize_database_url(
        os.environ.get("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{_DEFAULT_SQLITE_PATH}")
    )


def normalize_database_url(url: str) -> str:
    if url.startswith(_POSTGRESQL_PSYCOPG_URL_PREFIX):
        return url
    if url.startswith(_POSTGRESQL_URL_PREFIX):
        return f"{_POSTGRESQL_PSYCOPG_URL_PREFIX}{url[len(_POSTGRESQL_URL_PREFIX):]}"
    if url.startswith(_POSTGRES_URL_PREFIX):
        return f"{_POSTGRESQL_PSYCOPG_URL_PREFIX}{url[len(_POSTGRES_URL_PREFIX):]}"
    return url


def _engine_options(url: str) -> dict[str, Any]:
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {}


def _sqlite_database_path(url: str) -> Path | None:
    parsed_url = make_url(url)
    if parsed_url.get_backend_name() != "sqlite" or not parsed_url.database:
        return None
    if parsed_url.database == ":memory:":
        return None
    return Path(parsed_url.database).expanduser()


def _ensure_sqlite_parent_dir(url: str) -> None:
    database_path = _sqlite_database_path(url)
    if database_path is not None:
        database_path.parent.mkdir(parents=True, exist_ok=True)


def get_engine(url: str | None = None) -> Engine:
    resolved_url = normalize_database_url(url or get_database_url())
    engine = _ENGINE_CACHE.get(resolved_url)
    if engine is None:
        _ensure_sqlite_parent_dir(resolved_url)
        engine = create_engine(resolved_url, future=True, **_engine_options(resolved_url))
        _ENGINE_CACHE[resolved_url] = engine
    return engine


def get_session_factory(url: str | None = None) -> sessionmaker[Session]:
    resolved_url = normalize_database_url(url or get_database_url())
    session_factory = _SESSION_FACTORY_CACHE.get(resolved_url)
    if session_factory is None:
        session_factory = sessionmaker(
            bind=get_engine(resolved_url),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        _SESSION_FACTORY_CACHE[resolved_url] = session_factory
    return session_factory


def get_db_session() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def ensure_database_ready(url: str | None = None) -> None:
    resolved_url = normalize_database_url(url or get_database_url())
    if resolved_url in _MIGRATED_URLS:
        return

    from trip_planner.persistence.models import (  # noqa: F401
        account,
        activity,
        budget,  # noqa: F401
        planner_memory,  # noqa: F401
        planning_ledger,  # noqa: F401
        policy,
        proposal,
        scenario,
        session,
        trip,
    )

    _ensure_sqlite_parent_dir(resolved_url)

    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.attributes["configure_logger"] = False
    config.set_main_option(
        "script_location",
        str(Path(__file__).resolve().parent / "alembic"),
    )
    config.set_main_option("sqlalchemy.url", resolved_url)
    command.upgrade(config, "head")
    _MIGRATED_URLS.add(resolved_url)


def reset_database_state() -> None:
    """Clear cached engines for tests that swap database URLs."""

    for engine in _ENGINE_CACHE.values():
        engine.dispose()
    _ENGINE_CACHE.clear()
    _SESSION_FACTORY_CACHE.clear()
    _MIGRATED_URLS.clear()
