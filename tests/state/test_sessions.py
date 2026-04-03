import json
from pathlib import Path

import pytest

from trip_planner.state import (
    ActivityLogEvent,
    PendingDecision,
    PlanningInteractionState,
    PlanningSessionState,
)
from trip_planner.state.repositories import (
    ActivityLogRepository,
    PlanningSessionRepository,
    SessionStateVersion,
)
from trip_planner.state.sessions import OptionPresentationRecord


def _fixture_path(name: str) -> Path:
    fixtures_dir = Path(__file__).resolve().parents[1] / "fixtures" / "state" / "sessions"
    return fixtures_dir / name


def _load_payload(name: str) -> dict:
    return json.loads(_fixture_path(name).read_text(encoding="utf-8"))


def _load_session(name: str) -> PlanningSessionState:
    return PlanningSessionState.from_dict(_load_payload(name)["session"])


def _load_events(name: str) -> list[ActivityLogEvent]:
    return [ActivityLogEvent.from_dict(item) for item in _load_payload(name).get("events", [])]


def test_planning_session_loads_active_leisure_fixture() -> None:
    session = _load_session("active_leisure_session.json")

    assert session.mode == "leisure"
    assert session.interaction_state.initiative_level == "balanced"
    assert session.recent_option_presentations[0].option_set_id == "option-set:kyoto-v3"
    assert session.pending_decisions[0].related_saved_scenario_id == (
        "saved-scenario:kyoto-baseline"
    )


def test_planning_session_loads_business_fixture_with_policy_review_state() -> None:
    session = _load_session("business_review_session.json")

    assert session.mode == "business"
    assert session.status == "paused"
    assert session.current_checkpoint_id == "checkpoint:client-summit-policy-review"
    assert session.pending_decisions[0].title == "Choose policy path"


def test_planning_session_loads_in_trip_revision_fixture_and_events() -> None:
    session = _load_session("in_trip_revision_session.json")
    events = _load_events("in_trip_revision_session.json")

    assert session.status == "active"
    assert session.current_saved_scenario_id == "saved-scenario:kyoto-rainy-day"
    assert session.recent_option_presentations[0].surface_kind == "in_trip_update"
    assert [event.event_kind for event in events] == [
        "scenario_saved",
        "budget_updated",
        "in_trip_change_requested",
    ]


def test_pending_decision_rejects_selected_choice_outside_choices() -> None:
    with pytest.raises(ValueError, match="selected_choice must be one of choices"):
        PendingDecision(
            decision_id="decision:test",
            prompt="Choose a route.",
            created_at="2026-04-02T12:00:00Z",
            choices=["A", "B"],
            selected_choice="C",
        )


def test_option_presentation_rejects_rejected_option_outside_surface() -> None:
    with pytest.raises(
        ValueError,
        match="rejected_option_ids must be drawn from surfaced options",
    ):
        OptionPresentationRecord(
            presentation_id="presentation:test",
            option_set_id="option-set:test",
            shown_at="2026-04-02T12:00:00Z",
            surfaced_option_ids=["option:1", "option:2"],
            rejected_option_ids=["option:3"],
        )


def test_activity_log_event_rejects_empty_metadata_value() -> None:
    with pytest.raises(ValueError, match="metadata must contain non-empty string values"):
        ActivityLogEvent(
            activity_event_id="activity:test",
            trip_id="trip-1",
            session_state_id="session-1",
            occurred_at="2026-04-02T12:00:00Z",
            event_kind="scenario_saved",
            summary="Saved scenario.",
            metadata={"reason": ""},
        )


def test_activity_log_event_rejects_non_dict_metadata() -> None:
    with pytest.raises(
        ValueError,
        match="metadata must be a dict of string keys to string values",
    ):
        ActivityLogEvent(
            activity_event_id="activity:test",
            trip_id="trip-1",
            session_state_id="session-1",
            occurred_at="2026-04-02T12:00:00Z",
            event_kind="scenario_saved",
            summary="Saved scenario.",
            metadata=["reason"],  # type: ignore[arg-type]
        )


def test_planning_session_rejects_duplicate_pending_decisions() -> None:
    payload = _load_payload("active_leisure_session.json")["session"]
    payload["pending_decisions"].append(payload["pending_decisions"][0])

    with pytest.raises(
        ValueError,
        match="pending_decisions cannot repeat decision_id values",
    ):
        PlanningSessionState.from_dict(payload)


