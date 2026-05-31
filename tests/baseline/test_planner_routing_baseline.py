"""Baseline scenarios for planner routing (``route_planner_turn``).

Issue #1268 acceptance criteria require at least one planner-routing baseline
scenario with directional and/or invariant checks. ``route_planner_turn`` is a
deterministic pure function over the message text and planning mode (no DB,
network, or LLM), so its task-class -> effort-class routing is a stable baseline
surface.

The routing decision lives in a small discrete space (three effort classes),
so it is expressed as cross-scenario *orderings* and structural *invariants*
using the shared ``baseline_kit`` primitives rather than frozen golden scalars.
"""

from __future__ import annotations

import pytest
from baseline_kit import InvariantResult, assert_invariants, evaluate_direction

from trip_planner.app.services.planner_routing import (
    EFFORT_CLASSES,
    EFFORT_DEEP,
    EFFORT_FAST,
    TASK_CLASSES,
    TASK_FIRST_TURN_TRIAGE,
    route_planner_turn,
)

# Effort classes form an ordinal scale: fast < standard < deep.
_EFFORT_RANK = {cls: rank for rank, cls in enumerate(("fast", "standard", "deep"))}


def _route(
    message: str, *, mode: str = "collaborative", base: str = TASK_FIRST_TURN_TRIAGE
):
    return route_planner_turn(
        message=message,
        base_task_class=base,
        planning_mode=mode,
        provider_state="model",
        fallback_reason=None,
    )


# Each message deterministically lands on a single task class (verified against
# ``classify_task_class`` lexical markers).
_SCENARIOS: dict[str, str] = {
    "quick_ack": "thanks",
    "note_capture": "remember this: passport renewal is due in March",
    "focus_switch": "let's switch to lodging",
    "final_summary": "let's wrap the trip up",
    "major_revision": "let's start over",
    "policy_prep": "prepare the policy packet",
    "research_pass": "research flights for the route",
    # deep-request marker on a first-turn-triage base -> planning_synthesis
    "planning_synthesis": "let's think this through carefully",
    "clarifying": "could you clarify what you mean",
}

# Directional orderings on effort rank (planning mode held at collaborative).
# A planning/synthesis/summary turn must receive at least as much effort as a
# quick acknowledgement / note / focus-switch turn.
_ORDERINGS = [
    ("final_summary_deeper_than_ack", "final_summary", "quick_ack", "greater_than"),
    ("research_deeper_than_note", "research_pass", "note_capture", "greater_than"),
    (
        "major_revision_deeper_than_clarify",
        "major_revision",
        "clarifying",
        "greater_than",
    ),
    (
        "synthesis_deeper_than_focus_switch",
        "planning_synthesis",
        "focus_switch",
        "greater_than",
    ),
]


@pytest.mark.parametrize("scen", _ORDERINGS, ids=[s[0] for s in _ORDERINGS])
def test_routing_effort_orderings(scen):
    name, left_key, right_key, direction = scen
    left = _EFFORT_RANK[_route(_SCENARIOS[left_key]).effort_class]
    right = _EFFORT_RANK[_route(_SCENARIOS[right_key]).effort_class]
    assert evaluate_direction(direction, left, right), (
        f"{name}: rank({left_key})={left} !{direction} rank({right_key})={right}"
    )


def test_planning_mode_biases_standard_band_only():
    # A clarifying question carries a base ``standard`` effort. Delegated mode
    # lifts the standard band to deep (autonomous synthesis); in-trip mode drops
    # it to fast (quick response). The two must straddle the standard baseline.
    delegated = _EFFORT_RANK[
        _route(_SCENARIOS["clarifying"], mode="delegated").effort_class
    ]
    in_trip = _EFFORT_RANK[
        _route(_SCENARIOS["clarifying"], mode="in-trip").effort_class
    ]
    assert evaluate_direction("greater_than", delegated, in_trip), (
        f"delegated rank={delegated} should exceed in-trip rank={in_trip}"
    )


def test_routing_invariants():
    results: list[InvariantResult] = []
    for key, msg in _SCENARIOS.items():
        d = _route(msg)
        results.append(
            InvariantResult(
                f"{key}_task_class_known",
                d.task_class in TASK_CLASSES,
                detail=d.task_class,
            )
        )
        results.append(
            InvariantResult(
                f"{key}_effort_class_known",
                d.effort_class in EFFORT_CLASSES,
                detail=d.effort_class,
            )
        )
        results.append(
            InvariantResult(
                f"{key}_base_effort_known",
                d.base_effort_class in EFFORT_CLASSES,
                detail=d.base_effort_class,
            )
        )
        # Planning mode never downgrades an explicit deep task nor upgrades an
        # explicit fast task; only the standard band is adjusted.
        if d.base_effort_class == EFFORT_DEEP:
            results.append(
                InvariantResult(
                    f"{key}_deep_preserved",
                    d.effort_class == EFFORT_DEEP,
                    detail=d.effort_class,
                )
            )
        if d.base_effort_class == EFFORT_FAST:
            results.append(
                InvariantResult(
                    f"{key}_fast_preserved",
                    d.effort_class == EFFORT_FAST,
                    detail=d.effort_class,
                )
            )
        # Routing is deterministic: re-running the same turn yields the same payload.
        again = _route(msg)
        results.append(
            InvariantResult(
                f"{key}_deterministic",
                again.to_payload() == d.to_payload(),
                detail="non-deterministic routing decision",
            )
        )
    assert_invariants(results, context="planner_routing_baseline")
