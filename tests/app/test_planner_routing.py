"""Tests for the planner runtime model-routing policy.

The policy maps planner turns into a discrete model effort class
(``fast`` / ``standard`` / ``deep``) so traveler-facing interactions
stay responsive while planning-heavy turns receive deeper synthesis.
These tests cover the policy in isolation (pure inputs, deterministic
outputs); the route-level integration with the fallback runtime and
fake planner model is covered in ``test_planner_routes.py``.
"""

from __future__ import annotations

import pytest

from trip_planner.app.services.planner_routing import (
    EFFORT_DEEP,
    EFFORT_FAST,
    EFFORT_STANDARD,
    TASK_CLARIFYING_QUESTION,
    TASK_FINAL_SUMMARY,
    TASK_FIRST_TURN_TRIAGE,
    TASK_FOCUS_SWITCH,
    TASK_MAJOR_REVISION,
    TASK_NOTE_CAPTURE,
    TASK_PLANNING_SYNTHESIS,
    TASK_POLICY_PREPARATION,
    TASK_QUICK_ACKNOWLEDGEMENT,
    TASK_RESEARCH_TOOL_PASS,
    TASK_ROUTE_COMPARISON,
    apply_planning_mode,
    base_effort_for,
    classify_task_class,
    route_planner_turn,
)

# --- Fast-path task classification ---------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        "thanks",
        "Thanks!",
        "ok",
        "Okay",
        "got it",
        "sounds good",
        "perfect",
    ],
)
def test_quick_acknowledgement_messages_classify_as_fast(message: str) -> None:
    decision = route_planner_turn(
        message=message,
        base_task_class=TASK_FIRST_TURN_TRIAGE,
        planning_mode="collaborative",
        provider_state="model",
        fallback_reason=None,
    )
    assert decision.task_class == TASK_QUICK_ACKNOWLEDGEMENT
    assert decision.effort_class == EFFORT_FAST
    assert decision.base_effort_class == EFFORT_FAST


@pytest.mark.parametrize(
    "message",
    [
        "Remember this for later: passport renewal is due in March",
        "save this note about the hotel",
        "note this address for the hotel",
        "remind me to book the train",
        "jot that down for the documents notebook",
    ],
)
def test_note_capture_messages_classify_as_fast(message: str) -> None:
    decision = route_planner_turn(
        message=message,
        base_task_class=TASK_FIRST_TURN_TRIAGE,
        planning_mode="collaborative",
        provider_state="model",
        fallback_reason=None,
    )
    assert decision.task_class == TASK_NOTE_CAPTURE
    assert decision.effort_class == EFFORT_FAST


@pytest.mark.parametrize(
    ("message", "expected_focus_present"),
    [
        ("Working on route now", True),
        ("Let's switch to lodging", True),
        ("Focusing on policy this turn", True),
        ("Switch to budget", True),
        ("moving on to activities", True),
    ],
)
def test_focus_switch_messages_classify_as_fast(message: str, expected_focus_present: bool) -> None:
    decision = route_planner_turn(
        message=message,
        base_task_class=TASK_FIRST_TURN_TRIAGE,
        planning_mode="collaborative",
        provider_state="model",
        fallback_reason=None,
    )
    assert decision.task_class == TASK_FOCUS_SWITCH
    assert decision.effort_class == EFFORT_FAST
    assert expected_focus_present


# --- Deep-path task classification ---------------------------------------


@pytest.mark.parametrize(
    ("message", "expected_task"),
    [
        ("Time for the final summary of the trip", TASK_FINAL_SUMMARY),
        ("Let's wrap this up before approval", TASK_FINAL_SUMMARY),
        ("I want to start over with a different plan", TASK_MAJOR_REVISION),
        ("Major revision needed for the itinerary", TASK_MAJOR_REVISION),
        ("Prepare the policy submission for my manager", TASK_POLICY_PREPARATION),
        ("Begin business approval packet prep", TASK_POLICY_PREPARATION),
        ("Look up direct flights from JFK to LIS", TASK_RESEARCH_TOOL_PASS),
        ("Search for boutique hotels near the conference venue", TASK_RESEARCH_TOOL_PASS),
    ],
)
def test_deep_task_classification(message: str, expected_task: str) -> None:
    decision = route_planner_turn(
        message=message,
        base_task_class=TASK_FIRST_TURN_TRIAGE,
        planning_mode="collaborative",
        provider_state="model",
        fallback_reason=None,
    )
    assert decision.task_class == expected_task
    assert decision.effort_class == EFFORT_DEEP
    assert decision.base_effort_class == EFFORT_DEEP


def test_explicit_deep_request_upgrades_triage_to_synthesis() -> None:
    decision = route_planner_turn(
        message="Please think this through carefully before answering",
        base_task_class=TASK_FIRST_TURN_TRIAGE,
        planning_mode="collaborative",
        provider_state="model",
        fallback_reason=None,
    )
    assert decision.task_class == TASK_PLANNING_SYNTHESIS
    assert decision.effort_class == EFFORT_DEEP


