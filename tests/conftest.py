import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
root_str = str(ROOT)
if root_str not in sys.path:
    sys.path.insert(0, root_str)


@pytest.fixture(autouse=True)
def isolate_tpp_transport_breakers() -> Iterator[None]:
    from trip_planner.integrations.tpp import client as tpp_client_module

    tpp_client_module.HTTPTPPIntegrationClient._breakers.clear()
    yield
    tpp_client_module.HTTPTPPIntegrationClient._breakers.clear()


@pytest.fixture(autouse=True)
def enable_explicit_tpp_fixture_responses(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Enable serialized TPP fixtures only inside the test process.

    Production routes ignore caller-supplied response envelopes by default.  The
    integration tests deliberately use those envelopes to model the trusted TPP
    boundary, while the security regression explicitly removes this switch to
    exercise the production behavior.
    """
    monkeypatch.setenv("TRIP_PLANNER_ALLOW_FIXTURE_TPP_RESPONSES", "true")
    yield
