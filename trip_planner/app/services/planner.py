"""Trip-scoped planner conversation services."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from trip_planner.app.services.auth import AuthenticatedUser
from trip_planner.app.services.workspace import (
    WORKSPACE_ACTIVITY_LOG_LIMIT,
    _append_activity_event,
    _get_or_create_workspace_session_record,
    _get_owned_trip_record,
    _record_planner_action,
    _serialize_activity_record,
    _serialize_session_record,
    get_workspace_payload,
)
from trip_planner.persistence.models.activity import (
    PersistedActivityLogEvent,
    PersistedPlannerAction,
)
from trip_planner.state.sessions import PlanningSessionState


class WorkspacePlannerTripNotFoundError(ValueError):
    """Raised when the planner conversation targets an unknown trip."""


def _isoformat(timestamp: datetime) -> str:
    return timestamp.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class PlannerConversationRequest:
    trip_id: str
    message: str
    planner_panel_state: dict[str, Any]
    session: PlanningSessionState


@dataclass(frozen=True, slots=True)
class PlannerConversationReply:
    content: str
    refs: list[str]


class PlannerConversationRunnable(Protocol):
    """LangChain-style runnable abstraction for planner conversation turns."""

    def invoke(self, request: PlannerConversationRequest) -> PlannerConversationReply:
        """Return one planner response for the provided turn."""


class DeterministicPlannerConversationRunnable:
    """Small provider-neutral runnable until a real LangChain chat stack is attached."""

    def invoke(self, request: PlannerConversationRequest) -> PlannerConversationReply:
        panel = request.planner_panel_state
        trip = panel["trip"]
        outputs = list(panel.get("outputs") or [])
        decisions = list(panel.get("pending_decisions") or [])
        options = list((panel.get("option_set") or {}).get("options") or [])

        lines = [
            f"{trip['title']} is using a trip-scoped planner session for this request.",
            f"You said: {request.message.strip()}",
        ]
        refs = [request.session.session_state_id]

        if decisions:
            active = decisions[0]
            choice_labels = ", ".join(active.get("choices") or [])
            lines.append(
                f"Current blocking decision: {active['prompt']} Choices: {choice_labels}."
            )
            refs.append(active["decision_id"])
        elif options:
            lead = options[0]
            lines.append(
                f"Current lead option: {lead['label']}. {lead['summary']}"
            )
            if len(options) > 1:
                lines.append(f"Alternative to compare next: {options[1]['label']}.")
            refs.append(lead["option_id"])
        else:
            lines.append(
                "No ranked planner options exist yet, so the session should stay focused on refining trip scope."
            )

        if outputs:
            latest_titles = ", ".join(output["title"] for output in outputs[:2])
            lines.append(f"Latest workspace signals: {latest_titles}.")
            refs.extend(output["output_id"] for output in outputs[:2])

        lines.append(
            "This reply is generated through the planner runnable boundary so a LangChain-backed engine can replace it without changing the route handlers."
        )
        deduped_refs = list(dict.fromkeys(refs))
        return PlannerConversationReply(content=" ".join(lines), refs=deduped_refs)


def _planner_runnable() -> PlannerConversationRunnable:
    return DeterministicPlannerConversationRunnable()


def _conversation_id(trip_id: str) -> str:
    return f"planner-conversation:{trip_id}"


def _message_payload(
    *,
    message_id: str,
    role: str,
    content: str,
    created_at: str,
    refs: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "message_id": message_id,
        "role": role,
        "content": content,
        "created_at": created_at,
        "refs": list(refs or []),
    }


def _conversation_messages(
    db_session: Session,
    *,
    session_state_id: str,
) -> list[dict[str, Any]]:
    records = db_session.scalars(
        select(PersistedPlannerAction)
        .where(PersistedPlannerAction.session_state_id == session_state_id)
        .where(PersistedPlannerAction.action_type.in_(["planner_user_turn", "planner_response"]))
        .order_by(
            PersistedPlannerAction.created_at.asc(),
            PersistedPlannerAction.planner_action_id.asc(),
        )
    ).all()
    messages: list[dict[str, Any]] = []
    for record in records:
        role = record.payload.get("role") or (
            "user" if record.action_type == "planner_user_turn" else "planner"
        )
        raw_refs = record.payload.get("refs", "")
        refs = [item for item in raw_refs.split(",") if item]
        messages.append(
            _message_payload(
                message_id=record.planner_action_id,
                role=role,
                content=record.payload.get("content", ""),
                created_at=record.occurred_at,
                refs=refs,
            )
        )
    return messages


def _activity_log(
    db_session: Session,
    *,
    trip_id: str,
) -> list[dict[str, Any]]:
    records = db_session.scalars(
        select(PersistedActivityLogEvent)
        .where(PersistedActivityLogEvent.trip_id == trip_id)
        .order_by(PersistedActivityLogEvent.occurred_at.desc())
        .limit(WORKSPACE_ACTIVITY_LOG_LIMIT)
    ).all()
    return [_serialize_activity_record(record) for record in records]


def _planner_session_payload(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    resumed_at: str | None = None,
) -> dict[str, Any]:
    workspace_payload = get_workspace_payload(db_session, user=user, trip_id=trip_id)
    if workspace_payload is None:
        raise WorkspacePlannerTripNotFoundError(f"Trip '{trip_id}' was not found.")

    session = workspace_payload["session"]
    session_state_id = session["session_state_id"]
    return {
        "trip_id": trip_id,
        "session_state_id": session_state_id,
        "conversation_id": _conversation_id(trip_id),
        "resumed_at": resumed_at,
        "session": session,
        "planner_panel_state": workspace_payload["planner_panel_state"],
        "activity_log": _activity_log(db_session, trip_id=trip_id),
        "messages": _conversation_messages(db_session, session_state_id=session_state_id),
    }


def get_planner_session_payload(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
) -> dict[str, Any]:
    try:
        record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    except ValueError as error:
        raise WorkspacePlannerTripNotFoundError(str(error)) from error
    _get_or_create_workspace_session_record(db_session, record=record)
    db_session.commit()
    return _planner_session_payload(db_session, user=user, trip_id=trip_id)


def resume_planner_session_payload(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
) -> dict[str, Any]:
    try:
        record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    except ValueError as error:
        raise WorkspacePlannerTripNotFoundError(str(error)) from error
    session_record = _get_or_create_workspace_session_record(db_session, record=record)
    resumed_at = _isoformat(datetime.now(UTC))
    session_record.last_updated_at = resumed_at
    record.updated_at = datetime.now(UTC)
    db_session.commit()
    return _planner_session_payload(
        db_session,
        user=user,
        trip_id=trip_id,
        resumed_at=resumed_at,
    )


def submit_planner_turn(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    message: str,
) -> dict[str, Any]:
    normalized_message = message.strip()
    if not normalized_message:
        raise ValueError("Planner turn message is required.")

    try:
        record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    except ValueError as error:
        raise WorkspacePlannerTripNotFoundError(str(error)) from error
    session_record = _get_or_create_workspace_session_record(db_session, record=record)
    workspace_payload = get_workspace_payload(db_session, user=user, trip_id=trip_id)
    if workspace_payload is None:
        raise WorkspacePlannerTripNotFoundError(f"Trip '{trip_id}' was not found.")

    session = PlanningSessionState.from_dict(_serialize_session_record(session_record))
    now = datetime.now(UTC)
    occurred_at = _isoformat(now)
    runnable = _planner_runnable()
    reply = runnable.invoke(
        PlannerConversationRequest(
            trip_id=trip_id,
            message=normalized_message,
            planner_panel_state=workspace_payload["planner_panel_state"],
            session=session,
        )
    )

    session.updated_at = occurred_at
    session.notes.append(f"planner-turn:{occurred_at}")
    session_record.last_updated_at = occurred_at
    session_record.notes = list(session.notes)
    record.updated_at = now

    user_activity_event_id = f"activity:{trip_id}:{secrets.token_hex(4)}"
    _append_activity_event(
        db_session,
        activity_event_id=user_activity_event_id,
        trip_id=trip_id,
        session_state_id=session.session_state_id,
        occurred_at=occurred_at,
        event_kind="decision_recorded",
        summary="Traveler submitted a planner conversation turn.",
        metadata={"message_length": str(len(normalized_message))},
    )
    _record_planner_action(
        db_session,
        trip_id=trip_id,
        session_state_id=session.session_state_id,
        activity_event_id=user_activity_event_id,
        occurred_at=occurred_at,
        action_type="planner_user_turn",
        payload={
            "role": "user",
            "content": normalized_message,
            "refs": session.session_state_id,
        },
    )

    planner_activity_event_id = f"activity:{trip_id}:{secrets.token_hex(4)}"
    _append_activity_event(
        db_session,
        activity_event_id=planner_activity_event_id,
        trip_id=trip_id,
        session_state_id=session.session_state_id,
        occurred_at=occurred_at,
        event_kind="rerank_requested",
        summary="Planner conversation service generated the next trip-scoped reply.",
        metadata={"ref_count": str(len(reply.refs))},
    )
    _record_planner_action(
        db_session,
        trip_id=trip_id,
        session_state_id=session.session_state_id,
        activity_event_id=planner_activity_event_id,
        occurred_at=occurred_at,
        action_type="planner_response",
        payload={
            "role": "planner",
            "content": reply.content,
            "refs": ",".join(reply.refs),
        },
    )

    db_session.commit()
    return _planner_session_payload(db_session, user=user, trip_id=trip_id)
