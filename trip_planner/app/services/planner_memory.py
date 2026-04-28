"""Helpers for persisted planner checkpoints and user-visible memory."""

from __future__ import annotations

import hashlib
from datetime import UTC
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from trip_planner.persistence.models.planner_memory import (
    PersistedPlannerCheckpoint,
    PersistedPlannerMemoryArtifact,
)
from trip_planner.persistence.models.session import PersistedPlanningSessionState
from trip_planner.persistence.models.activity import PersistedPlannerAction


def _truncate(value: str, limit: int) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 1].rstrip()}…"


def _planner_message_records(
    db_session: Session,
    *,
    session_state_id: str,
) -> list[PersistedPlannerAction]:
    return list(
        db_session.scalars(
            select(PersistedPlannerAction)
            .where(PersistedPlannerAction.session_state_id == session_state_id)
            .where(
                PersistedPlannerAction.action_type.in_(["planner_user_turn", "planner_response"])
            )
            .order_by(
                PersistedPlannerAction.created_at.asc(),
                PersistedPlannerAction.planner_action_id.asc(),
            )
        ).all()
    )


def _checkpoint_summary(
    messages: list[PersistedPlannerAction], *, turn_index: int
) -> dict[str, Any]:
    latest_reply_record = next(
        (record for record in reversed(messages) if record.action_type == "planner_response"),
        None,
    )
    latest_user = next(
        (
            record.payload.get("content", "").strip()
            for record in reversed(messages)
            if record.action_type == "planner_user_turn"
        ),
        "",
    )
    latest_reply = (
        latest_reply_record.payload.get("content", "").strip()
        if latest_reply_record is not None
        else ""
    )
    tool_calls = (
        list(latest_reply_record.payload.get("tool_calls") or [])
        if latest_reply_record is not None
        else []
    )
    selected_planning_mode = (
        str(latest_reply_record.payload.get("selected_planning_mode") or "")
        if latest_reply_record is not None
        else ""
    )
    refs = list(
        dict.fromkeys(
            ref
            for record in messages
            for ref in str(record.payload.get("refs", "")).split(",")
            if ref
        )
    )
    summary = (
        f"Turn {turn_index} checkpoint keeps the latest traveler intent and planner guidance "
        f"available for later resume."
    )
    detail_lines = [
        f"Traveler focus: {_truncate(latest_user or 'No traveler message stored.', 220)}",
        f"Planner summary: {_truncate(latest_reply or 'No planner reply stored.', 320)}",
    ]
    if refs:
        detail_lines.append(f"Linked refs: {', '.join(refs[:4])}")
    if selected_planning_mode:
        detail_lines.append(f"Selected planning mode: {selected_planning_mode}.")
    if tool_calls:
        detail_lines.append(f"Tool traces persisted: {len(tool_calls)}.")
    return {
        "summary": summary,
        "title": f"Planner checkpoint {turn_index}",
        "detail": " ".join(detail_lines),
        "refs": refs[:8],
        "metadata": {
            "ref_count": len(refs[:8]),
            "tool_call_count": len(tool_calls),
            "selected_planning_mode": selected_planning_mode or None,
            "planning_stage": (
                latest_reply_record.payload.get("planning_stage")
                if latest_reply_record is not None
                else None
            ),
            "runtime_mode": (
                latest_reply_record.payload.get("runtime_mode")
                if latest_reply_record is not None
                else None
            ),
        },
    }


def _planner_memory_ids(
    *,
    session_state_id: str,
    source_message_ids: list[str],
) -> tuple[str, str]:
    digest = hashlib.sha256(
        "|".join([session_state_id, *source_message_ids]).encode("utf-8")
    ).hexdigest()[:20]
    return (f"planner-chk:{digest}", f"planner-mem:{digest}")


