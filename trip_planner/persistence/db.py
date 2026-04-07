"""Database and migration helpers for runtime-backed persistence."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

_DEFAULT_SQLITE_PATH = Path(__file__).resolve().parents[2] / ".tmp" / "trip_planner.db"
_ENGINE_CACHE: dict[str, Engine] = {}
_SESSION_FACTORY_CACHE: dict[str, sessionmaker[Session]] = {}
_MIGRATED_URLS: set[str] = set()


class Base(DeclarativeBase):
    """Base SQLAlchemy model for persistence tables."""


def get_database_url() -> str:
    return os.environ.get(
        "TRIP_PLANNER_DATABASE_URL", f"sqlite:///{_DEFAULT_SQLITE_PATH}"
    )


def _engine_options(url: str) -> dict[str, Any]:
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {}


def get_engine(url: str | None = None) -> Engine:
    resolved_url = url or get_database_url()
    engine = _ENGINE_CACHE.get(resolved_url)
    if engine is None:
        if resolved_url.startswith("sqlite"):
            _DEFAULT_SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(
            resolved_url, future=True, **_engine_options(resolved_url)
        )
        _ENGINE_CACHE[resolved_url] = engine
    return engine


def get_session_factory(url: str | None = None) -> sessionmaker[Session]:
    resolved_url = url or get_database_url()
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
    resolved_url = url or get_database_url()
    if resolved_url in _MIGRATED_URLS:
        return

    from trip_planner.persistence.models import account, session  # noqa: F401

    if resolved_url.startswith("sqlite"):
        database_path = Path(resolved_url.replace("sqlite:///", "", 1))
        database_path.parent.mkdir(parents=True, exist_ok=True)

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
