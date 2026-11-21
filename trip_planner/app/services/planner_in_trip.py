"""Translate typed in-trip results into the planner's existing persisted state."""

import json
from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy.orm import Session

from trip_planner.app.services.auth import AuthenticatedUser
from trip_planner.app.services.workspace import (
    _get_or_create_workspace_session_record,
    _get_owned_trip_record,
    _isoformat,
    _lock_workspace_trip,
    _record_planner_action,
    _serialize_session_record,
)
from trip_planner.orchestration import (
    InTripAdjustmentContext,
    InTripRevisionOutput,
    InTripTriggerEvent,
    build_in_trip_adjustment_result,
)
from trip_planner.persistence.models.activity import PersistedActivityLogEvent
from trip_planner.persistence.models.scenario import PersistedSavedScenario
from trip_planner.state.scenarios import ScenarioArtifactRefs, ScenarioVersion
from trip_planner.state.sessions import PlanningSessionState


class InTripEventConflictError(ValueError):
    """An event ID was reused with a different payload."""


def _save_revision(
    db: Session,
    *,
    base: ScenarioVersion,
    revision: InTripRevisionOutput,
    session_id: str,
    event_key: str,
) -> str | None:
    if revision.output_kind not in {"scenario_revision", "emergency_fallback"}:
        return None

    scenario_id = f"saved-scenario:in-trip:{event_key}"
    version = ScenarioVersion(
        version_id=f"{scenario_id}-v1",
        saved_scenario_id=scenario_id,
        trip_id=base.trip_id,
        title=f"In-trip revision of {base.title}",
        label="in_trip_revision",
        created_at=revision.generated_at,
        snapshot_refs=ScenarioArtifactRefs(
            scenario_search_id=base.snapshot_refs.scenario_search_id,
            session_state_id=session_id,
            policy_state_id=base.snapshot_refs.policy_state_id,
            budget_state_id=base.snapshot_refs.budget_state_id,
        ),
        created_by="planner",
        scope=base.scope,
        based_on_version_id=base.version_id,
        summary=revision.summary,
        tags=["pending-replan"],
        notes=[f"Revision output {revision.revision_output_id}."],
    )
    db.add(
        PersistedSavedScenario(
            saved_scenario_id=scenario_id,
            trip_id=base.trip_id,
            current_version_id=version.version_id,
            versions=[version.to_dict()],
            tags=["in-trip", "pending-replan"],
        )
    )
    return scenario_id


def persist_in_trip_event(
    db: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    event: InTripTriggerEvent,
) -> None:
    """Write the activity, session change, scenario and planner turn atomically."""
    if event.trip_id != trip_id or len(event.summary) > 600:
        raise ValueError("The event must match the trip and fit the activity summary.")

    _lock_workspace_trip(db, trip_id=trip_id, user_id=user.user_id)

    key = sha256(json.dumps([trip_id, event.trigger_event_id]).encode()).hexdigest()[:32]
    fingerprint = sha256(json.dumps(event.to_dict(), sort_keys=True).encode()).hexdigest()
    activity_id = f"activity:in-trip:{key}"
    existing = db.get(PersistedActivityLogEvent, activity_id)
    if existing is not None:
        if existing.metadata_payload.get("event_fingerprint") != fingerprint:
            raise InTripEventConflictError("Event ID already has a different payload.")
        return

    trip = _get_owned_trip_record(db, user=user, trip_id=trip_id)
    record = _get_or_create_workspace_session_record(db, record=trip)
    session = PlanningSessionState.from_dict(_serialize_session_record(record))
    scenario_id = session.current_saved_scenario_id
    if event.affected_saved_scenario_id not in {None, scenario_id}:
        raise ValueError("The event must refer to the current saved scenario.")
    if event.affected_checkpoint_id not in {None, session.current_checkpoint_id}:
        raise ValueError("The event must refer to the current checkpoint.")
    saved = db.get(PersistedSavedScenario, scenario_id) if scenario_id else None
    if saved is None or saved.trip_id != trip_id:
        raise ValueError("Save a scenario before processing an in-trip event.")
    base = ScenarioVersion.from_dict(
        next(
            version
            for version in saved.versions
            if version["version_id"] == saved.current_version_id
        )
    )
    search_id = base.snapshot_refs.scenario_search_id
    if search_id is None:
        raise ValueError("The saved scenario must reference a scenario search.")
    occurred_at = _isoformat(datetime.now(UTC))
    context = InTripAdjustmentContext(
        session_state=session,
        scenario_search_id=search_id,
        ranked_result_set_id=base.snapshot_refs.ranked_result_set_id,
        generated_at=occurred_at,
    )
    result = build_in_trip_adjustment_result(context, event)
    revised_id = _save_revision(
        db,
        base=base,
        revision=result.revision_output,
        session_id=session.session_state_id,
        event_key=key,
    )
    updated = result.updated_session_state
    record.pending_decisions = [decision.to_dict() for decision in updated.pending_decisions]
    record.tags = list(updated.tags)
    record.notes = list(updated.notes)
    record.last_updated_at = updated.updated_at

    previous_ids = {decision.decision_id for decision in session.pending_decisions}
    decision_id = next(
        (d.decision_id for d in updated.pending_decisions if d.decision_id not in previous_ids),
        None,
    )
    # PostgreSQL enforces the same length for both activity and action links.
    if decision_id is not None and len(decision_id) > 96:
        raise ValueError("The derived in-trip decision ID exceeds 96 characters.")
    activity = result.activity_event
    db.add(
        PersistedActivityLogEvent(
            activity_event_id=activity_id,
            trip_id=trip_id,
            session_state_id=session.session_state_id,
            occurred_at=occurred_at,
            event_kind=activity.event_kind,
            summary=activity.summary,
            actor=user.user_id,
            related_decision_id=decision_id,
            related_option_set_id=activity.related_option_set_id,
            saved_scenario_id=activity.saved_scenario_id,
            checkpoint_id=activity.checkpoint_id,
            budget_plan_id=activity.budget_plan_id,
            metadata_payload={**activity.metadata, "event_fingerprint": fingerprint},
            tags=activity.tags,
            notes=activity.notes,
        )
    )
    db.flush()
    _record_planner_action(
        db,
        trip_id=trip_id,
        session_state_id=session.session_state_id,
        activity_event_id=activity_id,
        occurred_at=occurred_at,
        action_type="planner_response",
        decision_id=decision_id,
        payload={
            "role": "planner",
            "content": result.revision_output.summary,
            "refs": ",".join(ref for ref in (activity_id, revised_id) if ref),
            "structured_blocks": [
                {
                    "kind": "in_trip_turn",
                    "title": "In-trip adjustment",
                    "items": [result.planner_turn.next_step.headline],
                    "metadata": {
                        "trigger_event_id": event.trigger_event_id,
                        "activity_event_id": activity_id,
                        "saved_scenario_id": revised_id,
                        "planner_turn": result.planner_turn.to_dict(),
                        "revision_output": result.revision_output.to_dict(),
                        "replanning_request": result.replanning_request.to_dict(),
                    },
                }
            ],
        },
    )
