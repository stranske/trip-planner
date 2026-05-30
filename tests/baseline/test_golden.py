"""Tier 0/1 golden masters of each transport fixture's derived metrics.

Re-bless after an intended change:
    pytest tests/baseline/test_golden.py --force-regen
then review and commit the updated baseline files.
"""

from __future__ import annotations

import pytest
from baseline_kit import check_metrics, load_catalog

from . import adapter
from .conftest import CATALOG_PATH

_FIXTURES = load_catalog(CATALOG_PATH)["fixtures"]


@pytest.mark.parametrize("fixture", _FIXTURES, ids=[f.replace(".json", "") for f in _FIXTURES])
def test_transport_metrics_golden(fixture, num_regression):
    check_metrics(num_regression, adapter.metrics_for(fixture))
