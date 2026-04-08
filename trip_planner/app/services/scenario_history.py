"""Services for persisted trip-level scenario and planning-history state."""

from __future__ import annotations

from datetime import UTC, datetime
import re
import secrets

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from trip_planner.app.services.auth import AuthenticatedUser
from trip_planner.persistence.models.scenario import (
    PersistedActivityLogEvent,
    PersistedSavedScenario,
)
from trip_planner.persistence.models.session import PersistedPlanningSessionState
from trip_planner.persistence.models.trip import PersistedTrip
from trip_planner.state import (
    ActivityLogEvent,
    PlanningSessionState,
    SESSION_STATE_SCHEMA_VERSION,
    SavedScenarioRecord,
)

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_SAVED_SCENARIO_ID_PREFIX = "saved-scenario:"
_SAVED_SCENARIO_ID_SUFFIX_LENGTH = 7
_SAVED_SCENARIO_ID_MAX_LENGTH = 93
_SAVED_SCENARIO_SLUG_MAX_LENGTH = (
    _SAVED_SCENARIO_ID_MAX_LENGTH
    - len(_SAVED_SCENARIO_ID_PREFIX)
    - _SAVED_SCENARIO_ID_SUFFIX_LENGTH
)
_SESSION_STATE_ID_PREFIX = "session-state:"
_SESSION_STATE_ID_SUFFIX_LENGTH = 7
_SESSION_STATE_ID_MAX_LENGTH = 96
_SESSION_STATE_SLUG_MAX_LENGTH = (
    _SESSION_STATE_ID_MAX_LENGTH
    - len(_SESSION_STATE_ID_PREFIX)
    - _SESSION_STATE_ID_SUFFIX_LENGTH
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _timestamp() -> str:
    return _utcnow().isoformat().replace("+00:00", "Z")


def _slugify(seed: str) -> str:
    slug = _SLUG_RE.sub("-", seed.strip().lower()).strip("-")
    return slug or "entry"


def _slugify_with_limit(seed: str, *, max_length: int) -> str:
    slug = _slugify(seed)
    if len(slug) <= max_length:
        return slug
    return slug[:max_length].rstrip("-") or "entry"


def _not_found(trip_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Trip '{trip_id}' was not found.")


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=400, detail=detail)


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=422, detail=detail)


def _domain_payload_error(error: ValueError) -> HTTPException:
    return _unprocessable(str(error))


def _domain_payload_exception(error: Exception) -> HTTPException:
    if isinstance(error, KeyError) and error.args:
        return _unprocessable(f"{error.args[0]} is required")
    if isinstance(error, TypeError):
        return _unprocessable(str(error))
    if isinstance(error, ValueError):
        return _domain_payload_error(error)
    raise TypeError(f"Unsupported domain payload exception: {type(error)!r}")


def _get_owned_trip(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
) -> PersistedTrip:
    trip = db_session.scalar(
        select(PersistedTrip)
        .where(PersistedTrip.trip_id == trip_id)
        .where(PersistedTrip.user_id == user.user_id)
    )
    if trip is None:
        raise _not_found(trip_id)
    return trip


def _serialize_saved_scenario(record: PersistedSavedScenario) -> dict:
    return SavedScenarioRecord.from_dict(
        {
            "saved_scenario_id": record.saved_scenario_id,
            "trip_id": record.trip_id,
            "current_version_id": record.current_version_id,
            "versions": list(record.versions),
            "comparisons": list(record.comparisons),
            "tags": list(record.tags),
            "notes": list(record.notes),
        }
    ).to_dict()


def _serialize_activity_entry(record: PersistedActivityLogEvent) -> dict:
    return ActivityLogEvent.from_dict(
        {
            "activity_event_id": record.activity_event_id,
            "trip_id": record.trip_id,
            "session_state_id": record.session_state_id,
            "occurred_at": record.occurred_at,
            "event_kind": record.event_kind,
            "summary": record.summary,
            "actor": record.actor,
            "related_decision_id": record.related_decision_id,
            "related_option_set_id": record.related_option_set_id,
            "saved_scenario_id": record.saved_scenario_id,
            "budget_plan_id": record.budget_plan_id,
            "scenario_budget_id": record.scenario_budget_id,
            "checkpoint_id": record.checkpoint_id,
            "metadata": dict(record.metadata_payload),
            "tags": list(record.tags),
            "notes": list(record.notes),
        }
    ).to_dict()


def _serialize_planning_session(record: PersistedPlanningSessionState) -> dict:
    return PlanningSessionState.from_dict(
        {
            "session_state_id": record.session_state_id,
            "trip_id": record.trip_id,
            "user_id": record.user_id,
            "owner_profile_id": record.owner_profile_id,
            "mode": record.mode,
            "started_at": record.started_at,
            "updated_at": record.last_updated_at,
            "interaction_state": dict(record.interaction_state),
            "recent_option_presentations": list(record.recent_option_presentations),
            "pending_decisions": list(record.pending_decisions),
            "status": record.status,
            "current_checkpoint_id": record.current_checkpoint_id,
            "current_saved_scenario_id": record.current_saved_scenario_id,
            "active_budget_plan_id": record.active_budget_plan_id,
            "activity_log_id": record.activity_log_id,
            "schema_version": record.schema_version,
            "tags": list(record.tags),
            "notes": list(record.notes),
        }
    ).to_dict()


