import json
from dataclasses import replace
from pathlib import Path

import pytest

from trip_planner.orchestration import (
    InTripAdjustmentContext,
    InTripRevisionOutput,
    InTripTriggerEvent,
    build_in_trip_adjustment_result,
)
from trip_planner.state import PlanningSessionState


def _fixture_path(name: str) -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "orchestration"
        / "in_trip"
        / name
    )


def _load_event(name: str) -> InTripTriggerEvent:
    payload = json.loads(_fixture_path(name).read_text(encoding="utf-8"))
    return InTripTriggerEvent(**payload["event"])


def _load_session() -> PlanningSessionState:
    payload = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "state"
            / "sessions"
            / "in_trip_revision_session.json"
        ).read_text(encoding="utf-8")
    )
    return PlanningSessionState.from_dict(payload["session"])


def _context(
    *,
    generated_at: str = "2026-04-02T11:30:00Z",
    session_state: PlanningSessionState | None = None,
) -> InTripAdjustmentContext:
    return InTripAdjustmentContext(
        session_state=session_state or _load_session(),
        scenario_search_id="scenario-search:kyoto-live",
        ranked_result_set_id="ranked-result-set:kyoto-live",
        generated_at=generated_at,
    )


def test_closure_event_routes_into_scenario_revision() -> None:
    result = build_in_trip_adjustment_result(
        _context(),
        _load_event("closure_driven_replan.json"),
    )

    assert result.replanning_request.replanning_kind == "scenario_revision"
    assert result.planner_turn.workflow_state.current_stage == "replanning"
    assert result.revision_output.output_kind == "scenario_revision"
    assert result.activity_event.event_kind == "in_trip_change_requested"
    assert result.updated_session_state.pending_decisions[-1].blocking is True
    assert result.replanning_request.based_on_saved_scenario_id == (
        "saved-scenario:kyoto-rainy-day"
    )


def test_budget_drift_event_routes_into_reranking() -> None:
    result = build_in_trip_adjustment_result(
        _context(),
        _load_event("budget_drift_replan.json"),
    )

    assert result.replanning_request.replanning_kind == "rerank"
    assert result.planner_turn.next_step.recommended_action_id == (
        "action-refresh-ranking"
    )
    assert result.revision_output.output_kind == "reranked_options"
    assert result.activity_event.event_kind == "budget_updated"
    assert result.updated_session_state.pending_decisions == _load_session().pending_decisions


def test_rerank_event_does_not_require_confirmation_for_prior_decisions() -> None:
    session = _load_session()
    session.pending_decisions = [*session.pending_decisions]
    session.pending_decisions[0] = replace(
        session.pending_decisions[0],
        blocking=True,
    )

    result = build_in_trip_adjustment_result(
        _context(session_state=session),
        _load_event("budget_drift_replan.json"),
    )

    assert result.replanning_request.replanning_kind == "rerank"
    assert result.replanning_request.requires_user_confirmation is False
    assert result.updated_session_state.pending_decisions == session.pending_decisions


def test_travel_delay_event_routes_into_emergency_fallback() -> None:
    result = build_in_trip_adjustment_result(
        _context(),
        _load_event("travel_delay_emergency.json"),
    )

    assert result.replanning_request.replanning_kind == "emergency_fallback"
    assert result.replanning_request.requires_user_confirmation is True
    assert result.revision_output.output_kind == "emergency_fallback"
    assert result.planner_turn.outputs[0].output_kind == "warning"
    assert result.planner_turn.workflow_state.pending_decisions[-1].decision_id == (
        "trigger:kyoto-travel-delay:decision"
    )


def test_informational_fatigue_event_stays_in_monitoring() -> None:
    event = InTripTriggerEvent(
        trigger_event_id="trigger:fatigue-soft",
        trip_id="trip-leisure-kyoto-live",
        session_state_id="session-state:kyoto-rainy-day",
        trigger_kind="fatigue_shift",
        severity="informational",
        change_scope="local_stop",
        observed_at="2026-04-02T11:35:00Z",
        summary="The traveler wants a slower pace but does not need a route change yet.",
        actor="user",
        source="chat",
        metadata={"option_set_id": "option-set:rainy-day-v1"},
    )

    result = build_in_trip_adjustment_result(_context(), event)

    assert result.replanning_request.replanning_kind == "ignore"
    assert result.planner_turn.workflow_state.current_stage == "monitoring"
    assert result.planner_turn.next_step.recommended_action_id == "action-record-trigger"
    assert result.updated_session_state.pending_decisions == _load_session().pending_decisions


def test_trigger_event_rejects_unknown_severity() -> None:
    with pytest.raises(ValueError, match="severity"):
        InTripTriggerEvent(
            trigger_event_id="trigger:bad",
            trip_id="trip-leisure-kyoto-live",
            session_state_id="session-state:kyoto-rainy-day",
            trigger_kind="closure",
            severity="urgent",
            change_scope="day_segment",
            observed_at="2026-04-02T11:40:00Z",
            summary="Bad severity fixture.",
        )


def test_trigger_event_from_dict_rejects_non_mapping_metadata() -> None:
    payload = {
        "trigger_event_id": "trigger:bad-metadata",
        "trip_id": "trip-leisure-kyoto-live",
        "session_state_id": "session-state:kyoto-rainy-day",
        "trigger_kind": "closure",
        "severity": "advisory",
        "change_scope": "day_segment",
        "observed_at": "2026-04-02T11:40:00Z",
        "summary": "Bad metadata fixture.",
        "metadata": ["option-set:bad"],
    }

    with pytest.raises(ValueError, match="metadata"):
        InTripTriggerEvent.from_dict(payload)


def test_revision_output_from_dict_rejects_non_mapping_payload() -> None:
    payload = {
        "revision_output_id": "revision-output:bad-payload",
        "trip_id": "trip-leisure-kyoto-live",
        "output_kind": "status_note",
        "generated_at": "2026-04-02T11:40:00Z",
        "summary": "Bad revision payload fixture.",
        "recommended_action_id": "action-record-trigger",
        "payload": ["not-a-mapping"],
    }

    with pytest.raises(ValueError, match="payload"):
        InTripRevisionOutput.from_dict(payload)
