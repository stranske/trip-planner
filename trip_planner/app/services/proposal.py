from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from trip_planner.app.services.auth import AuthenticatedUser
from trip_planner.business import ExceptionRequest, TripPlanProposal
from trip_planner.integrations.tpp import (
    BaseTPPIntegrationClient,
    EvaluationResultIngestionError,
    HTTPTPPIntegrationClient,
    TPPCorrelationId,
    TPPConfigurationError,
    TPPContractError,
    TPPErrorRecord,
    TPPEvaluationResultIngestionService,
    TPPExecutionStatus,
    TPPProposalSubmissionService,
    TPPRequestEnvelope,
    TPPResponseEnvelope,
    TPPRetryMetadata,
    TPPTransportError,
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


_TPP_EXPENSE_CATEGORY_MAP = {
    "air": "airfare",
    "airfare": "airfare",
    "flight": "airfare",
    "flights": "airfare",
    "hotel": "lodging",
    "lodging": "lodging",
    "ground": "ground_transport",
    "ground_transport": "ground_transport",
    "rental_car": "ground_transport",
    "car": "ground_transport",
    "meals": "meals",
    "meal": "meals",
    "food": "meals",
    "conference": "conference_fees",
    "conference_fees": "conference_fees",
}


def _tpp_expense_category(category: str) -> str:
    normalized = category.strip().lower().replace("-", "_")
    return _TPP_EXPENSE_CATEGORY_MAP.get(normalized, "other")


def _required_tpp_trip_date(value: str | None, field_name: str) -> str:
    if not value:
        raise ValueError(f"Live TPP proposal submission requires trip {field_name}.")
    return value


def _aggregate_tpp_costs(proposal: TripPlanProposal) -> dict[str, float]:
    costs: dict[str, float] = {}
    for category, amount in proposal.cost_summary.category_estimates.items():
        tpp_category = _tpp_expense_category(category)
        costs[tpp_category] = costs.get(tpp_category, 0.0) + float(amount)
    for option in proposal.selected_options:
        if option.estimated_cost is None or option.estimated_cost.typical_amount is None:
            continue
        tpp_category = _tpp_expense_category(option.category)
        costs.setdefault(tpp_category, float(option.estimated_cost.typical_amount))
    return costs


def _tpp_trip_plan_payload(
    record: PersistedTrip,
    *,
    user: AuthenticatedUser,
    proposal: TripPlanProposal,
) -> dict[str, Any]:
    primary_regions = [region for region in record.primary_regions if region]
    if not primary_regions:
        raise ValueError("Live TPP proposal submission requires at least one primary region.")
    costs = _aggregate_tpp_costs(proposal)
    selected_providers = {
        _tpp_expense_category(option.category): option.vendor
        for option in proposal.selected_options
        if option.vendor
    }
    comparable_hotels = [
        comparable.estimated_cost.typical_amount
        for comparable in proposal.comparables
        if _tpp_expense_category(comparable.category) == "lodging"
        and comparable.estimated_cost.typical_amount is not None
    ]
    airfare_cost = costs.get("airfare")
    lodging_cost = costs.get("lodging")
    transportation_mode = "air" if airfare_cost is not None else "mixed"

    return {
        "trip_id": proposal.trip_id,
        "traveler_name": user.display_name,
        "traveler_role": proposal.traveler_context.employee_type,
        "department": proposal.constraint_set_id,
        "destination": ", ".join(primary_regions),
        "origin_city": proposal.traveler_context.home_airport,
        "destination_city": primary_regions[0],
        "departure_date": _required_tpp_trip_date(record.start_date, "start_date"),
        "return_date": _required_tpp_trip_date(record.end_date, "end_date"),
        "purpose": record.summary or record.title,
        "transportation_mode": transportation_mode,
        "expected_costs": costs,
        "funding_source": proposal.constraint_set_id,
        "estimated_cost": proposal.cost_summary.total_estimated_cost,
        "status": "submitted",
        "expense_breakdown": costs,
        "selected_fare": airfare_cost,
        "flight_cost": airfare_cost,
        "comparable_hotels": comparable_hotels or ([lodging_cost] if lodging_cost else None),
        "selected_providers": selected_providers,
        "validation_results": [],
        "approval_history": [],
        "exception_requests": [],
    }


class _PassiveTPPClient(BaseTPPIntegrationClient):
    def __init__(self, response: TPPResponseEnvelope) -> None:
        self.response = response

    def execute(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        return self.response


def _resolve_submission_response(
    request: TPPRequestEnvelope,
    response_payload: dict[str, Any] | None,
    *,
    proposal_version: str,
    trip_record: PersistedTrip,
    user: AuthenticatedUser,
    proposal: TripPlanProposal,
) -> TPPResponseEnvelope:
    if response_payload is not None:
        return TPPResponseEnvelope.from_dict(response_payload)
    live_request = request
    live_payload = dict(request.payload)
    if not live_payload.get("proposal_version"):
        live_payload["proposal_version"] = proposal_version
    if not isinstance(live_payload.get("trip_plan"), dict):
        live_payload["trip_plan"] = _tpp_trip_plan_payload(
            trip_record,
            user=user,
            proposal=proposal,
        )
    if live_payload != request.payload:
        live_request = TPPRequestEnvelope(
            operation=request.operation,
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            payload=live_payload,
            transport_pattern=request.transport_pattern,
            organization_id=request.organization_id,
            trip_id=request.trip_id,
            proposal_id=request.proposal_id,
            submitted_at=request.submitted_at,
            metadata=dict(request.metadata),
        )
    return HTTPTPPIntegrationClient().submit_proposal(live_request)


def _transport_error_details(error: Exception, *, source: str) -> dict[str, str]:
    details: dict[str, str] = {"source": source}
    error_code = getattr(error, "error_code", None)
    status_code = getattr(error, "status_code", None)
    if error_code:
        details["error_code"] = str(error_code)
    if status_code is not None:
        details["status_code"] = str(status_code)
    return details


def _should_persist_stored_policy_fallback(error: TPPTransportError) -> bool:
    return error.error_code in {"breaker_open", "timeout"}


def _fallback_submission_response(
    *,
    request: TPPRequestEnvelope,
    error: TPPTransportError,
) -> TPPResponseEnvelope:
    if error.error_code == "breaker_open":
        summary = (
            "Live TPP transport circuit breaker is open; the workspace is using stored-policy "
            "posture until the next retry window."
        )
    else:
        summary = (
            "Live TPP transport timed out; the workspace is using stored-policy posture until "
            "the next retry."
        )
    return TPPResponseEnvelope(
        operation=request.operation,
        request_id=request.request_id,
        correlation_id=request.correlation_id,
        transport_pattern="deferred",
        execution_status=TPPExecutionStatus(
            state="retry_scheduled",
            terminal=False,
            summary=summary,
            updated_at=_now_iso(),
        ),
        result_payload={},
        error=TPPErrorRecord(
            code=error.error_code,
            message=str(error) or summary,
            category="transport",
            retryable=True,
            details=_transport_error_details(error, source="workspace_proposal_submission"),
        ),
        retry=TPPRetryMetadata(
            attempt=1,
            max_attempts=5,
            retryable=True,
            reason=summary,
        ),
        received_at=_now_iso(),
    )


def _fallback_evaluation_record(
    *,
    request: TPPRequestEnvelope,
    error: TPPTransportError,
    existing: PersistedProposalState,
) -> dict[str, Any]:
    if error.error_code == "breaker_open":
        summary = (
            "Live TPP transport circuit breaker is open; the workspace is using stored-policy "
            "posture until the next retry window."
        )
    else:
        summary = (
            "Live TPP transport timed out; the workspace is using stored-policy posture until "
            "the next retry."
        )
    return {
        "linkage": {
            "trip_id": existing.trip_id,
            "proposal_id": existing.proposal_id,
            "proposal_version": existing.proposal_version,
            "scenario_id": existing.scenario_id,
            "execution_id": existing.execution_id,
            "organization_id": existing.organization_id,
        },
        "request_id": request.request_id,
        "correlation_id": request.correlation_id.value,
        "transport_pattern": "deferred",
        "execution_status": TPPExecutionStatus(
            state="retry_scheduled",
            terminal=False,
            summary=summary,
            updated_at=_now_iso(),
        ).to_dict(),
        "request_payload": dict(request.payload),
        "response_payload": {},
        "retry": TPPRetryMetadata(
            attempt=1,
            max_attempts=5,
            retryable=True,
            reason=summary,
        ).to_dict(),
        "error": TPPErrorRecord(
            code=error.error_code,
            message=str(error) or summary,
            category="transport",
            retryable=True,
            details=_transport_error_details(error, source="workspace_proposal_evaluation"),
        ).to_dict(),
        "received_at": _now_iso(),
    }


def _normalize_evaluation_request(
    request: TPPRequestEnvelope,
    *,
    existing: PersistedProposalState,
    proposal_version: str,
) -> TPPRequestEnvelope:
    live_payload = dict(request.payload)
    live_payload["proposal_version"] = existing.proposal_version or proposal_version
    if existing.execution_id:
        live_payload["execution_id"] = existing.execution_id

    organization_id = existing.organization_id or request.organization_id
    if (
        live_payload != request.payload
        or request.trip_id != existing.trip_id
        or request.proposal_id != existing.proposal_id
        or request.organization_id != organization_id
    ):
        return TPPRequestEnvelope(
            operation=request.operation,
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            payload=live_payload,
            transport_pattern=request.transport_pattern,
            organization_id=organization_id,
            trip_id=existing.trip_id,
            proposal_id=existing.proposal_id,
            submitted_at=request.submitted_at,
            metadata=dict(request.metadata),
        )
    return request


def _resolve_evaluation_response(
    request: TPPRequestEnvelope,
    response_payload: dict[str, Any] | None,
    *,
    existing: PersistedProposalState,
    proposal_version: str,
) -> TPPResponseEnvelope:
    if response_payload is not None:
        return TPPResponseEnvelope.from_dict(response_payload)
    live_request = _normalize_evaluation_request(
        request,
        existing=existing,
        proposal_version=proposal_version,
    )
    return HTTPTPPIntegrationClient().fetch_evaluation_result(live_request)


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
            "selected_alternative": alternative if isinstance(alternative, dict) else None,
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
    follow_up["selected_alternative"] = follow_up.get("selected_alternative")
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
    submission_requires_polling = (
        execution_status.get("terminal") is False or evaluation_transport.get("terminal") is False
    )
    return {
        "trip_id": proposal_payload.get("trip_id"),
        "proposal_id": proposal_payload.get("proposal_id"),
        "proposal_version": submission_record.get("linkage", {}).get("proposal_version"),
        "submission_status": execution_status.get("state"),
        "submission_summary": execution_status.get("summary"),
        "submission_requires_polling": submission_requires_polling,
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
        "submission_error": submission_record.get("error"),
        "submission_retry": submission_record.get("retry"),
        "evaluation_error": evaluation_record.get("error"),
        "evaluation_retry": evaluation_record.get("retry"),
    }


_FOLLOW_UP_PATH_BY_STATUS: dict[str, str] = {
    "awaiting_evaluation": "pending",
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


def _resolve_manual_follow_up_path(*, existing_follow_up: dict[str, Any], status: str) -> str:
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


def _make_runtime_request(
    *,
    operation: str,
    record: PersistedProposalState,
    payload: dict[str, Any],
) -> TPPRequestEnvelope:
    submission_record = dict(record.submission_record)
    correlation_id = submission_record.get("correlation_id")
    if not correlation_id:
        raise ValueError("Persisted proposal state is missing correlation metadata.")
    return TPPRequestEnvelope(
        operation=operation,
        request_id=f"{operation}:{uuid4().hex}",
        correlation_id=TPPCorrelationId.from_value(str(correlation_id)),
        payload=payload,
        transport_pattern=str(submission_record.get("transport_pattern") or "async"),
        organization_id=record.organization_id,
        trip_id=record.trip_id,
        proposal_id=record.proposal_id,
        submitted_at=_now_iso(),
        metadata={"source": "workspace_proposal_refresh"},
    )


def _update_submission_record_from_poll(
    *,
    record: PersistedProposalState,
    request: TPPRequestEnvelope,
    response: TPPResponseEnvelope,
) -> None:
    submission_record = dict(record.submission_record)
    response_payload = dict(response.result_payload or {})
    execution_id = response_payload.get("execution_id") or record.execution_id

    submission_record["last_poll_request_id"] = request.request_id
    submission_record["last_poll_request_payload"] = dict(request.payload)
    submission_record["transport_pattern"] = response.transport_pattern
    submission_record["execution_status"] = response.execution_status.to_dict()
    submission_record["last_poll_response_payload"] = response_payload
    submission_record["last_poll_received_at"] = response.received_at
    submission_record["received_at"] = response.received_at
    submission_record["status_endpoint"] = response.status_endpoint or submission_record.get(
        "status_endpoint"
    )
    submission_record["last_poll_status_endpoint"] = (
        response.status_endpoint or submission_record.get("last_poll_status_endpoint")
    )
    submission_record["execution_id"] = execution_id
    if response_payload.get("queue_state") is not None:
        submission_record["queue_state"] = response_payload["queue_state"]
    if response.retry is not None:
        submission_record["retry"] = response.retry.to_dict()
    else:
        submission_record.pop("retry", None)
    if response.error is not None:
        submission_record["error"] = response.error.to_dict()
    else:
        submission_record.pop("error", None)

    record.execution_id = str(execution_id) if execution_id else None
    record.submission_status = response.execution_status.state
    record.submission_record = submission_record


def _persist_evaluation_refresh_failure(
    *,
    record: PersistedProposalState,
    request: TPPRequestEnvelope,
    error: Exception,
) -> None:
    details = _transport_error_details(error, source="workspace_proposal_refresh")

    if isinstance(error, TPPTransportError):
        category = "transport"
    elif isinstance(error, (EvaluationResultIngestionError, ValueError)):
        category = "contract"
    else:
        category = "application"

    record.evaluation_status = "retry_scheduled"
    record.evaluation_record = {
        "linkage": {
            "trip_id": record.trip_id,
            "proposal_id": record.proposal_id,
            "proposal_version": record.proposal_version,
            "scenario_id": record.scenario_id,
            "execution_id": record.execution_id,
            "organization_id": record.organization_id,
        },
        "request_id": request.request_id,
        "correlation_id": request.correlation_id.value,
        "transport_pattern": request.transport_pattern,
        "execution_status": TPPExecutionStatus(
            state="retry_scheduled",
            terminal=False,
            summary=(
                "Policy execution finished, but loading the evaluation result failed. "
                "Refresh live status to retry."
            ),
            updated_at=_now_iso(),
        ).to_dict(),
        "request_payload": dict(request.payload),
        "response_payload": {},
        "retry": TPPRetryMetadata(
            attempt=1,
            max_attempts=5,
            retryable=True,
            reason="Retry the live workspace refresh after evaluation retrieval fails.",
        ).to_dict(),
        "error": TPPErrorRecord(
            code="evaluation_refresh_failed",
            message=str(error) or "Live evaluation refresh failed.",
            category=category,
            retryable=True,
            details=details,
        ).to_dict(),
        "received_at": _now_iso(),
    }


def _persist_submission_refresh_failure(
    *,
    record: PersistedProposalState,
    request: TPPRequestEnvelope,
    error: Exception,
) -> None:
    details = _transport_error_details(error, source="workspace_proposal_refresh")

    if isinstance(error, TPPConfigurationError):
        category = "configuration"
        state = "failed"
        retryable = True
        terminal = True
        summary = "Workspace refresh needs live TPP configuration before status can be updated."
        code = "submission_refresh_configuration_failed"
    elif isinstance(error, TPPContractError):
        category = "contract"
        state = "failed"
        retryable = False
        terminal = True
        summary = "Workspace refresh received an invalid live TPP status payload."
        code = "submission_refresh_contract_failed"
    elif isinstance(error, TPPTransportError):
        category = "transport"
        state = "retry_scheduled"
        retryable = True
        terminal = False
        summary = "Workspace refresh could not reach the live proposal status endpoint. Retry the status check."
        code = f"submission_refresh_{error.error_code}"
    else:
        category = "application"
        state = "failed"
        retryable = False
        terminal = True
        summary = "Workspace refresh could not reconcile the stored proposal status."
        code = "submission_refresh_failed"

    submission_record = dict(record.submission_record)
    previous_execution_status = dict(submission_record.get("execution_status") or {})
    if previous_execution_status:
        submission_record["last_known_execution_status"] = previous_execution_status

    submission_record["last_poll_request_id"] = request.request_id
    submission_record["last_poll_request_payload"] = dict(request.payload)
    submission_record["last_poll_error_at"] = _now_iso()
    submission_record["execution_status"] = TPPExecutionStatus(
        state=state,
        terminal=terminal,
        summary=summary,
        external_status=str(previous_execution_status.get("external_status") or ""),
        updated_at=_now_iso(),
    ).to_dict()
    submission_record["error"] = TPPErrorRecord(
        code=code,
        message=str(error) or summary,
        category=category,
        retryable=retryable,
        details=details,
    ).to_dict()
    if retryable:
        previous_retry = dict(submission_record.get("retry") or {})
        next_attempt = int(previous_retry.get("attempt") or 0) + 1
        max_attempts = int(previous_retry.get("max_attempts") or 5)
        submission_record["retry"] = TPPRetryMetadata(
            attempt=min(next_attempt, max_attempts),
            max_attempts=max_attempts,
            retryable=True,
            reason=summary,
        ).to_dict()
    else:
        submission_record.pop("retry", None)

    record.submission_status = state
    record.submission_record = submission_record


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
    response_payload: dict[str, Any] | None,
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
    try:
        response = _resolve_submission_response(
            request,
            response_payload,
            proposal_version=proposal_version,
            trip_record=trip_record,
            user=user,
            proposal=proposal,
        )
    except TPPTransportError as error:
        if not _should_persist_stored_policy_fallback(error):
            raise
        response = _fallback_submission_response(request=request, error=error)
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
    response_payload: dict[str, Any] | None,
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

    request = _normalize_evaluation_request(
        TPPRequestEnvelope.from_dict(request_payload),
        existing=existing,
        proposal_version=proposal_version,
    )
    try:
        response = _resolve_evaluation_response(
            request,
            response_payload,
            existing=existing,
            proposal_version=proposal_version,
        )
        evaluation = TPPEvaluationResultIngestionService(
            _PassiveTPPClient(response)
        ).fetch_evaluation_result(
            request,
            proposal_version=proposal_version,
            scenario_id=scenario_id,
        )
    except TPPTransportError as error:
        if not _should_persist_stored_policy_fallback(error):
            raise
        existing.evaluation_status = "retry_scheduled"
        existing.evaluation_record = _fallback_evaluation_record(
            request=request,
            error=error,
            existing=existing,
        )
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
    if (
        existing.scenario_id is not None
        and evaluation.linkage.scenario_id is not None
        and evaluation.linkage.scenario_id != existing.scenario_id
    ):
        raise ValueError("evaluation linkage.scenario_id must match the persisted proposal.")
    if (
        existing.organization_id is not None
        and evaluation.linkage.organization_id is not None
        and evaluation.linkage.organization_id != existing.organization_id
    ):
        raise ValueError("evaluation linkage.organization_id must match the persisted proposal.")

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


def refresh_workspace_proposal_status(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
) -> dict[str, Any]:
    trip_record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    if trip_record.mode != "business":
        raise ValueError("Only business trips can persist proposal lifecycle state.")

    existing = _get_latest_proposal_state(db_session, trip_id=trip_id, user_id=user.user_id)
    if existing is None:
        raise WorkspaceProposalNotFoundError(
            "Proposal status cannot be refreshed before a proposal submission exists."
        )
    if not existing.execution_id:
        raise ValueError("Proposal status cannot be refreshed without an execution_id.")

    poll_request = _make_runtime_request(
        operation="poll_execution_status",
        record=existing,
        payload={
            "proposal_version": existing.proposal_version,
            "execution_id": existing.execution_id,
        },
    )
    try:
        polled_response = HTTPTPPIntegrationClient().poll_execution_status(poll_request)
        _update_submission_record_from_poll(
            record=existing,
            request=poll_request,
            response=polled_response,
        )
        existing.summary = _build_summary(
            submission_record=dict(existing.submission_record),
            evaluation_record=dict(existing.evaluation_record),
            proposal_payload=dict(existing.proposal_payload),
            persisted_follow_up=dict(existing.summary.get("follow_up") or {}),
        )
        trip_record.updated_at = datetime.now(UTC)
        db_session.commit()
        db_session.refresh(existing)
    except (TPPTransportError, ValueError) as error:
        _persist_submission_refresh_failure(
            record=existing,
            request=poll_request,
            error=error,
        )
        existing.summary = _build_summary(
            submission_record=dict(existing.submission_record),
            evaluation_record=dict(existing.evaluation_record),
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

    if polled_response.execution_status.state == "succeeded":
        evaluation_request = _make_runtime_request(
            operation="fetch_evaluation_result",
            record=existing,
            payload={
                "proposal_version": existing.proposal_version,
                "execution_id": existing.execution_id,
            },
        )
        try:
            return save_workspace_proposal_evaluation(
                db_session,
                user=user,
                trip_id=trip_id,
                request_payload=evaluation_request.to_dict(),
                response_payload=None,
                proposal_version=existing.proposal_version,
                scenario_id=existing.scenario_id,
            )
        except (EvaluationResultIngestionError, TPPTransportError, ValueError) as error:
            _persist_evaluation_refresh_failure(
                record=existing,
                request=evaluation_request,
                error=error,
            )
            existing.summary = _build_summary(
                submission_record=dict(existing.submission_record),
                evaluation_record=dict(existing.evaluation_record),
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

    return {
        "proposal_state": _serialize_proposal_state(existing),
        "summary": dict(existing.summary),
    }