def _owner_profile_id_for_trip(trip: PersistedTrip) -> str:
    if trip.mode == "business" and trip.business_profile_id:
        return trip.business_profile_id
    if trip.leisure_profile_id:
        return trip.leisure_profile_id
    return f"profile:{trip.trip_id}:{trip.mode}"


def list_trip_scenario_history(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
) -> dict[str, list[dict]]:
    _get_owned_trip(db_session, user=user, trip_id=trip_id)

    saved_scenarios = db_session.scalars(
        select(PersistedSavedScenario)
        .where(PersistedSavedScenario.trip_id == trip_id)
        .order_by(
            PersistedSavedScenario.updated_at.desc(),
            PersistedSavedScenario.saved_scenario_id.asc(),
        )
    ).all()
    planning_history = db_session.scalars(
        select(PersistedActivityLogEvent)
        .where(PersistedActivityLogEvent.trip_id == trip_id)
        .order_by(
            PersistedActivityLogEvent.occurred_at.desc(),
            PersistedActivityLogEvent.activity_event_id.asc(),
        )
    ).all()
    planning_sessions = db_session.scalars(
        select(PersistedPlanningSessionState)
        .where(PersistedPlanningSessionState.trip_id == trip_id)
        .order_by(
            PersistedPlanningSessionState.last_updated_at.desc(),
            PersistedPlanningSessionState.session_state_id.asc(),
        )
    ).all()

    return {
        "saved_scenarios": [_serialize_saved_scenario(record) for record in saved_scenarios],
        "planning_history": [_serialize_activity_entry(record) for record in planning_history],
        "planning_sessions": [
            _serialize_planning_session(record) for record in planning_sessions
        ],
    }


def create_saved_scenario(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    payload: dict,
) -> dict:
    trip = _get_owned_trip(db_session, user=user, trip_id=trip_id)
    saved_scenario_id = payload.get("saved_scenario_id") or (
        f"{_SAVED_SCENARIO_ID_PREFIX}"
        f"{_slugify_with_limit(payload['title'], max_length=_SAVED_SCENARIO_SLUG_MAX_LENGTH)}"
        f"-{secrets.token_hex(3)}"
    )
    version_id = payload.get("version_id") or f"{saved_scenario_id}-v1"
    created_at = payload.get("created_at") or _timestamp()

    existing = db_session.get(PersistedSavedScenario, saved_scenario_id)
    if existing is not None:
        raise _bad_request(f"Saved scenario '{saved_scenario_id}' already exists.")

    try:
        scenario_record = SavedScenarioRecord.from_dict(
            {
                "saved_scenario_id": saved_scenario_id,
                "trip_id": trip_id,
                "current_version_id": version_id,
                "versions": [
                    {
                        "version_id": version_id,
                        "saved_scenario_id": saved_scenario_id,
                        "trip_id": trip_id,
                        "title": payload["title"],
                        "label": payload["label"],
                        "created_at": created_at,
                        "snapshot_refs": payload.get("snapshot_refs", {}),
                        "created_by": payload.get("created_by", "system"),
                        "scope": payload.get("scope", "route"),
                        "based_on_version_id": payload.get("based_on_version_id"),
                        "summary": payload.get("summary", ""),
                        "tags": payload.get("tags", []),
                        "notes": payload.get("notes", []),
                    }
                ],
                "comparisons": payload.get("comparisons", []),
                "tags": payload.get("tags", []),
                "notes": payload.get("notes", []),
            }
        )
    except ValueError as error:
        raise _domain_payload_error(error) from error

    record = PersistedSavedScenario(
        saved_scenario_id=scenario_record.saved_scenario_id,
        trip_id=trip_id,
        current_version_id=scenario_record.current_version_id,
        versions=[item.to_dict() for item in scenario_record.versions],
        comparisons=[item.to_dict() for item in scenario_record.comparisons],
        tags=list(scenario_record.tags),
        notes=list(scenario_record.notes),
    )
    trip.updated_at = _utcnow()
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return _serialize_saved_scenario(record)


