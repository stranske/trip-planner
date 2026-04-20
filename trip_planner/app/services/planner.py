"""Trip-scoped planner conversation services."""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from trip_planner.app.services.auth import AuthenticatedUser
from trip_planner.app.services.planner_memory import (
    build_planner_memory_payload,
    ensure_planner_memory_persisted,
    refresh_planner_memory,
)
from trip_planner.app.services.planner_runtime_config import (
    PlannerRuntimeConfig,
    get_planner_runtime_config,
)
from trip_planner.app.services.planner_tools import (
    execute_planner_tool_call,
    list_planner_tools,
)
from trip_planner.preferences.autonomy import AutonomyGuardrails
from trip_planner.app.services.workspace import (
    WORKSPACE_ACTIVITY_LOG_LIMIT,
    _append_activity_event,
    _get_or_create_workspace_session_record,
    _get_owned_trip_record,
    _isoformat,
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

@dataclass(frozen=True, slots=True)
class PlannerConversationRequest:
    trip_id: str
    message: str
    planner_panel_state: dict[str, Any]
    session: PlanningSessionState
    runtime_context: dict[str, Any]


@dataclass(frozen=True, slots=True)
class PlannerConversationReply:
    content: str
    refs: list[str]
    tool_calls: list[dict[str, Any]]
    requested_tool_calls: list[dict[str, Any]] | None = None


class PlannerChatModel(Protocol):
    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return planner content and optional tool call requests."""


PlannerChatModelFactory = Callable[[PlannerRuntimeConfig], PlannerChatModel]

_PLANNER_CHAT_MODEL_FACTORY: PlannerChatModelFactory | None = None


def set_planner_chat_model_factory_for_tests(factory: PlannerChatModelFactory | None) -> None:
    global _PLANNER_CHAT_MODEL_FACTORY
    _PLANNER_CHAT_MODEL_FACTORY = factory


class PlannerConversationRunnable(Protocol):
    """LangChain-style runnable abstraction for planner conversation turns."""

    def invoke(self, request: PlannerConversationRequest) -> PlannerConversationReply:
        """Return one planner response for the provided turn."""


class DeterministicPlannerConversationRunnable:
    """Provider-neutral fallback when planner model configuration is absent."""

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
            "Deterministic planner fallback is active; configure a planner model for tool-grounded orchestration."
        )
        deduped_refs = list(dict.fromkeys(refs))
        return PlannerConversationReply(content=" ".join(lines), refs=deduped_refs, tool_calls=[])


class _OpenAIPlannerChatModel:
    def __init__(self, config: PlannerRuntimeConfig) -> None:
        if not config.model:
            raise ValueError("Planner model name is required.")
        from langchain_openai import ChatOpenAI

        self._model = ChatOpenAI(model=config.model, temperature=0)

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": tool["tool_name"],
                    "description": tool["description"],
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": True,
                    },
                },
            }
            for tool in payload["available_tools"]
        ]
        model = self._model.bind_tools(tools)
        response = model.invoke(
            [
                (
                    "system",
                    "You are a trip-scoped planner. Use only the listed app tools for "
                    "workspace, inventory, scenario, budget, policy, or proposal facts. "
                    "Do not invent persisted state.",
                ),
                (
                    "human",
                    json.dumps(
                        {
                            "message": payload["message"],
                            "context": payload["runtime_context"],
                        },
                        default=str,
                    ),
                ),
            ]
        )
        tool_calls: list[dict[str, Any]] = []
        for call in getattr(response, "tool_calls", []) or []:
            tool_calls.append(
                {
                    "tool_name": call.get("name") or call.get("tool_name") or "",
                    "arguments": call.get("args") or call.get("arguments") or {},
                }
            )
        return {"content": str(response.content), "tool_calls": tool_calls}


class ModelBackedPlannerConversationRunnable:
    def __init__(self, config: PlannerRuntimeConfig, chat_model: PlannerChatModel) -> None:
        self._config = config
        self._chat_model = chat_model

    def invoke(self, request: PlannerConversationRequest) -> PlannerConversationReply:
        raw = self._chat_model.invoke(
            {
                "message": request.message,
                "trip_id": request.trip_id,
                "available_tools": list_planner_tools(),
                "runtime_context": request.runtime_context,
                "provider": self._config.provider,
                "model": self._config.model,
            }
        )
        content = str(raw.get("content") or "").strip()
        if not content:
            content = "Planner model returned an empty response after reading the current trip context."
        requested_tool_calls = [
            {
                "tool_name": str(item.get("tool_name") or item.get("name") or ""),
                "arguments": item.get("arguments") or item.get("args") or {},
            }
            for item in list(raw.get("tool_calls") or [])
        ]
        return PlannerConversationReply(
            content=content,
            refs=[request.session.session_state_id],
            tool_calls=[],
            requested_tool_calls=requested_tool_calls,
        )


def _planner_runnable(config: PlannerRuntimeConfig) -> PlannerConversationRunnable:
    if config.mode != "model":
        return DeterministicPlannerConversationRunnable()
    factory = _PLANNER_CHAT_MODEL_FACTORY or (lambda runtime_config: _OpenAIPlannerChatModel(runtime_config))
    return ModelBackedPlannerConversationRunnable(config, factory(config))


def _conversation_id(trip_id: str) -> str:
    return f"planner-conversation:{trip_id}"


def _message_payload(
    *,
    message_id: str,
    role: str,
    content: str,
    created_at: str,
    refs: list[str] | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "message_id": message_id,
        "role": role,
        "content": content,
        "created_at": created_at,
        "refs": list(refs or []),
        "tool_calls": list(tool_calls or []),
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
        tool_calls = list(record.payload.get("tool_calls") or [])
        messages.append(
            _message_payload(
                message_id=record.planner_action_id,
                role=role,
                content=record.payload.get("content", ""),
                created_at=record.occurred_at,
                refs=refs,
                tool_calls=tool_calls,
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


def _planner_runtime_context(
    workspace_payload: dict[str, Any],
    *,
    session: PlanningSessionState,
    planner_memory: dict[str, Any],
    activity_log: list[dict[str, Any]],
) -> dict[str, Any]:
    panel = workspace_payload["planner_panel_state"]
    required_sections = {
        "inventory_summary": workspace_payload.get("inventory_summary") or {},
        "scenario_search": workspace_payload.get("scenario_search") or {},
        "runtime_scenario_comparison": workspace_payload.get("runtime_scenario_comparison") or {},
        "budget_state": workspace_payload.get("budget_state") or {},
        "planner_memory": planner_memory,
    }
    missing_sections = [key for key, value in required_sections.items() if not value]
    return {
        "trip": panel["trip"],
        "pending_decisions": panel.get("pending_decisions") or [],
        "option_set": panel.get("option_set") or {},
        "outputs": panel.get("outputs") or [],
        **required_sections,
        "policy_state": workspace_payload.get("policy_state") or {},
        "proposal_state": workspace_payload.get("proposal_state") or {},
        "autonomy_preferences": {
            "interaction_state": session.interaction_state.to_dict(),
            "guardrails": AutonomyGuardrails().to_dict(),
            "planner_behavior": panel.get("planner_behavior") or {},
        },
        "recent_activity": activity_log[:8],
        "context_readiness": {
            "status": "partial" if missing_sections else "ready",
            "missing_sections": missing_sections,
        },
    }


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
    planner_memory = build_planner_memory_payload(
        db_session,
        trip_id=trip_id,
        session_state_id=session_state_id,
    )
    activity_log = _activity_log(db_session, trip_id=trip_id)
    return {
        "trip_id": trip_id,
        "session_state_id": session_state_id,
        "conversation_id": _conversation_id(trip_id),
        "resumed_at": resumed_at,
        "runtime": get_planner_runtime_config().to_payload(),
        "session": session,
        "planner_panel_state": workspace_payload["planner_panel_state"],
        "planner_memory": planner_memory,
        "available_tools": list_planner_tools(),
        "activity_log": activity_log,
        "messages": _conversation_messages(db_session, session_state_id=session_state_id),
    }


def _tool_call_error(tool_name: str, message: str) -> dict[str, Any]:
    return {
        "tool_name": tool_name or "unknown",
        "status": "error",
        "summary": message,
        "mutates_state": False,
        "refs": [],
        "output": {"error": message},
    }


def _planner_model_error_reply(
    *,
    session_state_id: str,
    error: Exception,
) -> PlannerConversationReply:
    message = (
        "Planner model runtime failed before it could complete the turn. "
        "The traveler message was saved, and the visible error state is available for retry."
    )
    return PlannerConversationReply(
        content=f"{message} Error: {error}",
        refs=[session_state_id],
        tool_calls=[_tool_call_error("planner_model", str(error))],
    )


def _execute_model_tool_calls(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    tool_calls: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    executed: list[dict[str, Any]] = []
    for tool_call in tool_calls or []:
        tool_name = str(tool_call.get("tool_name") or "")
        try:
            result = execute_planner_tool_call(
                db_session,
                user=user,
                trip_id=trip_id,
                tool_name=tool_name,
                arguments=tool_call.get("arguments") or {},
            )
        except Exception as error:
            executed.append(_tool_call_error(tool_name, str(error)))
        else:
            executed.append(result.to_dict())
    return executed


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
    ensure_planner_memory_persisted(
        db_session,
        trip_id=trip_id,
        session_state_id=session_record.session_state_id,
        occurred_at=resumed_at,
    )
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
    tool_calls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized_message = message.strip()
    if not normalized_message:
        raise ValueError("Planner turn message is required.")

    try:
        record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    except ValueError as error:
        raise WorkspacePlannerTripNotFoundError(str(error)) from error
    session_record = _get_or_create_workspace_session_record(db_session, record=record)
    now = datetime.now(UTC)
    occurred_at = _isoformat(now)
    session = PlanningSessionState.from_dict(_serialize_session_record(session_record))

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
        event_kind="planner_message",
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
            "tool_calls": [],
            "selected_planning_mode": session.mode,
        },
    )

    executed_tool_calls: list[dict[str, Any]] = []
    for tool_call in tool_calls or []:
        result = execute_planner_tool_call(
            db_session,
            user=user,
            trip_id=trip_id,
            tool_name=str(tool_call.get("tool_name") or ""),
            arguments=tool_call.get("arguments") or {},
        )
        executed_tool_calls.append(result.to_dict())

    workspace_payload = get_workspace_payload(db_session, user=user, trip_id=trip_id)
    if workspace_payload is None:
        raise WorkspacePlannerTripNotFoundError(f"Trip '{trip_id}' was not found.")
    session = PlanningSessionState.from_dict(_serialize_session_record(session_record))
    planner_memory = build_planner_memory_payload(
        db_session,
        trip_id=trip_id,
        session_state_id=session.session_state_id,
    )
    activity_log = _activity_log(db_session, trip_id=trip_id)
    runtime_config = get_planner_runtime_config()
    runnable = _planner_runnable(runtime_config)
    runtime_context = _planner_runtime_context(
        workspace_payload,
        session=session,
        planner_memory=planner_memory,
        activity_log=activity_log,
    )
    try:
        reply = runnable.invoke(
            PlannerConversationRequest(
                trip_id=trip_id,
                message=normalized_message,
                planner_panel_state=workspace_payload["planner_panel_state"],
                session=session,
                runtime_context=runtime_context,
            )
        )
    except Exception as error:
        reply = _planner_model_error_reply(
            session_state_id=session.session_state_id,
            error=error,
        )
    model_tool_calls = _execute_model_tool_calls(
        db_session,
        user=user,
        trip_id=trip_id,
        tool_calls=reply.requested_tool_calls,
    )
    executed_tool_calls.extend(model_tool_calls)
    if executed_tool_calls:
        tool_summary = " ".join(item["summary"] for item in executed_tool_calls)
        reply = PlannerConversationReply(
            content=f"{reply.content} Tool results: {tool_summary}",
            refs=list(dict.fromkeys(reply.refs + [ref for item in executed_tool_calls for ref in item["refs"]])),
            tool_calls=executed_tool_calls,
        )

    planner_activity_event_id = f"activity:{trip_id}:{secrets.token_hex(4)}"
    _append_activity_event(
        db_session,
        activity_event_id=planner_activity_event_id,
        trip_id=trip_id,
        session_state_id=session.session_state_id,
        occurred_at=occurred_at,
        event_kind="planner_message",
        summary="Planner conversation service generated the next trip-scoped reply.",
        actor="planner",
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
            "tool_calls": reply.tool_calls,
            "selected_planning_mode": session.mode,
            "planning_stage": (
                workspace_payload["planner_panel_state"]
                .get("planner_behavior", {})
                .get("trip_stage")
            ),
            "runtime_mode": runtime_config.mode,
            "context_readiness": runtime_context["context_readiness"],
        },
    )
    refresh_planner_memory(
        db_session,
        trip_id=trip_id,
        session_state_id=session.session_state_id,
        occurred_at=occurred_at,
    )

    db_session.commit()
    return _planner_session_payload(db_session, user=user, trip_id=trip_id)
