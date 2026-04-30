from __future__ import annotations
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from trip_planner.app.services.auth import AuthenticatedUser
from trip_planner.business import (
    ApprovalRequirement,
    PolicyConstraintSet,
    PolicyEvaluationResult,
    PolicyFailureReason,
    ProposalCostSummary,
    SelectedOptionSummary,
    TravelerContext,
    TripPlanProposal,
)
from trip_planner.integrations.tpp import (
    BaseTPPIntegrationClient,
    HTTPTPPIntegrationClient,
    OrganizationContextSnapshot,
    PolicyConstraintImport,
    PolicyFreshness,
    TPPPolicySyncService,
    TPPRequestEnvelope,
    TPPResponseEnvelope,
)
from trip_planner.persistence.models.policy import PersistedPolicyState
from trip_planner.persistence.models.trip import PersistedTrip


class WorkspacePolicyNotFoundError(ValueError):
    """Raised when workspace policy state or trip ownership is missing."""


def _isoformat(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


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
        raise WorkspacePolicyNotFoundError(f"Trip '{trip_id}' was not found.")
    return record


def _get_latest_policy_state(
    db_session: Session,
    *,
    trip_id: str,
    user_id: str,
) -> PersistedPolicyState | None:
    return db_session.scalar(
        select(PersistedPolicyState)
        .where(PersistedPolicyState.trip_id == trip_id)
        .where(PersistedPolicyState.user_id == user_id)
        .order_by(PersistedPolicyState.updated_at.desc())
    )


def _required_tpp_trip_date(value: str | None, field_name: str) -> str:
    if not value:
        raise ValueError(f"Live TPP policy sync requires trip {field_name}.")
    return value


def _tpp_trip_plan_payload(record: PersistedTrip, *, user: AuthenticatedUser) -> dict[str, Any]:
    primary_regions = [region for region in record.primary_regions if region]
    if not primary_regions:
        raise ValueError("Live TPP policy sync requires at least one primary region.")
    return {
        "trip_id": record.trip_id,
        "traveler_name": user.display_name,
        "traveler_role": "business traveler",
        "department": _owner_profile_id(record),
        "destination": ", ".join(primary_regions),
        "destination_city": primary_regions[0],
        "departure_date": _required_tpp_trip_date(record.start_date, "start_date"),
        "return_date": _required_tpp_trip_date(record.end_date, "end_date"),
        "purpose": record.summary or record.title,
        "transportation_mode": "mixed",
        "expected_costs": {},
        "estimated_cost": 0,
        "status": "draft",
        "expense_breakdown": {},
        "selected_providers": {},
        "validation_results": [],
        "approval_history": [],
        "exception_requests": [],
    }


class _PassiveTPPClient(BaseTPPIntegrationClient):
    def __init__(self, response: TPPResponseEnvelope) -> None:
        self.response = response

    def execute(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        return self.response


def _resolve_policy_response(
    request: TPPRequestEnvelope,
    response_payload: dict[str, Any] | None,
    *,
    trip_plan_payload: dict[str, Any],
) -> TPPResponseEnvelope:
    if response_payload is not None:
        return TPPResponseEnvelope.from_dict(response_payload)
    live_request = request
    if not isinstance(request.payload.get("trip_plan"), dict):
        live_request = TPPRequestEnvelope(
            operation=request.operation,
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            payload={**request.payload, "trip_plan": trip_plan_payload},
            transport_pattern=request.transport_pattern,
            organization_id=request.organization_id,
            trip_id=request.trip_id,
            proposal_id=request.proposal_id,
            submitted_at=request.submitted_at,
            metadata=dict(request.metadata),
        )
    return HTTPTPPIntegrationClient().fetch_policy_constraints(live_request)


def _is_effectively_stale(imported: PolicyConstraintImport) -> bool:
    return imported.freshness.status != "current" or imported.freshness.invalidated_at is not None


def _summarize_policy_import(imported: PolicyConstraintImport) -> dict[str, Any]:
    constraint_set = imported.constraint_set
    org = imported.organization_context
    freshness = imported.freshness
    stale = _is_effectively_stale(imported)
    return {
        "policy_id": constraint_set.policy_id,
        "organization_id": constraint_set.organization_id,
        "policy_version": constraint_set.policy_version,
        "sync_status": freshness.status,
        "is_stale": stale,
        "required_booking_channels": list(constraint_set.required_booking_channels),
        "approval_triggers": list(org.approval_triggers),
        "documentation_rules": list(constraint_set.documentation_rules),
        "allowed_exception_types": list(constraint_set.allowed_exception_types),
        "fresh_until": freshness.fresh_until,
        "captured_at": freshness.captured_at,
    }


def _proposal_from_import(
    record: PersistedTrip, imported: PolicyConstraintImport
) -> TripPlanProposal:
    notes = [
        f"Imported policy {imported.constraint_set.policy_id} v{imported.constraint_set.policy_version}.",
        (
            "Final proposal submission remains out of scope for this stored-policy slice; "
            "workspace approval-readiness is advisory until submission work lands."
        ),
    ]
    if imported.constraint_set.documentation_rules:
        notes.append(
            "Required documentation: " + ", ".join(imported.constraint_set.documentation_rules)
        )
    return TripPlanProposal(
        proposal_id=f"proposal-preview:{record.trip_id}",
        trip_id=record.trip_id,
        mode="business",
        traveler_context=TravelerContext(
            employee_type="employee",
            traveler_experience="occasional",
            home_airport="policy-import",
            loyalty_programs=[],
            mobility_or_access_needs=[],
        ),
        selected_options=[
            SelectedOptionSummary(
                category="policy_constraints",
                option_id=f"policy-preview:{record.trip_id}",
                label="Imported policy constraint set",
                vendor=imported.organization_id,
                booking_channel=(
                    imported.constraint_set.required_booking_channels[0]
                    if imported.constraint_set.required_booking_channels
                    else "policy-sync"
                ),
                estimated_cost=None,
                justification_refs=[f"policy-state:{record.trip_id}"],
            )
        ],
        cost_summary=ProposalCostSummary(
            currency="USD",
            total_estimated_cost=0.0,
            category_estimates={},
            notes=["Cost summary not available until proposal submission wiring lands."],
        ),
        approval_notes=notes,
        constraint_set_id=imported.constraint_set.policy_id,
    )


def _policy_evaluation_from_import(
    record: PersistedTrip,
    imported: PolicyConstraintImport,
) -> PolicyEvaluationResult:
    approval_requirements = [
        ApprovalRequirement(role="manager", reason=f"Review trigger: {trigger}", mandatory=True)
        for trigger in imported.organization_context.approval_triggers
    ]
    failure_reasons: list[PolicyFailureReason] = []
    notes = [
        f"Imported {imported.constraint_set.policy_id} for organization {imported.organization_id}.",
        "Constraint storage is local to planning; final compliance decisions remain external.",
    ]
    compliance_score = 1.0
    status = "compliant"

    if _is_effectively_stale(imported):
        status = "non_compliant"
        compliance_score = 0.35
        failure_reasons.append(
            PolicyFailureReason(
                code="stale_policy_snapshot",
                message="Stored policy inputs are stale or invalidated and should be refreshed before submission.",
                severity="blocking",
                related_category="policy_sync",
            )
        )
    elif approval_requirements:
        compliance_score = 0.82
        notes.append(
            "Approval-readiness remains active because the imported policy defines approval triggers."
        )

    if not record.start_date or not record.end_date:
        compliance_score = min(compliance_score, 0.65)
        failure_reasons.append(
            PolicyFailureReason(
                code="trip_window_incomplete",
                message="Trip dates should be finalized before the approval packet is treated as complete.",
                severity="warning",
                related_category="trip_frame",
            )
        )
    if not record.primary_regions:
        compliance_score = min(compliance_score, 0.65)
        failure_reasons.append(
            PolicyFailureReason(
                code="trip_region_missing",
                message="Primary travel regions are missing from the persisted trip frame.",
                severity="warning",
                related_category="trip_frame",
            )
        )

    if imported.constraint_set.required_booking_channels:
        notes.append(
            "Approved booking channels: "
            + ", ".join(imported.constraint_set.required_booking_channels)
        )
    if imported.constraint_set.documentation_rules:
        notes.append(
            "Documentation rules: " + ", ".join(imported.constraint_set.documentation_rules)
        )

    return PolicyEvaluationResult(
        evaluation_id=f"policy-eval:{record.trip_id}:{imported.constraint_set.policy_id}",
        proposal_id=f"proposal-preview:{record.trip_id}",
        status=status,
        approval_requirements=approval_requirements,
        failure_reasons=failure_reasons,
        preferred_alternatives=[],
        exception_guidance=(
            ["Refresh the policy import before preparing a final approval packet."]
            if _is_effectively_stale(imported)
            else [
                "Use the stored constraint set as planning guidance until proposal submission is wired."
            ]
        ),
        notes=notes,
        compliance_score=compliance_score,
    )


def _normalize_json_object(payload: object) -> dict[str, Any]:
    if isinstance(payload, dict):
        return dict(payload)
    return {}


def _normalize_string_list(payload: object) -> list[str]:
    if not isinstance(payload, list):
        return []
    return [value for value in payload if isinstance(value, str) and value]


def _normalize_constraint_set_payload(record: PersistedPolicyState) -> dict[str, Any]:
    constraint_set = _normalize_json_object(record.constraint_set)
    return {
        "policy_id": str(constraint_set.get("policy_id") or record.policy_id),
        "organization_id": str(constraint_set.get("organization_id") or record.organization_id),
        "policy_version": str(constraint_set.get("policy_version") or record.policy_version),
        "required_booking_channels": _normalize_string_list(
            constraint_set.get("required_booking_channels")
        ),
        "airfare_rules": _normalize_json_object(constraint_set.get("airfare_rules")),
        "lodging_rules": _normalize_json_object(constraint_set.get("lodging_rules")),
        "ground_transport_rules": _normalize_json_object(
            constraint_set.get("ground_transport_rules")
        ),
        "meal_rules": _normalize_json_object(constraint_set.get("meal_rules")),
        "approval_rules": _normalize_string_list(constraint_set.get("approval_rules")),
        "documentation_rules": _normalize_string_list(constraint_set.get("documentation_rules")),
        "allowed_exception_types": _normalize_string_list(
            constraint_set.get("allowed_exception_types")
        ),
    }


def _normalize_organization_context_payload(record: PersistedPolicyState) -> dict[str, Any]:
    organization_context = _normalize_json_object(record.organization_context)
    comparable_requirements_payload = organization_context.get("comparable_requirements")
    comparable_requirements: dict[str, int] = {}
    if isinstance(comparable_requirements_payload, dict):
        for key, value in comparable_requirements_payload.items():
            if isinstance(key, str) and key and isinstance(value, int):
                comparable_requirements[key] = value
    return {
        "organization_id": str(
            organization_context.get("organization_id") or record.organization_id
        ),
        "approved_channels": _normalize_string_list(organization_context.get("approved_channels")),
        "comparable_requirements": comparable_requirements,
        "documentation_rules": _normalize_string_list(
            organization_context.get("documentation_rules")
        ),
        "approval_triggers": _normalize_string_list(organization_context.get("approval_triggers")),
        "comfort_preferences": _normalize_json_object(
            organization_context.get("comfort_preferences")
        ),
        "class_of_service_limits": _normalize_json_object(
            organization_context.get("class_of_service_limits")
        ),
        "metadata": _normalize_json_object(organization_context.get("metadata")),
    }


def _normalize_freshness_payload(record: PersistedPolicyState) -> dict[str, Any]:
    freshness = _normalize_json_object(record.freshness)
    return {
        "snapshot_version": str(freshness.get("snapshot_version") or record.policy_version),
        "captured_at": str(freshness.get("captured_at") or record.imported_at),
        "fresh_until": (
            freshness.get("fresh_until") if isinstance(freshness.get("fresh_until"), str) else None
        ),
        "invalidated_at": (
            freshness.get("invalidated_at")
            if isinstance(freshness.get("invalidated_at"), str)
            else None
        ),
        "invalidation_reason": (
            freshness.get("invalidation_reason")
            if isinstance(freshness.get("invalidation_reason"), str)
            else None
        ),
        "status": str(freshness.get("status") or record.sync_status or "current"),
    }


def _serialize_policy_state(record: PersistedPolicyState) -> dict[str, Any]:
    return {
        "policy_state_id": record.policy_state_id,
        "trip_id": record.trip_id,
        "owner_profile_id": record.owner_profile_id,
        "source_kind": record.source_kind,
        "source_request_id": record.source_request_id,
        "source_correlation_id": record.source_correlation_id,
        "policy_id": record.policy_id,
        "organization_id": record.organization_id,
        "policy_version": record.policy_version,
        "sync_status": record.sync_status,
        "imported_at": record.imported_at,
        "constraint_set": _normalize_constraint_set_payload(record),
        "organization_context": _normalize_organization_context_payload(record),
        "freshness": _normalize_freshness_payload(record),
        "raw_payload": _normalize_json_object(record.raw_payload),
        "tags": list(record.tags),
        "notes": list(record.notes),
    }


def _build_workspace_policy_payload(
    *,
    trip_record: PersistedTrip,
    policy_record: PersistedPolicyState,
) -> dict[str, Any]:
    imported = PolicyConstraintImport(
        constraint_set=PolicyConstraintSet(**_normalize_constraint_set_payload(policy_record)),
        organization_context=OrganizationContextSnapshot(
            **_normalize_organization_context_payload(policy_record)
        ),
        freshness=PolicyFreshness(**_normalize_freshness_payload(policy_record)),
        source_request_id=policy_record.source_request_id,
        source_correlation_id=policy_record.source_correlation_id,
        raw_payload=_normalize_json_object(policy_record.raw_payload),
    )
    proposal = _proposal_from_import(trip_record, imported)
    policy_evaluation = _policy_evaluation_from_import(trip_record, imported)
    return {
        "policy_state": _serialize_policy_state(policy_record),
        "proposal": proposal.to_dict(),
        "policy_evaluation": policy_evaluation.to_dict(),
        "summary": _summarize_policy_import(imported),
    }


def get_workspace_policy_payload(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
) -> dict[str, Any]:
    trip_record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    policy_record = _get_latest_policy_state(
        db_session,
        trip_id=trip_id,
        user_id=user.user_id,
    )
    if policy_record is None:
        return {
            "policy_state": None,
            "proposal": None,
            "policy_evaluation": None,
            "summary": {"trip_id": trip_id, "status": "missing"},
        }
    return _build_workspace_policy_payload(
        trip_record=trip_record,
        policy_record=policy_record,
    )


def import_workspace_policy_constraints(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    request_payload: dict[str, Any],
    response_payload: dict[str, Any] | None,
    source_kind: str,
    tags: list[str],
    notes: list[str],
) -> dict[str, Any]:
    trip_record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    if trip_record.mode != "business":
        raise ValueError("Only business trips can import workspace policy constraints.")

    request = TPPRequestEnvelope.from_dict(request_payload)
    response = _resolve_policy_response(
        request,
        response_payload,
        trip_plan_payload=(
            _tpp_trip_plan_payload(trip_record, user=user) if response_payload is None else {}
        ),
    )
    imported = TPPPolicySyncService(_PassiveTPPClient(response)).import_policy_constraints(request)
    imported_at = _isoformat(datetime.now(UTC))
    existing = _get_latest_policy_state(
        db_session,
        trip_id=trip_id,
        user_id=user.user_id,
    )
    policy_state_id = (
        existing.policy_state_id if existing is not None else f"policy-state:{trip_id}"
    )

    record = existing or PersistedPolicyState(
        policy_state_id=policy_state_id,
        trip_id=trip_id,
        user_id=user.user_id,
        owner_profile_id=_owner_profile_id(trip_record),
        source_kind=source_kind,
        source_request_id=imported.source_request_id,
        source_correlation_id=imported.source_correlation_id,
        policy_id=imported.constraint_set.policy_id,
        organization_id=imported.organization_id,
        policy_version=imported.constraint_set.policy_version,
        sync_status=imported.freshness.status,
        imported_at=imported_at,
        constraint_set=imported.constraint_set.to_dict(),
        organization_context=imported.organization_context.to_dict(),
        freshness=imported.freshness.to_dict(),
        raw_payload=imported.raw_payload,
        tags=[],
        notes=[],
    )
    record.owner_profile_id = _owner_profile_id(trip_record)
    record.source_kind = source_kind
    record.source_request_id = imported.source_request_id
    record.source_correlation_id = imported.source_correlation_id
    record.policy_id = imported.constraint_set.policy_id
    record.organization_id = imported.organization_id
    record.policy_version = imported.constraint_set.policy_version
    record.sync_status = imported.freshness.status
    record.imported_at = imported_at
    record.constraint_set = imported.constraint_set.to_dict()
    record.organization_context = imported.organization_context.to_dict()
    record.freshness = imported.freshness.to_dict()
    record.raw_payload = imported.raw_payload
    record.tags = list(dict.fromkeys([*record.tags, *tags]))
    record.notes = list(
        dict.fromkeys(
            [
                *record.notes,
                *notes,
                "Persisted policy storage is limited to imported constraint sets and readiness context.",
                "Proposal submission and final policy evaluation remain separate later workflow stages.",
            ]
        )
    )

    if existing is None:
        db_session.add(record)

    trip_record.policy_state_id = policy_state_id
    trip_record.updated_at = datetime.now(UTC)
    db_session.commit()
    db_session.refresh(record)
    return _build_workspace_policy_payload(
        trip_record=trip_record,
        policy_record=record,
    )
