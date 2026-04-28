"""Failing acceptance tests for planner-turn execution and adjacent runtime contracts.

This module is the first wedge under stranske/trip-planner#956. Each test names the
design contract (epic doc / parent issue) it protects and is expected to fail until
the corresponding implementation lands. None of these tests pass by asserting only
on fixture or placeholder output.

The wider issue calls for failing acceptance tests across four areas — planner turn
execution, map target behavior, TPP approval flow, and preference-resolution
behavior. Preference resolution already has sustained coverage in
``tests/preferences/``, so this initial wedge focuses on the three currently
under-covered areas, with one focused failing test per design contract:

- docs/runtime-planning-services-epic.md (epic #677, children #690-#693)
- docs/live-tpp-execution-reoptimization-epic.md (live TPP flow)
- docs/maps-timeline-comparison-epic.md (epic #679, child #699)

Tests run through the standard ``pytest`` invocation (e.g. ``pytest -q
tests/planner/test_planner_turn_acceptance.py``) and produce deterministic failures
naming the missing capability when the contract is absent. Once the underlying
contract lands, the tests pass without modification; if a contract is intentionally
deferred, mark the corresponding test with ``pytest.mark.xfail(reason=..., strict=False)``
and link the implementation issue.
"""

from __future__ import annotations

import importlib
import inspect

import pytest


@pytest.mark.xfail(
    strict=False,
    reason=(
        "Runtime-planning-services-epic #677 (children #690-#693) outputs are "
        "not yet wired through the planner-turn → workspace path. Expected to "
        "pass once the contract is implemented; tracked under the parent epic."
    ),
)
def test_planner_turn_surfaces_runtime_planning_services_outputs() -> None:
    """Runtime-planning-services-epic #677 (children #690-#693) acceptance contract.

    The epic commits to exposing four runtime-planning-service outputs through the
    planner-turn → workspace path:

    - inventory bundle assembly (#690)
    - feasibility and move-cost evaluation (#691)
    - ranking and scenario generation (#692)
    - route search and scenario comparison (#693)

    The workspace payload returned by ``get_workspace_payload`` is the canonical
    consumer surface for those services. This test fails when one or more of the
    four outputs are not yet wired into that payload, naming the missing capability
    so the next implementation lane can pick it up directly.
    """
    from trip_planner.app.services.workspace import get_workspace_payload

    src = inspect.getsource(get_workspace_payload)
    required_outputs = (
        "inventory_bundle",
        "feasibility",
        "ranking",
        "route_comparison",
    )
    missing = [name for name in required_outputs if name not in src]

    assert not missing, (
        "Planner turn → workspace contract is missing runtime-planning-services "
        f"outputs: {missing}. Required by docs/runtime-planning-services-epic.md "
        "(#677, child issues #690-#693). Implement the workspace payload section "
        "for each missing capability so a planner turn surfaces it to the consumer."
    )


@pytest.mark.xfail(
    strict=False,
    reason=(
        "Live TPP approval-flow entry points (request_approval / "
        "poll_approval_status) are not yet wired into "
        "trip_planner.integrations.tpp. Expected to pass once the live TPP "
        "execution/reoptimization epic implements the round-trip."
    ),
)
def test_tpp_approval_flow_round_trip_from_planner_turn() -> None:
    """Live-tpp-execution-reoptimization-epic acceptance contract.

    A planner-turn-driven booking action against the live TPP service must produce
    the documented round-trip:

        permission request → approval evidence → confirmation

    The contract requires explicit functions that initiate the approval, poll for
    its status, and surface the confirmation back through ``trip_planner.integrations.tpp``.
    This test fails when those entry points are absent so the implementer has a
    clear next step.
    """
    # importlib + hasattr keeps mypy/static-analysis happy while still
    # asserting the runtime contract: we expect these symbols to be missing
    # until the live TPP flow is wired through trip-planner.
    tpp_module = importlib.import_module("trip_planner.integrations.tpp")
    missing = [
        name
        for name in ("request_approval", "poll_approval_status")
        if not hasattr(tpp_module, name)
    ]
    if missing:
        pytest.fail(
            "TPP approval-flow contract is not yet wired into "
            f"trip_planner.integrations.tpp: missing entry points {missing}. "
            "Required by docs/live-tpp-execution-reoptimization-epic.md. "
            "Implement ``request_approval`` and ``poll_approval_status`` (or "
            "the equivalent named entry points referenced in the epic) and "
            "route them from a planner-turn tool call so the round-trip "
            "(permission request → approval evidence → confirmation) is "
            "exercisable."
        )


@pytest.mark.xfail(
    strict=False,
    reason=(
        "Maps-timeline-comparison-epic #679 (child #699) typed route-context "
        "contract is not yet exported from trip_planner.contracts. Expected "
        "to pass once the route-context map surface lands."
    ),
)
def test_map_target_uses_typed_route_context_contract() -> None:
    """Maps-timeline-comparison-epic #679 (child #699) acceptance contract.

    The shared design rule for epic #679 keeps ``trip_planner/app/`` and the
    existing typed frontend data-loading contracts as the canonical source for
    trip, route, and scenario data; child issue #699 adds a route-context map
    surface that consumes those typed contracts rather than inventing parallel
    browser-only models.

    The contract requires a route-context export from ``trip_planner.contracts``
    that the map target can consume directly. This test fails when no such export
    exists, so the map surface either has not landed or is silently using ad-hoc
    shapes.
    """
    from trip_planner import contracts

    candidate_exports = ("RouteContext", "MapRouteContext", "MapTargetRouteContext")
    available = dir(contracts)
    found = [name for name in candidate_exports if name in available]

    assert found, (
        "Map target route-context contract is missing from "
        "``trip_planner.contracts``. Expected at least one of "
        f"{list(candidate_exports)} to be exported. Required by "
        "docs/maps-timeline-comparison-epic.md (#679, child #699). Add the typed "
        "route/option contract surface in ``trip_planner.contracts`` so the "
        "frontend map can stop using parallel browser-only models."
    )
