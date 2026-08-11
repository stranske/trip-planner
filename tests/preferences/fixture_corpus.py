"""Test helpers for the packaged production fixture corpus.

Production code loads persona data from ``trip_planner.resources.preferences``.
Tests use the same corpus by default; ``load_fixture_corpus(path=...)`` remains
available for validation/error-case fixtures written to temporary files.
"""

from __future__ import annotations

import json
from pathlib import Path

from trip_planner.preferences.fixture_corpus import (
    IntendedInterpretation,
    TravelerFixture,
    _build_fixture,
    build_evidence_record,
    build_profile_from_overrides,
    load_fixture_map,
)
from trip_planner.preferences.schema import SCHEMA_VERSION

__all__ = [
    "IntendedInterpretation",
    "TravelerFixture",
    "build_evidence_record",
    "build_profile_from_overrides",
    "fixture_corpus_path",
    "load_fixture_corpus",
    "load_fixture_map",
]


def fixture_corpus_path() -> Path:
    import trip_planner.resources.preferences as preferences_resources

    return Path(preferences_resources.__file__).resolve().parent / "leisure_fixture_corpus.json"


def load_fixture_corpus(path: Path | None = None) -> list[TravelerFixture]:
    if path is None:
        from trip_planner.preferences.fixture_corpus import load_fixture_corpus as _load

        return _load()

    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            "fixture corpus schema_version must match trip_planner.preferences.schema.SCHEMA_VERSION"
        )
    fixtures = payload.get("fixtures", [])
    if not isinstance(fixtures, list):
        raise ValueError("fixtures must be a list")
    fixture_objects = [_build_fixture(index, entry) for index, entry in enumerate(fixtures)]
    fixture_ids = [fixture.id for fixture in fixture_objects]
    if len(set(fixture_ids)) != len(fixture_ids):
        raise ValueError("fixture corpus ids must be unique")
    return fixture_objects