def test_route_comparison_base_class_passes_through_to_deep() -> None:
    decision = route_planner_turn(
        message="Looking at the train and flight tradeoffs again",
        base_task_class=TASK_ROUTE_COMPARISON,
        planning_mode="collaborative",
        provider_state="model",
        fallback_reason=None,
    )
    assert decision.task_class == TASK_ROUTE_COMPARISON
    assert decision.effort_class == EFFORT_DEEP


# --- Planning-mode bias --------------------------------------------------


def test_delegated_mode_bumps_standard_to_deep() -> None:
    decision = route_planner_turn(
        message="Help me plan a long weekend",
        base_task_class=TASK_FIRST_TURN_TRIAGE,
        planning_mode="delegated",
        provider_state="model",
        fallback_reason=None,
    )
    assert decision.base_effort_class == EFFORT_STANDARD
    assert decision.effort_class == EFFORT_DEEP
    assert "delegated" in decision.reasoning


def test_collaborative_mode_keeps_standard_standard() -> None:
    decision = route_planner_turn(
        message="Help me plan a long weekend",
        base_task_class=TASK_FIRST_TURN_TRIAGE,
        planning_mode="collaborative",
        provider_state="model",
        fallback_reason=None,
    )
    assert decision.effort_class == EFFORT_STANDARD
    assert "collaborative" in decision.reasoning


def test_in_trip_mode_biases_to_fast_on_standard_band() -> None:
    decision = route_planner_turn(
        message="Help me plan a long weekend",
        base_task_class=TASK_FIRST_TURN_TRIAGE,
        planning_mode="in-trip",
        provider_state="model",
        fallback_reason=None,
    )
    assert decision.effort_class == EFFORT_FAST
    assert "in_trip" in decision.reasoning


def test_planning_mode_does_not_override_explicit_deep_task() -> None:
    decision = route_planner_turn(
        message="Compare options for the family route",
        base_task_class=TASK_ROUTE_COMPARISON,
        planning_mode="in-trip",
        provider_state="model",
        fallback_reason=None,
    )
    # in-trip prefers fast, but explicit deep task wins.
    assert decision.effort_class == EFFORT_DEEP
    assert "route_comparison_pins_deep" in decision.reasoning


def test_planning_mode_does_not_override_explicit_fast_task() -> None:
    decision = route_planner_turn(
        message="thanks",
        base_task_class=TASK_FIRST_TURN_TRIAGE,
        planning_mode="delegated",
        provider_state="model",
        fallback_reason=None,
    )
    # delegated would otherwise bump standard→deep; quick ack stays fast.
    assert decision.effort_class == EFFORT_FAST
    assert "quick_acknowledgement_pins_fast" in decision.reasoning


# --- Fallback-state preservation -----------------------------------------


def test_fallback_reason_recorded_separately_from_effort() -> None:
    decision = route_planner_turn(
        message="Compare the train and the flight",
        base_task_class=TASK_ROUTE_COMPARISON,
        planning_mode="delegated",
        provider_state="fallback",
        fallback_reason="planner_model_not_configured",
    )
    assert decision.effort_class == EFFORT_DEEP
    assert decision.provider_state == "fallback"
    assert decision.fallback_reason == "planner_model_not_configured"


def test_payload_round_trips_all_diagnostic_fields() -> None:
    decision = route_planner_turn(
        message="thanks",
        base_task_class=TASK_FIRST_TURN_TRIAGE,
        planning_mode="collaborative",
        provider_state="model",
        fallback_reason=None,
    )
    payload = decision.to_payload()
    assert payload["task_class"] == TASK_QUICK_ACKNOWLEDGEMENT
    assert payload["effort_class"] == EFFORT_FAST
    assert payload["base_effort_class"] == EFFORT_FAST
    assert payload["selected_planning_mode"] == "collaborative"
    assert payload["provider_state"] == "model"
    assert payload["fallback_reason"] is None
    assert payload["reasoning"]


# --- Helpers can be used independently -----------------------------------


def test_classify_task_class_preserves_base_when_no_marker_matches() -> None:
    assert (
        classify_task_class("we have June dates", base_task_class=TASK_FIRST_TURN_TRIAGE)
        == TASK_FIRST_TURN_TRIAGE
    )


def test_clarifying_question_marker_only_demotes_lower_priority_classes() -> None:
    assert (
        classify_task_class("Could you clarify?", base_task_class=TASK_FIRST_TURN_TRIAGE)
        == TASK_CLARIFYING_QUESTION
    )
    # Should not demote a planning_synthesis base.
    assert (
        classify_task_class("Could you clarify?", base_task_class=TASK_PLANNING_SYNTHESIS)
        == TASK_PLANNING_SYNTHESIS
    )


def test_base_effort_for_returns_standard_for_unknown_task_class() -> None:
    assert base_effort_for("not-a-real-task-class") == EFFORT_STANDARD


def test_apply_planning_mode_default_when_mode_is_none() -> None:
    effort, reason = apply_planning_mode(
        EFFORT_STANDARD,
        planning_mode=None,
        task_class=TASK_FIRST_TURN_TRIAGE,
    )
    assert effort == EFFORT_STANDARD
    assert reason == "default_standard"
