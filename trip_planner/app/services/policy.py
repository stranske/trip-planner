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


class _PassiveTPPClient:
    def __init__(self, response: TPPResponseEnvelope) -> None:
        self.response = response

    def fetch_policy_constraints(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        return self.response


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


def _proposal_from_import(record: PersistedTrip, imported: PolicyConstraintImport) -> TripPlanProposal:
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
            [
                "Refresh the policy import before preparing a final approval packet."
            ]
            if _is_effectively_stale(imported)
            else [
                "Use the stored constraint set as planning guidance until proposal submission is wired."
            ]
        ),
        notes=notes,
        compliance_score=compliance_score,
    )


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
        "constraint_set": dict(record.constraint_set),
        "organization_context": dict(record.organization_context),
        "freshness": dict(record.freshness),
        "raw_payload": dict(record.raw_payload),
        "tags": list(record.tags),
        "notes": list(record.notes),
    }


def _build_workspace_policy_payload(
    *,
    trip_record: PersistedTrip,
    policy_record: PersistedPolicyState,
) -> dict[str, Any]:
    imported = PolicyConstraintImport(
        constraint_set=PolicyConstraintSet(**policy_record.constraint_set),
        organization_context=OrganizationContextSnapshot(**policy_record.organization_context),
        freshness=PolicyFreshness(**policy_record.freshness),
        source_request_id=policy_record.source_request_id,
        source_correlation_id=policy_record.source_correlation_id,
        raw_payload=dict(policy_record.raw_payload),
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
    response_payload: dict[str, Any],
    source_kind: str,
    tags: list[str],
    notes: list[str],
) -> dict[str, Any]:
    trip_record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    if trip_record.mode != "business":
        raise ValueError("Only business trips can import workspace policy constraints.")

    request = TPPRequestEnvelope.from_dict(request_payload)
    response = TPPResponseEnvelope.from_dict(response_payload)
    imported = TPPPolicySyncService(_PassiveTPPClient(response)).import_policy_constraints(request)
    imported_at = _isoformat(datetime.now(UTC))
    existing = _get_latest_policy_state(
        db_session,
        trip_id=trip_id,
        user_id=user.user_id,
    )
    policy_state_id = existing.policy_state_id if existing is not None else f"policy-state:{trip_id}"

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
