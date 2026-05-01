"""Failing acceptance tests for planner-turn execution and adjacent runtime contracts.

This module is the first wedge under stranske/trip-planner#956. Each test names the
design contract (epic doc / parent issue) it protects and is expected to fail until
the corresponding implementation lands. None of these tests pass by asserting only
on fixture or placeholder output.

The wider issue calls for failing acceptance tests across four areas — planner turn
execution, map target behavior, TPP approval flow, and preference-resolution
behavior. Preference resolution already has sustained coverage in
``tests/preferences/``. Of the three remaining wedges, the live-TPP and
route-context surfaces have since shipped under different names; their original
xfail tests have been removed and recorded in ``tests/planner/MIGRATIONS.md``.
The runtime-planning-services wedge below is now narrowed to the two outputs
that are still genuinely deferred and is marked ``strict=True`` so that
surfacing them in ``get_workspace_payload`` flips the test to XPASS and forces
the implementer to convert the xfail into a real assertion.

Tests run through the standard ``pytest`` invocation (e.g. ``pytest -q
tests/planner/test_planner_turn_acceptance.py``). Once the underlying contract
lands, the surviving xfail will pass and CI will fail with XPASS, prompting the
implementer to remove the xfail marker and tighten the assertion. New
acceptance-style xfails added in ``tests/planner/``, ``tests/contracts/``, or
``tests/integrations/`` must be ``strict=True`` (or carry an
``# xfail-exempt: <reason>`` marker on the decorator line); this is enforced
by ``scripts/check_xfail_strictness.py``.
"""

from __future__ import annotations

import inspect

import pytest


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Runtime-planning-services-epic #677: ``get_workspace_payload`` "
        "surfaces inventory bundles and feasibility, but the ranking output "
        "(#692) is currently produced inside ``_build_planner_panel_state`` "
        "rather than as a top-level workspace key, and the route-search / "
        "scenario-comparison output (#693) is exposed as "
        "``runtime_scenario_comparison`` instead of the documented "
        "``route_comparison`` shape. Expected to pass once both are surfaced "
        "directly in the workspace payload under the documented names."
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

    The 2026-04-30 audit (issue #1046) confirmed that #690 (surfaced as
    ``inventory_summary``, with the assembled bundles nested inside) and #691
    (surfaced as ``feasibility_summary``) are now top-level keys of the dict
    returned by ``get_workspace_payload``. The two children that remain
    deferred — #692 (``ranking``) and #693 (``route_comparison``) — are still
    only reachable indirectly: ranking is computed inside
    ``_build_planner_panel_state`` rather than surfaced as a top-level
    workspace key, and the route/scenario comparison is currently named
    ``runtime_scenario_comparison`` rather than the documented
    ``route_comparison`` shape. This test therefore asserts only on the two
    still-missing names. With ``strict=True`` it converts to XPASS and fails
    CI the moment both surface as substrings of ``get_workspace_payload``,
    forcing whoever lands the implementation to delete the xfail and assert
    on the payload directly.
    """
    from trip_planner.app.services.workspace import get_workspace_payload

    src = inspect.getsource(get_workspace_payload)
    required_outputs = ("ranking", "route_comparison")
    missing = [name for name in required_outputs if name not in src]

    assert not missing, (
        "Planner turn → workspace contract is missing runtime-planning-services "
        f"outputs: {missing}. Required by docs/runtime-planning-services-epic.md "
        "(#677, child issues #692 (ranking) and #693 (route comparison)). Surface "
        "each missing capability as a top-level key of the dict returned by "
        "``get_workspace_payload`` under the documented names so the planner "
        "turn → workspace consumer can read it without descending into helper "
        "builders."
    )
