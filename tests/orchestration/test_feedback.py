import json
from pathlib import Path

import pytest

from tests.preferences.fixture_corpus import load_fixture_map
from trip_planner.orchestration import (
    FeedbackLoopContext,
    OptionFeedbackEvent,
    build_feedback_loop_result,
)
from trip_planner.preferences import PlanningAutonomyProfile
from trip_planner.state import PlanningSessionState


def _fixture_path(name: str) -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "orchestration"
        / "feedback"
        / name
    )


def _load_event(name: str) -> OptionFeedbackEvent:
    payload = json.loads(_fixture_path(name).read_text(encoding="utf-8"))
    return OptionFeedbackEvent(**payload["event"])


def _load_session() -> PlanningSessionState:
    payload = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "state"
            / "sessions"
            / "active_leisure_session.json"
        ).read_text(encoding="utf-8")
    )
    return PlanningSessionState.from_dict(payload["session"])


def _context(
    *,
    generated_at: str = "2026-04-02T15:00:00Z",
    session_state: PlanningSessionState | None = None,
    autonomy_profile: PlanningAutonomyProfile | None = None,
) -> FeedbackLoopContext:
    fixture = load_fixture_map()["discovery-wanderer"]
    return FeedbackLoopContext(
        preference_profile=fixture.profile,
        session_state=session_state or _load_session(),
        autonomy_profile=autonomy_profile or PlanningAutonomyProfile(),
        generated_at=generated_at,
    )


def test_accept_option_routes_feedback_into_checkpoint_state() -> None:
    result = build_feedback_loop_result(_context(), _load_event("accept_option.json"))

    presentation = result.updated_session_state.recent_option_presentations[0]

    assert presentation.selected_option_id == "option:kyoto-central"
    assert result.activity_event.event_kind == "decision_recorded"
    assert result.planner_turn.workflow_state.current_stage == "decision_checkpoint"
    assert result.planner_turn.next_step.recommended_action_id == (
        "action-request-decision"
    )
    assert result.revealed_preference_updates[0].signal.reaction_type == "selected"


def test_reject_and_rerank_clears_checkpoint_and_updates_autonomy() -> None:
    result = build_feedback_loop_result(
        _context(),
        _load_event("reject_and_rerank.json"),
    )

    presentation = result.updated_session_state.recent_option_presentations[0]

    assert "option:osaka-daytrip" in presentation.rejected_option_ids
    assert result.updated_session_state.pending_decisions == []
    assert result.activity_event.event_kind == "rerank_requested"
    assert result.planner_turn.next_step.recommended_action_id == "action-rank-options"
    assert (
        result.updated_session_state.interaction_state.auto_advance_research_passes > 1
    )
    assert result.planner_turn.workflow_state.pending_decisions == []


def test_save_as_fallback_emits_structured_scenario_capture_request() -> None:
    result = build_feedback_loop_result(
        _context(),
        _load_event("save_as_fallback.json"),
    )

    assert result.scenario_capture_request is not None
    assert result.scenario_capture_request.label == "fallback"
    assert result.scenario_capture_request.saved_scenario_id == (
        "saved-scenario:osaka-weather-fallback"
    )
    assert result.activity_event.event_kind == "scenario_saved"
    assert result.activity_event.saved_scenario_id == (
        "saved-scenario:osaka-weather-fallback"
    )
    assert result.planner_turn.next_step.recommended_action_id == (
        "action-persist-fallback"
    )
    presentation = result.updated_session_state.recent_option_presentations[0]
    assert presentation.selected_option_id is None
    assert presentation.rejected_option_ids == ["option:osaka-daytrip"]
    assert result.activity_event.actor == "user"
    assert result.planner_turn.workflow_state.pending_decisions[0].decision_id == (
        "decision:save-baseline"
    )


def test_feedback_context_rejects_invalid_trip_stage() -> None:
    fixture = load_fixture_map()["discovery-wanderer"]
    with pytest.raises(ValueError, match="trip_stage"):
        FeedbackLoopContext(
            preference_profile=fixture.profile,
            session_state=_load_session(),
            autonomy_profile=PlanningAutonomyProfile(),
            generated_at="2026-04-02T15:00:00Z",
            trip_stage="bad-stage",
        )


def test_reject_option_records_option_rejected_activity() -> None:
    event = _load_event("reject_and_rerank.json")
    event.feedback_kind = "reject_option"
    result = build_feedback_loop_result(_context(), event)

    assert result.activity_event.event_kind == "option_rejected"
    assert result.activity_event.actor == "user"


def test_feedback_rejects_unknown_option_id() -> None:
    event = _load_event("accept_option.json")
    event.option_id = "option:missing"

    with pytest.raises(ValueError, match="surfaced_option_ids"):
        build_feedback_loop_result(_context(), event)


def test_feedback_loop_supports_reentry_with_updated_session_state() -> None:
    first = build_feedback_loop_result(_context(), _load_event("accept_option.json"))
    second = build_feedback_loop_result(
        _context(
            generated_at="2026-04-02T15:20:00Z",
            session_state=first.updated_session_state,
            autonomy_profile=first.updated_autonomy_profile,
        ),
        _load_event("reject_and_rerank.json"),
    )

    presentation = second.updated_session_state.recent_option_presentations[0]

    assert presentation.selected_option_id == "option:kyoto-central"
    assert "option:osaka-daytrip" in presentation.rejected_option_ids
    assert second.updated_session_state.notes[-2:] == [
        "feedback-loop:accept_option:quick_preference_check:option:kyoto-central",
        "feedback-loop:request_alternatives:inventory_narrowing:option:osaka-daytrip",
    ]
    assert second.planner_turn.transition.to_stage == "ranking"
