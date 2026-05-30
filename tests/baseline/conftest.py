"""Fixtures and catalog loading for the trip-planner baseline kit."""

from __future__ import annotations

import functools
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
CATALOG_PATH = HERE / "catalog.yaml"

# Ensure the repo root is importable (so `trip_planner` resolves under pytest).
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@functools.lru_cache(maxsize=1)
def load_catalog_cached():
    from baseline_kit import load_catalog

    return load_catalog(CATALOG_PATH)


@pytest.fixture(scope="session")
def catalog():
    return load_catalog_cached()
