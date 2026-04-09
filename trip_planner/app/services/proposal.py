from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from trip_planner.app.services.auth import AuthenticatedUser
from trip_planner.business import ExceptionRequest, TripPlanProposal
from trip_planner.integrations.tpp import (
    BaseTPPIntegrationClient,
    TPPEvaluationResultIngestionService,
    TPPProposalSubmissionService,
    TPPRequestEnvelope,
    TPPResponseEnvelope,
)
from trip_planner.persistence.models.proposal import PersistedProposalState
from trip_planner.persistence.models.trip import PersistedTrip


class WorkspaceProposalNotFoundError(ValueError):
    """Raised when workspace proposal state or trip ownership is missing."""


def _owner_profile_id(record: PersistedTrip) -> str:
    if record.mode == "business" and record.business_profile_id:
        return record.business_profile_id
    if record.leisure_profile_id:
        return record.leisure_profile_id
    return f"profile:{record.trip_id}:{record.mode}"


def _get_owned_trip_record(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
) -> PersistedTrip:
    record = db_session.scalar(
        select(PersistedTrip)
        .where(PersistedTrip.trip_id == trip_id)
        .where(PersistedTrip.user_id == user.user_id)
    )
    if record is None:
        raise WorkspaceProposalNotFoundError(f"Trip '{trip_id}' was not found.")
    return record


def _get_latest_proposal_state(
    db_session: Session,
    *,
    trip_id: str,
    user_id: str,
) -> PersistedProposalState | None:
    return db_session.scalar(
        select(PersistedProposalState)
        .where(PersistedProposalState.trip_id == trip_id)
        .where(PersistedProposalState.user_id == user_id)
        .order_by(PersistedProposalState.updated_at.desc())
    )


