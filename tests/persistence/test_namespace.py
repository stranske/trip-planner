from trip_planner.persistence import (
    PERSISTENCE_BOUNDED_CONTEXTS,
    PERSISTENCE_CHILD_ISSUES,
)


def test_persistence_namespace_exposes_expected_bounded_contexts() -> None:
    assert PERSISTENCE_BOUNDED_CONTEXTS == (
        "profiles",
        "trips",
        "scenarios",
        "budgets",
        "sessions",
    )


def test_persistence_namespace_maps_child_issues_by_context() -> None:
    assert PERSISTENCE_CHILD_ISSUES == {
        "profiles": 538,
        "trips": 539,
        "scenarios": 540,
        "budgets": 541,
        "sessions": 542,
    }
