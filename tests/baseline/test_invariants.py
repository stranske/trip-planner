"""Tier 3 invariants on every transport fixture."""

from __future__ import annotations

import pytest
from baseline_kit import assert_invariants, load_catalog

from . import invariants
from .conftest import CATALOG_PATH

_FIXTURES = load_catalog(CATALOG_PATH)["fixtures"]


@pytest.mark.parametrize("fixture", _FIXTURES, ids=[f.replace(".json", "") for f in _FIXTURES])
def test_option_invariants(fixture):
    assert_invariants(invariants.check_option(fixture), context=fixture)
