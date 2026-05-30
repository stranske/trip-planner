"""Tier 1 directional checks: cross-option orderings (cheaper, fewer transfers...)."""

from __future__ import annotations

import pytest
from baseline_kit import evaluate_direction, load_catalog

from . import adapter
from .conftest import CATALOG_PATH

_ORDERINGS = load_catalog(CATALOG_PATH)["orderings"]


@pytest.mark.parametrize("scen", _ORDERINGS, ids=[s["id"] for s in _ORDERINGS])
def test_ordering(scen, record_property):
    metric = scen["metric"]
    left = adapter.metrics_for(scen["left"])[metric]
    right = adapter.metrics_for(scen["right"])[metric]
    holds = evaluate_direction(scen["direction"], left, right)
    msg = f"{scen['id']}: {metric} left={left:.4g} {scen['direction']} right={right:.4g} -> {holds}"
    record_property("ordering", msg)
    if scen.get("enforce"):
        assert holds, "Economically wrong ordering -- " + msg
    elif not holds:
        pytest.skip("[report-only] " + msg)