def create_planning_history_entry(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    payload: dict,
) -> dict:
    trip = _get_owned_trip(db_session, user=user, trip_id=trip_id)
    activity_event_id = payload.get("activity_event_id") or (
        f"activity:{_slugify(payload['event_kind'])}-{secrets.token_hex(3)}"
    )
    existing = db_session.get(PersistedActivityLogEvent, activity_event_id)
    if existing is not None:
        raise _bad_request(f"Planning history entry '{activity_event_id}' already exists.")

    try:
        entry = ActivityLogEvent.from_dict(
            {
                "activity_event_id": activity_event_id,
                "trip_id": trip_id,
                "session_state_id": payload.get("session_state_id") or f"session:{trip_id}",
                "occurred_at": payload.get("occurred_at") or _timestamp(),
                "event_kind": payload["event_kind"],
                "summary": payload["summary"],
                "actor": payload.get("actor", "system"),
                "related_decision_id": payload.get("related_decision_id"),
                "related_option_set_id": payload.get("related_option_set_id"),
                "saved_scenario_id": payload.get("saved_scenario_id"),
                "budget_plan_id": payload.get("budget_plan_id"),
                "scenario_budget_id": payload.get("scenario_budget_id"),
                "checkpoint_id": payload.get("checkpoint_id"),
                "metadata": payload.get("metadata", {}),
                "tags": payload.get("tags", []),
                "notes": payload.get("notes", []),
            }
        )
    except ValueError as error:
        raise _domain_payload_error(error) from error

    record = PersistedActivityLogEvent(
        activity_event_id=entry.activity_event_id,
        trip_id=trip_id,
        session_state_id=entry.session_state_id,
        occurred_at=entry.occurred_at,
        event_kind=entry.event_kind,
        summary=entry.summary,
        actor=entry.actor,
        related_decision_id=entry.related_decision_id,
        related_option_set_id=entry.related_option_set_id,
        saved_scenario_id=entry.saved_scenario_id,
        budget_plan_id=entry.budget_plan_id,
        scenario_budget_id=entry.scenario_budget_id,
        checkpoint_id=entry.checkpoint_id,
        metadata_payload=dict(entry.metadata),
        tags=list(entry.tags),
        notes=list(entry.notes),
    )
    trip.updated_at = _utcnow()
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return _serialize_activity_entry(record)


def create_planning_session(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    payload: dict,
) -> dict:
    trip = _get_owned_trip(db_session, user=user, trip_id=trip_id)
    session_state_id = payload.get("session_state_id") or (
        f"{_SESSION_STATE_ID_PREFIX}"
        f"{_slugify_with_limit(trip.title, max_length=_SESSION_STATE_SLUG_MAX_LENGTH)}"
        f"-{secrets.token_hex(3)}"
    )
    started_at = payload.get("started_at") or _timestamp()
    updated_at = payload.get("updated_at") or started_at
    existing = db_session.get(PersistedPlanningSessionState, session_state_id)
    if existing is not None:
        raise _bad_request(f"Planning session '{session_state_id}' already exists.")

    try:
        session_state = PlanningSessionState.from_dict(
            {
                "session_state_id": session_state_id,
                "trip_id": trip_id,
                "user_id": user.user_id,
                "owner_profile_id": payload.get("owner_profile_id")
                or _owner_profile_id_for_trip(trip),
                "mode": payload.get("mode") or trip.mode,
                "started_at": started_at,
                "updated_at": updated_at,
                "interaction_state": payload.get("interaction_state", {}),
                "recent_option_presentations": payload.get(
                    "recent_option_presentations", []
                ),
                "pending_decisions": payload.get("pending_decisions", []),
                "status": payload.get("status", "active"),
                "current_checkpoint_id": payload.get("current_checkpoint_id"),
                "current_saved_scenario_id": payload.get("current_saved_scenario_id"),
                "active_budget_plan_id": payload.get("active_budget_plan_id"),
                "activity_log_id": payload.get("activity_log_id"),
                "schema_version": payload.get("schema_version")
                or SESSION_STATE_SCHEMA_VERSION,
                "tags": payload.get("tags", []),
                "notes": payload.get("notes", []),
            }
        )
    except (KeyError, TypeError, ValueError) as error:
        raise _domain_payload_exception(error) from error

    record = PersistedPlanningSessionState(
        session_state_id=session_state.session_state_id,
        trip_id=session_state.trip_id,
        user_id=session_state.user_id,
        owner_profile_id=session_state.owner_profile_id,
        mode=session_state.mode,
        started_at=session_state.started_at,
        last_updated_at=session_state.updated_at,
        interaction_state=session_state.interaction_state.to_dict(),
        recent_option_presentations=[
            item.to_dict() for item in session_state.recent_option_presentations
        ],
        pending_decisions=[item.to_dict() for item in session_state.pending_decisions],
        status=session_state.status,
        current_checkpoint_id=session_state.current_checkpoint_id,
        current_saved_scenario_id=session_state.current_saved_scenario_id,
        active_budget_plan_id=session_state.active_budget_plan_id,
        activity_log_id=session_state.activity_log_id,
        schema_version=session_state.schema_version,
        tags=list(session_state.tags),
        notes=list(session_state.notes),
    )
    trip.updated_at = _utcnow()
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return _serialize_planning_session(record)