def refresh_planner_memory(
    db_session: Session,
    *,
    trip_id: str,
    session_state_id: str,
    occurred_at: str | None = None,
) -> str | None:
    db_session.flush()
    messages = _planner_message_records(db_session, session_state_id=session_state_id)
    turn_index = sum(1 for record in messages if record.action_type == "planner_response")
    if turn_index == 0:
        return None

    summary_payload = _checkpoint_summary(messages, turn_index=turn_index)
    source_message_ids = [record.planner_action_id for record in messages[-2:]]
    checkpoint_id, artifact_id = _planner_memory_ids(
        session_state_id=session_state_id,
        source_message_ids=source_message_ids,
    )
    checkpoint = db_session.get(PersistedPlannerCheckpoint, checkpoint_id)
    if checkpoint is None:
        checkpoint = PersistedPlannerCheckpoint(
            checkpoint_id=checkpoint_id,
            trip_id=trip_id,
            session_state_id=session_state_id,
            checkpoint_kind="conversation_summary",
            turn_index=turn_index,
            message_count=len(messages),
            summary=summary_payload["summary"],
            source_message_ids=source_message_ids,
            metadata_payload=summary_payload["metadata"],
        )
        db_session.add(checkpoint)
    else:
        checkpoint.message_count = len(messages)
        checkpoint.summary = summary_payload["summary"]
        checkpoint.source_message_ids = source_message_ids
        checkpoint.metadata_payload = summary_payload["metadata"]

    artifact = db_session.get(PersistedPlannerMemoryArtifact, artifact_id)
    if artifact is None:
        artifact = PersistedPlannerMemoryArtifact(
            memory_artifact_id=artifact_id,
            trip_id=trip_id,
            session_state_id=session_state_id,
            checkpoint_id=checkpoint_id,
            artifact_kind="conversation_summary",
            title=summary_payload["title"],
            summary=summary_payload["summary"],
            detail=summary_payload["detail"],
            source_message_ids=source_message_ids,
            tags=["planner-memory", "user-visible", "checkpoint-summary"],
        )
        db_session.add(artifact)
    else:
        artifact.checkpoint_id = checkpoint_id
        artifact.title = summary_payload["title"]
        artifact.summary = summary_payload["summary"]
        artifact.detail = summary_payload["detail"]
        artifact.source_message_ids = source_message_ids
        artifact.tags = ["planner-memory", "user-visible", "checkpoint-summary"]

    session_record = db_session.get(PersistedPlanningSessionState, session_state_id)
    if session_record is not None:
        session_record.current_checkpoint_id = checkpoint_id
        if occurred_at is not None:
            session_record.last_updated_at = occurred_at
        notes = list(session_record.notes)
        note = f"planner-memory:{checkpoint_id}"
        if note not in notes:
            notes.append(note)
        session_record.notes = notes
    return checkpoint_id


def ensure_planner_memory_persisted(
    db_session: Session,
    *,
    trip_id: str,
    session_state_id: str,
    occurred_at: str | None = None,
) -> str | None:
    messages = _planner_message_records(db_session, session_state_id=session_state_id)
    turn_index = sum(1 for record in messages if record.action_type == "planner_response")
    if turn_index == 0:
        return None

    source_message_ids = [record.planner_action_id for record in messages[-2:]]
    checkpoint_id, artifact_id = _planner_memory_ids(
        session_state_id=session_state_id,
        source_message_ids=source_message_ids,
    )
    if (
        db_session.get(PersistedPlannerCheckpoint, checkpoint_id) is not None
        and db_session.get(PersistedPlannerMemoryArtifact, artifact_id) is not None
    ):
        return checkpoint_id

    return refresh_planner_memory(
        db_session,
        trip_id=trip_id,
        session_state_id=session_state_id,
        occurred_at=occurred_at,
    )


def _serialize_checkpoint(record: PersistedPlannerCheckpoint) -> dict[str, Any]:
    return {
        "checkpoint_id": record.checkpoint_id,
        "checkpoint_kind": record.checkpoint_kind,
        "turn_index": record.turn_index,
        "message_count": record.message_count,
        "summary": record.summary,
        "source_message_ids": list(record.source_message_ids),
        "created_at": record.created_at.astimezone(UTC).isoformat(),
        "updated_at": record.updated_at.astimezone(UTC).isoformat(),
    }


def _serialize_artifact(record: PersistedPlannerMemoryArtifact) -> dict[str, Any]:
    return {
        "memory_artifact_id": record.memory_artifact_id,
        "checkpoint_id": record.checkpoint_id,
        "artifact_kind": record.artifact_kind,
        "title": record.title,
        "summary": record.summary,
        "detail": record.detail,
        "source_message_ids": list(record.source_message_ids),
        "tags": list(record.tags),
        "created_at": record.created_at.astimezone(UTC).isoformat(),
        "updated_at": record.updated_at.astimezone(UTC).isoformat(),
    }


def build_planner_memory_payload(
    db_session: Session,
    *,
    trip_id: str,
    session_state_id: str,
) -> dict[str, Any]:
    checkpoints = db_session.scalars(
        select(PersistedPlannerCheckpoint)
        .where(PersistedPlannerCheckpoint.session_state_id == session_state_id)
        .order_by(
            PersistedPlannerCheckpoint.turn_index.desc(),
            PersistedPlannerCheckpoint.created_at.desc(),
        )
    ).all()
    artifacts = db_session.scalars(
        select(PersistedPlannerMemoryArtifact)
        .where(PersistedPlannerMemoryArtifact.session_state_id == session_state_id)
        .order_by(PersistedPlannerMemoryArtifact.created_at.desc())
    ).all()
    current_checkpoint = checkpoints[0].checkpoint_id if checkpoints else None
    return {
        "current_checkpoint_id": current_checkpoint,
        "checkpoints": [_serialize_checkpoint(record) for record in checkpoints],
        "artifacts": [_serialize_artifact(record) for record in artifacts],
    }