class _PassiveTPPClient(BaseTPPIntegrationClient):
    def __init__(self, response: TPPResponseEnvelope) -> None:
        self.response = response

    def execute(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        return self.response


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _derive_follow_up_state(
    *,
    proposal_payload: dict[str, Any],
    evaluation_record: dict[str, Any],
    persisted_follow_up: dict[str, Any] | None = None,
    submission_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evaluation_result = dict(evaluation_record.get("evaluation_result") or {})
    preferred_alternatives = list(evaluation_result.get("preferred_alternatives") or [])
    approval_requirements = list(evaluation_result.get("approval_requirements") or [])
    failure_reasons = list(evaluation_result.get("failure_reasons") or [])
    exception_guidance = list(evaluation_result.get("exception_guidance") or [])
    requested_exception = proposal_payload.get("requested_exception")
    status = evaluation_result.get("status")

    follow_up: dict[str, Any]

    if status == "compliant":
        follow_up = {
            "status": "resolved",
            "path": "approval",
            "title": "Approval-ready proposal",
            "summary": "Policy evaluation passed. Move the workspace packet into final approval handling.",
            "recommended_action": "prepare_approval",
            "recommended_label": "Advance to approval",
        }
    elif status == "non_compliant":
        alternative = preferred_alternatives[0] if preferred_alternatives else None
        follow_up = {
            "status": "reoptimization_required",
            "path": "reoptimization",
            "title": "Reoptimization path required",
            "summary": (
                alternative.get("summary")
                if isinstance(alternative, dict) and alternative.get("summary")
                else "The current proposal is non-compliant. Rebuild it around a policy-safe alternative."
            ),
            "recommended_action": "reoptimize",
            "recommended_label": "Reoptimize plan",
        }
    elif status == "exception_required":
        follow_up = {
            "status": "exception_requested" if requested_exception else "exception_required",
            "path": "exception",
            "title": "Exception path required",
            "summary": (
                requested_exception.get("reason")
                if isinstance(requested_exception, dict) and requested_exception.get("reason")
                else "The workspace needs an exception-oriented next step before booking can proceed."
            ),
            "recommended_action": (
                "await_approval" if requested_exception else "request_exception"
            ),
            "recommended_label": (
                "Review drafted exception" if requested_exception else "Prepare exception request"
            ),
        }
    else:
        follow_up = {
            "status": "awaiting_evaluation",
            "path": "pending",
            "title": "Awaiting policy verdict",
            "summary": (
                dict(submission_record or {}).get("execution_status", {}).get("summary")
                or "Proposal transport is stored. Wait for the policy result before choosing a follow-up path."
            ),
            "recommended_action": "monitor_submission",
            "recommended_label": "Monitor evaluation",
        }

    follow_up["alternatives"] = preferred_alternatives
    follow_up["approval_requirements"] = approval_requirements
    follow_up["failure_reasons"] = failure_reasons
    follow_up["guidance"] = exception_guidance
    follow_up["requested_exception"] = requested_exception
    follow_up["selected_alternative"] = None
    follow_up["notes"] = []

    if persisted_follow_up and persisted_follow_up.get("manual"):
        for key in (
            "status",
            "path",
            "title",
            "summary",
            "recommended_action",
            "recommended_label",
            "selected_alternative",
            "notes",
            "updated_at",
        ):
            if key in persisted_follow_up and persisted_follow_up[key] not in (None, ""):
                follow_up[key] = persisted_follow_up[key]
        if persisted_follow_up.get("requested_exception") is not None:
            follow_up["requested_exception"] = persisted_follow_up["requested_exception"]

    return follow_up


def _build_summary(
    *,
    submission_record: dict[str, Any],
    evaluation_record: dict[str, Any],
    proposal_payload: dict[str, Any],
    persisted_follow_up: dict[str, Any] | None = None,
) -> dict[str, Any]:
    execution_status = dict(submission_record.get("execution_status") or {})
    evaluation_transport = dict(evaluation_record.get("execution_status") or {})
    evaluation_result = dict(evaluation_record.get("evaluation_result") or {})
    failure_reasons = list(evaluation_result.get("failure_reasons") or [])
    follow_up = _derive_follow_up_state(
        proposal_payload=proposal_payload,
        evaluation_record=evaluation_record,
        persisted_follow_up=persisted_follow_up,
        submission_record=submission_record,
    )
    highlights = (
        list(evaluation_result.get("notes") or [])[:2]
        if evaluation_result
        else list(proposal_payload.get("approval_notes") or [])[:2]
    )
    if follow_up.get("summary"):
        highlights = [str(follow_up["summary"]), *highlights][:3]
    return {
        "trip_id": proposal_payload.get("trip_id"),
        "proposal_id": proposal_payload.get("proposal_id"),
        "proposal_version": submission_record.get("linkage", {}).get("proposal_version"),
        "submission_status": execution_status.get("state"),
        "submission_summary": execution_status.get("summary"),
        "submission_requires_polling": execution_status.get("terminal") is False,
        "evaluation_transport_status": evaluation_transport.get("state"),
        "evaluation_result_status": evaluation_result.get("status"),
        "approval_ready": evaluation_result.get("status") == "compliant",
        "comparable_count": len(proposal_payload.get("comparables") or []),
        "approval_requirement_count": len(evaluation_result.get("approval_requirements") or []),
        "blocking_failure_count": len(
            [item for item in failure_reasons if item.get("severity") == "blocking"]
        ),
        "highlights": highlights,
        "follow_up_status": follow_up.get("status"),
        "follow_up_title": follow_up.get("title"),
        "follow_up_summary": follow_up.get("summary"),
        "follow_up": follow_up,
    }


_FOLLOW_UP_PATH_BY_STATUS: dict[str, str] = {
    "reoptimization_required": "reoptimization",
    "reoptimized": "reoptimization",
    "exception_required": "exception",
    "exception_requested": "exception",
}
_FOLLOW_UP_STATUSES_USING_EXISTING_PATH = {"approval_pending", "resolved"}


def _resolved_follow_up_payload(record: PersistedProposalState) -> dict[str, Any]:
    follow_up = dict(record.summary.get("follow_up") or {})
    if follow_up:
        return follow_up
    return _derive_follow_up_state(
        proposal_payload=dict(record.proposal_payload),
        evaluation_record=dict(record.evaluation_record),
        submission_record=dict(record.submission_record),
    )


def _resolve_manual_follow_up_path(
    *, existing_follow_up: dict[str, Any], status: str
) -> str:
    if status in _FOLLOW_UP_PATH_BY_STATUS:
        return _FOLLOW_UP_PATH_BY_STATUS[status]
    if status in _FOLLOW_UP_STATUSES_USING_EXISTING_PATH:
        existing_path = existing_follow_up.get("path")
        if existing_path in {"approval", "exception", "reoptimization"}:
            return str(existing_path)
        raise ValueError(
            f"Cannot store follow-up status '{status}' without an existing follow-up path."
        )
    raise ValueError(f"Unsupported workspace proposal follow-up status: {status}")


def _reset_evaluation_state(record: PersistedProposalState) -> None:
    record.evaluation_status = None
    record.evaluation_record = {}


def _serialize_proposal_state(record: PersistedProposalState) -> dict[str, Any]:
    follow_up = _resolved_follow_up_payload(record)
    return {
        "proposal_state_id": record.proposal_state_id,
        "trip_id": record.trip_id,
        "owner_profile_id": record.owner_profile_id,
        "proposal_id": record.proposal_id,
        "proposal_version": record.proposal_version,
        "scenario_id": record.scenario_id,
        "organization_id": record.organization_id,
        "execution_id": record.execution_id,
        "submission_status": record.submission_status,
        "evaluation_status": record.evaluation_status,
        "proposal": dict(record.proposal_payload),
        "submission": dict(record.submission_record),
        "evaluation": dict(record.evaluation_record),
        "summary": dict(record.summary),
        "follow_up": follow_up,
    }


def get_workspace_proposal_payload(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
) -> dict[str, Any]:
    _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    proposal_state = _get_latest_proposal_state(db_session, trip_id=trip_id, user_id=user.user_id)
    if proposal_state is None:
        return {
            "proposal_state": None,
            "summary": {"trip_id": trip_id, "status": "missing"},
        }
    return {
        "proposal_state": _serialize_proposal_state(proposal_state),
        "summary": dict(proposal_state.summary),
    }


def save_workspace_proposal_submission(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    proposal_payload: dict[str, Any],
    request_payload: dict[str, Any],
    response_payload: dict[str, Any],
    proposal_version: str,
    scenario_id: str | None,
) -> dict[str, Any]:
    trip_record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    if trip_record.mode != "business":
        raise ValueError("Only business trips can persist proposal lifecycle state.")

    proposal = TripPlanProposal.from_dict(proposal_payload)
    if proposal.trip_id != trip_id:
        raise ValueError("proposal.trip_id must match the workspace trip.")

    request = TPPRequestEnvelope.from_dict(request_payload)
    response = TPPResponseEnvelope.from_dict(response_payload)
    submission = TPPProposalSubmissionService(_PassiveTPPClient(response)).submit_proposal(
        request,
        proposal,
        proposal_version=proposal_version,
        scenario_id=scenario_id,
    )

    existing = _get_latest_proposal_state(db_session, trip_id=trip_id, user_id=user.user_id)
    proposal_state_id = (
        existing.proposal_state_id if existing is not None else f"proposal-state:{trip_id}"
    )
    record = existing or PersistedProposalState(
        proposal_state_id=proposal_state_id,
        trip_id=trip_id,
        user_id=user.user_id,
        owner_profile_id=_owner_profile_id(trip_record),
        proposal_id=proposal.proposal_id,
        proposal_version=proposal_version,
        scenario_id=submission.linkage.scenario_id,
        organization_id=submission.linkage.organization_id,
        execution_id=submission.execution_id,
        submission_status=submission.execution_status.state,
        evaluation_status=None,
        proposal_payload=proposal.to_dict(),
        submission_record=submission.to_dict(),
        evaluation_record={},
        summary={},
    )
    record.owner_profile_id = _owner_profile_id(trip_record)
    record.proposal_id = proposal.proposal_id
    record.proposal_version = submission.linkage.proposal_version
    record.scenario_id = submission.linkage.scenario_id
    record.organization_id = submission.linkage.organization_id
    record.execution_id = submission.execution_id
    record.submission_status = submission.execution_status.state
    record.proposal_payload = proposal.to_dict()
    record.submission_record = submission.to_dict()
    _reset_evaluation_state(record)
    record.summary = _build_summary(
        submission_record=record.submission_record,
        evaluation_record={},
        proposal_payload=record.proposal_payload,
        persisted_follow_up=dict(existing.summary.get("follow_up") or {}) if existing else None,
    )

    if existing is None:
        db_session.add(record)

    trip_record.updated_at = datetime.now(UTC)
    db_session.commit()
    db_session.refresh(record)
    return {
        "proposal_state": _serialize_proposal_state(record),
        "summary": dict(record.summary),
    }


def save_workspace_proposal_evaluation(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    request_payload: dict[str, Any],
    response_payload: dict[str, Any],
    proposal_version: str,
    scenario_id: str | None,
) -> dict[str, Any]:
    trip_record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    if trip_record.mode != "business":
        raise ValueError("Only business trips can persist proposal lifecycle state.")

    existing = _get_latest_proposal_state(db_session, trip_id=trip_id, user_id=user.user_id)
    if existing is None:
        raise WorkspaceProposalNotFoundError(
            "Proposal evaluation cannot be stored before a proposal submission exists."
        )

    request = TPPRequestEnvelope.from_dict(request_payload)
    response = TPPResponseEnvelope.from_dict(response_payload)
    evaluation = TPPEvaluationResultIngestionService(_PassiveTPPClient(response)).fetch_evaluation_result(
        request,
        proposal_version=proposal_version,
        scenario_id=scenario_id,
    )
    if request.trip_id is not None and request.trip_id != trip_id:
        raise ValueError("evaluation request.trip_id must match the workspace trip.")
    if evaluation.linkage.trip_id != trip_id:
        raise ValueError("evaluation linkage.trip_id must match the workspace trip.")
    if evaluation.linkage.proposal_id != existing.proposal_id:
        raise ValueError("evaluation linkage.proposal_id must match the persisted proposal.")
    if evaluation.linkage.proposal_version != existing.proposal_version:
        raise ValueError(
            "evaluation linkage.proposal_version must match the persisted proposal version."
        )

    existing.proposal_version = evaluation.linkage.proposal_version
    existing.scenario_id = evaluation.linkage.scenario_id
    existing.organization_id = evaluation.linkage.organization_id
    existing.execution_id = evaluation.linkage.execution_id or existing.execution_id
    existing.evaluation_status = evaluation.execution_status.state
    existing.evaluation_record = evaluation.to_dict()
    existing.summary = _build_summary(
        submission_record=dict(existing.submission_record),
        evaluation_record=existing.evaluation_record,
        proposal_payload=dict(existing.proposal_payload),
        persisted_follow_up=dict(existing.summary.get("follow_up") or {}),
    )

    trip_record.updated_at = datetime.now(UTC)
    db_session.commit()
    db_session.refresh(existing)
    return {
        "proposal_state": _serialize_proposal_state(existing),
        "summary": dict(existing.summary),
    }


def save_workspace_proposal_follow_up(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    status: str,
    summary: str,
    title: str | None,
    notes: list[str],
    selected_alternative: dict[str, Any] | None,
    requested_exception: dict[str, Any] | None,
) -> dict[str, Any]:
    trip_record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    if trip_record.mode != "business":
        raise ValueError("Only business trips can persist proposal lifecycle state.")

    existing = _get_latest_proposal_state(db_session, trip_id=trip_id, user_id=user.user_id)
    if existing is None:
        raise WorkspaceProposalNotFoundError(
            "Proposal follow-up cannot be stored before a proposal submission exists."
        )

    existing_follow_up = _resolved_follow_up_payload(existing)
    proposal_payload = dict(existing.proposal_payload)
    serialized_exception: dict[str, Any] | None = None
    if requested_exception is not None:
        serialized_exception = ExceptionRequest(**requested_exception).to_dict()
        proposal_payload["requested_exception"] = serialized_exception

    manual_follow_up = {
        "manual": True,
        "status": status,
        "path": _resolve_manual_follow_up_path(
            existing_follow_up=existing_follow_up,
            status=status,
        ),
        "title": title or existing.summary.get("follow_up_title") or "Workspace follow-up updated",
        "summary": summary,
        "notes": list(notes),
        "selected_alternative": dict(selected_alternative) if selected_alternative else None,
        "updated_at": _now_iso(),
    }
    if serialized_exception is not None:
        manual_follow_up["requested_exception"] = serialized_exception

    existing.proposal_payload = proposal_payload
    existing.summary = _build_summary(
        submission_record=dict(existing.submission_record),
        evaluation_record=dict(existing.evaluation_record),
        proposal_payload=proposal_payload,
        persisted_follow_up=manual_follow_up,
    )

    trip_record.updated_at = datetime.now(UTC)
    db_session.commit()
    db_session.refresh(existing)
    return {
        "proposal_state": _serialize_proposal_state(existing),
        "summary": dict(existing.summary),
    }
