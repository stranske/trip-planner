"""Reject silent test removal during unrestricted collection checks."""

from collections.abc import Iterator

import pytest


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> Iterator[None]:
    """Compare nodes around pytest's collection-modification hooks."""
    collected = {item.nodeid for item in items}
    yield
    missing = collected - {item.nodeid for item in items}
    if missing:
        raise pytest.UsageError(f"Collection hooks removed regressions: {sorted(missing)}")
