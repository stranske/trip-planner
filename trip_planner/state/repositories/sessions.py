"""Backend-neutral repository interfaces for planning-session state."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol

from trip_planner.contracts._validators import require_non_empty
from trip_planner.state.sessions import (
    ActivityLogEvent,
    OptionPresentationRecord,
    PendingDecision,
    PlanningInteractionState,
    PlanningSessionState,
)


@dataclass(slots=True)
class SessionStateVersion:
    version_id: str
    session_state_id: str
    recorded_at: str
    summary: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.version_id, "version_id")
        require_non_empty(self.session_state_id, "session_state_id")
        require_non_empty(self.recorded_at, "recorded_at")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PlanningSessionRepository(Protocol):
    def get_session(self, session_state_id: str) -> PlanningSessionState | None:
        """Load one persisted planning-session state record."""

    def save_session(
        self,
        session_state: PlanningSessionState,
        *,
        summary: str = "",
    ) -> SessionStateVersion:
        """Persist one session-state record and return version metadata."""

    def update_interaction_state(
        self,
        session_state_id: str,
        interaction_state: PlanningInteractionState,
        *,
        updated_at: str,
        summary: str = "",
    ) -> SessionStateVersion:
        """Persist an updated interaction-state view for one session."""

    def replace_pending_decisions(
        self,
        session_state_id: str,
        pending_decisions: list[PendingDecision],
        *,
        updated_at: str,
        summary: str = "",
    ) -> SessionStateVersion:
        """Persist the current mutable pending-decision set for one session."""

    def record_option_presentation(
        self,
        session_state_id: str,
        presentation: OptionPresentationRecord,
        *,
        updated_at: str,
        summary: str = "",
    ) -> SessionStateVersion:
        """Persist the latest option-presentation history for one session."""

    def list_sessions(
        self,
        *,
        trip_id: str | None = None,
        user_id: str | None = None,
        owner_profile_id: str | None = None,
        mode: str | None = None,
        status: str | None = None,
    ) -> list[PlanningSessionState]:
        """List session-state records using backend-neutral filters."""

    def list_versions(self, session_state_id: str) -> list[SessionStateVersion]:
        """List saved versions for one persisted session-state record."""


class ActivityLogRepository(Protocol):
    def get_event(self, activity_event_id: str) -> ActivityLogEvent | None:
        """Load one append-only activity-log event."""

    def append_event(self, event: ActivityLogEvent) -> ActivityLogEvent:
        """Persist one append-only activity-log event."""

    def list_events(
        self,
        *,
        trip_id: str | None = None,
        session_state_id: str | None = None,
        event_kind: str | None = None,
        related_decision_id: str | None = None,
        related_option_set_id: str | None = None,
    ) -> list[ActivityLogEvent]:
        """List append-only activity-log events using backend-neutral filters."""