def test_planning_session_repository_protocol_can_store_session_state_and_logs() -> None:
    class InMemoryPlanningSessionRepository(PlanningSessionRepository):
        def __init__(self) -> None:
            self._sessions: dict[str, PlanningSessionState] = {}
            self._versions: dict[str, list[SessionStateVersion]] = {}

        def get_session(self, session_state_id: str) -> PlanningSessionState | None:
            return self._sessions.get(session_state_id)

        def save_session(
            self,
            session_state: PlanningSessionState,
            *,
            summary: str = "",
        ) -> SessionStateVersion:
            self._sessions[session_state.session_state_id] = session_state
            version = SessionStateVersion(
                version_id=(
                    f"{session_state.session_state_id}-v"
                    f"{len(self._versions.get(session_state.session_state_id, [])) + 1}"
                ),
                session_state_id=session_state.session_state_id,
                recorded_at=session_state.updated_at,
                summary=summary,
            )
            self._versions.setdefault(session_state.session_state_id, []).append(version)
            return version

        def update_interaction_state(
            self,
            session_state_id: str,
            interaction_state: PlanningInteractionState,
            *,
            updated_at: str,
            summary: str = "",
        ) -> SessionStateVersion:
            session = self._sessions[session_state_id]
            session.interaction_state = interaction_state
            session.updated_at = updated_at
            return self.save_session(session, summary=summary or "interaction update")

        def replace_pending_decisions(
            self,
            session_state_id: str,
            pending_decisions: list[PendingDecision],
            *,
            updated_at: str,
            summary: str = "",
        ) -> SessionStateVersion:
            session = self._sessions[session_state_id]
            session.pending_decisions = pending_decisions
            session.updated_at = updated_at
            return self.save_session(session, summary=summary or "decision update")

        def record_option_presentation(
            self,
            session_state_id: str,
            presentation: OptionPresentationRecord,
            *,
            updated_at: str,
            summary: str = "",
        ) -> SessionStateVersion:
            session = self._sessions[session_state_id]
            session.recent_option_presentations.append(presentation)
            session.updated_at = updated_at
            return self.save_session(
                session,
                summary=summary or "option presentation recorded",
            )

        def list_sessions(
            self,
            *,
            trip_id: str | None = None,
            user_id: str | None = None,
            owner_profile_id: str | None = None,
            mode: str | None = None,
            status: str | None = None,
        ) -> list[PlanningSessionState]:
            sessions = list(self._sessions.values())
            if trip_id is not None:
                sessions = [session for session in sessions if session.trip_id == trip_id]
            if user_id is not None:
                sessions = [session for session in sessions if session.user_id == user_id]
            if owner_profile_id is not None:
                sessions = [
                    session for session in sessions if session.owner_profile_id == owner_profile_id
                ]
            if mode is not None:
                sessions = [session for session in sessions if session.mode == mode]
            if status is not None:
                sessions = [session for session in sessions if session.status == status]
            return sessions

        def list_versions(self, session_state_id: str) -> list[SessionStateVersion]:
            return list(self._versions.get(session_state_id, []))

    class InMemoryActivityLogRepository(ActivityLogRepository):
        def __init__(self) -> None:
            self._events: dict[str, ActivityLogEvent] = {}

        def get_event(self, activity_event_id: str) -> ActivityLogEvent | None:
            return self._events.get(activity_event_id)

        def append_event(self, event: ActivityLogEvent) -> ActivityLogEvent:
            self._events[event.activity_event_id] = event
            return event

        def list_events(
            self,
            *,
            trip_id: str | None = None,
            session_state_id: str | None = None,
            event_kind: str | None = None,
            related_decision_id: str | None = None,
            related_option_set_id: str | None = None,
        ) -> list[ActivityLogEvent]:
            events = list(self._events.values())
            if trip_id is not None:
                events = [event for event in events if event.trip_id == trip_id]
            if session_state_id is not None:
                events = [event for event in events if event.session_state_id == session_state_id]
            if event_kind is not None:
                events = [event for event in events if event.event_kind == event_kind]
            if related_decision_id is not None:
                events = [
                    event for event in events if event.related_decision_id == related_decision_id
                ]
            if related_option_set_id is not None:
                events = [
                    event
                    for event in events
                    if event.related_option_set_id == related_option_set_id
                ]
            return events

    session_repo = InMemoryPlanningSessionRepository()
    log_repo = InMemoryActivityLogRepository()
    session = _load_session("active_leisure_session.json")
    event = _load_events("in_trip_revision_session.json")[0]

    first = session_repo.save_session(session, summary="initial session import")
    second = session_repo.update_interaction_state(
        session.session_state_id,
        PlanningInteractionState(
            interaction_style="collaborative",
            initiative_level="planner_led",
            checkpoint_frequency="phase",
            option_preview_timing="early",
            summary_granularity="balanced",
            auto_advance_research_passes=2,
            ask_before_major_change=False,
        ),
        updated_at="2026-04-02T09:20:00Z",
        summary="increase planner initiative",
    )
    third = session_repo.record_option_presentation(
        session.session_state_id,
        OptionPresentationRecord(
            presentation_id="presentation:extra",
            option_set_id="option-set:kyoto-v4",
            shown_at="2026-04-02T09:22:00Z",
            surfaced_option_ids=["option:3", "option:4"],
            highlighted_option_id="option:3",
            selected_option_id="option:3",
            summary="Presented a narrowed fallback pair.",
        ),
        updated_at="2026-04-02T09:22:00Z",
        summary="recorded narrowed fallback pair",
    )
    stored_event = log_repo.append_event(event)

    stored = session_repo.get_session(session.session_state_id)

    assert stored is not None
    assert stored.interaction_state.initiative_level == "planner_led"
    assert stored.recent_option_presentations[-1].option_set_id == "option-set:kyoto-v4"
    assert [
        version.version_id for version in session_repo.list_versions(session.session_state_id)
    ] == [first.version_id, second.version_id, third.version_id]
    assert stored_event.event_kind == "scenario_saved"
    assert log_repo.list_events(event_kind="scenario_saved")[0].activity_event_id == (
        stored_event.activity_event_id
    )
