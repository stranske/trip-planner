"""Approval-readiness packaging for policy-facing business trip proposals."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from trip_planner._validators import (
    require_non_empty,
    require_probability,
    require_strings,
)

from .policy_contracts import (
    ApprovalRequirement,
    BookingChannelSummary,
    ComparableOption,
    ExceptionRequest,
    JustificationRecord,
    PolicyEvaluationResult,
    PolicyFailureReason,
    PreferredAlternative,
    SelectedOptionSummary,
    TripPlanProposal,
)
from .profile import BusinessTravelProfile, RequiredPresenceWindow, TravelerContext

APPROVAL_PACKAGE_STATUSES: tuple[str, ...] = (
    "approval_ready",
    "exception_ready",
    "policy_revision_needed",
)
APPROVAL_PACKAGE_POSTURES: tuple[str, ...] = ("compliant_first", "exception_nearest")
APPROVAL_CHECK_STATUSES: tuple[str, ...] = ("ready", "attention", "not_applicable")


@dataclass(slots=True)
class ApprovalReadinessCheck:
    key: str
    label: str
    status: str
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.key, "key")
        require_non_empty(self.label, "label")
        if self.status not in APPROVAL_CHECK_STATUSES:
            raise ValueError(f"status must be one of {APPROVAL_CHECK_STATUSES}")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ApprovalReadyPackage:
    package_id: str
    proposal_id: str
    trip_id: str
    package_status: str
    scenario_posture: str
    traveler_context: TravelerContext
    business_justification: str
    required_presence_windows: list[RequiredPresenceWindow] = field(default_factory=list)
    selected_options: list[SelectedOptionSummary] = field(default_factory=list)
    comparables: list[ComparableOption] = field(default_factory=list)
    justifications: list[JustificationRecord] = field(default_factory=list)
    booking_channel_summaries: list[BookingChannelSummary] = field(default_factory=list)
    approval_requirements: list[ApprovalRequirement] = field(default_factory=list)
    approval_roles: list[str] = field(default_factory=list)
    required_receipt_categories: list[str] = field(default_factory=list)
    justification_fields: list[str] = field(default_factory=list)
    approval_notes: list[str] = field(default_factory=list)
    package_summary: list[str] = field(default_factory=list)
    readiness_checks: list[ApprovalReadinessCheck] = field(default_factory=list)
    failure_reasons: list[PolicyFailureReason] = field(default_factory=list)
    preferred_alternatives: list[PreferredAlternative] = field(default_factory=list)
    exception_guidance: list[str] = field(default_factory=list)
    requested_exception: ExceptionRequest | None = None
    compliance_score: float = 1.0

    def __post_init__(self) -> None:
        require_non_empty(self.package_id, "package_id")
        require_non_empty(self.proposal_id, "proposal_id")
        require_non_empty(self.trip_id, "trip_id")
        if self.package_status not in APPROVAL_PACKAGE_STATUSES:
            raise ValueError(f"package_status must be one of {APPROVAL_PACKAGE_STATUSES}")
        if self.scenario_posture not in APPROVAL_PACKAGE_POSTURES:
            raise ValueError(f"scenario_posture must be one of {APPROVAL_PACKAGE_POSTURES}")
        if not isinstance(self.traveler_context, TravelerContext):
            raise ValueError("traveler_context must be a TravelerContext")
        require_non_empty(self.business_justification, "business_justification")
        if any(
            not isinstance(window, RequiredPresenceWindow)
            for window in self.required_presence_windows
        ):
            raise ValueError(
                "required_presence_windows must contain RequiredPresenceWindow instances"
            )
        if any(not isinstance(item, SelectedOptionSummary) for item in self.selected_options):
            raise ValueError("selected_options must contain SelectedOptionSummary instances")
        if any(not isinstance(item, ComparableOption) for item in self.comparables):
            raise ValueError("comparables must contain ComparableOption instances")
        if any(not isinstance(item, JustificationRecord) for item in self.justifications):
            raise ValueError("justifications must contain JustificationRecord instances")
        if any(
            not isinstance(item, BookingChannelSummary) for item in self.booking_channel_summaries
        ):
            raise ValueError(
                "booking_channel_summaries must contain BookingChannelSummary instances"
            )
        if any(not isinstance(item, ApprovalRequirement) for item in self.approval_requirements):
            raise ValueError("approval_requirements must contain ApprovalRequirement instances")
        if any(not isinstance(item, ApprovalReadinessCheck) for item in self.readiness_checks):
            raise ValueError("readiness_checks must contain ApprovalReadinessCheck instances")
        if any(not isinstance(item, PolicyFailureReason) for item in self.failure_reasons):
            raise ValueError("failure_reasons must contain PolicyFailureReason instances")
        if any(not isinstance(item, PreferredAlternative) for item in self.preferred_alternatives):
            raise ValueError("preferred_alternatives must contain PreferredAlternative instances")
        if self.requested_exception is not None and not isinstance(
            self.requested_exception, ExceptionRequest
        ):
            raise ValueError("requested_exception must be an ExceptionRequest when provided")
        require_strings(self.approval_roles, "approval_roles")
        require_strings(self.required_receipt_categories, "required_receipt_categories")
        require_strings(self.justification_fields, "justification_fields")
        require_strings(self.approval_notes, "approval_notes")
        require_strings(self.package_summary, "package_summary")
        require_strings(self.exception_guidance, "exception_guidance")
        require_probability(self.compliance_score, "compliance_score")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_approval_ready_package(
    profile: BusinessTravelProfile,
    proposal: TripPlanProposal,
    evaluation: PolicyEvaluationResult,
    *,
    package_id: str | None = None,
    scenario_posture: str | None = None,
) -> ApprovalReadyPackage:
    if proposal.proposal_id != evaluation.proposal_id:
        raise ValueError("proposal_id and evaluation_result.proposal_id must match")

    posture = scenario_posture or _default_posture_for_status(evaluation.status)
    if posture not in APPROVAL_PACKAGE_POSTURES:
        raise ValueError(f"scenario_posture must be one of {APPROVAL_PACKAGE_POSTURES}")

    approval_roles = sorted(
        {
            *profile.approval_targets.approval_roles,
            *(requirement.role for requirement in evaluation.approval_requirements),
            *(
                proposal.requested_exception.requested_approval_roles
                if proposal.requested_exception is not None
                else []
            ),
        }
    )

    return ApprovalReadyPackage(
        package_id=package_id or f"approval-{proposal.proposal_id}",
        proposal_id=proposal.proposal_id,
        trip_id=proposal.trip_id,
        package_status=_package_status_for_evaluation(evaluation.status),
        scenario_posture=posture,
        traveler_context=proposal.traveler_context,
        business_justification=profile.trip_purpose.business_justification,
        required_presence_windows=list(profile.trip_purpose.required_presence_windows),
        selected_options=list(proposal.selected_options),
        comparables=list(proposal.comparables),
        justifications=list(proposal.justifications),
        booking_channel_summaries=list(proposal.booking_channel_summaries),
        approval_requirements=list(evaluation.approval_requirements),
        approval_roles=approval_roles,
        required_receipt_categories=list(
            profile.documentation_requirements.required_receipt_categories
        ),
        justification_fields=list(profile.documentation_requirements.justification_fields),
        approval_notes=list(proposal.approval_notes),
        package_summary=_build_package_summary(profile, proposal, evaluation, posture),
        readiness_checks=_build_readiness_checks(profile, proposal, evaluation),
        failure_reasons=list(evaluation.failure_reasons),
        preferred_alternatives=list(evaluation.preferred_alternatives),
        exception_guidance=list(evaluation.exception_guidance),
        requested_exception=proposal.requested_exception,
        compliance_score=evaluation.compliance_score,
    )


def _default_posture_for_status(status: str) -> str:
    if status == "exception_required":
        return "exception_nearest"
    return "compliant_first"


def _package_status_for_evaluation(status: str) -> str:
    if status == "compliant":
        return "approval_ready"
    if status == "exception_required":
        return "exception_ready"
    return "policy_revision_needed"


def _build_package_summary(
    profile: BusinessTravelProfile,
    proposal: TripPlanProposal,
    evaluation: PolicyEvaluationResult,
    posture: str,
) -> list[str]:
    summary = [
        f"Business justification: {profile.trip_purpose.business_justification}",
        f"Package posture: {posture.replace('_', ' ')}",
        f"Policy status: {evaluation.status.replace('_', ' ')}",
        f"Selected option categories: {', '.join(option.category for option in proposal.selected_options)}",
    ]
    if evaluation.approval_requirements:
        summary.append(
            "Approval route: "
            + ", ".join(requirement.role for requirement in evaluation.approval_requirements)
        )
    if proposal.requested_exception is not None:
        summary.append(
            f"Exception request: {proposal.requested_exception.exception_type} "
            f"for {proposal.requested_exception.reason}"
        )
    return summary


def _build_readiness_checks(
    profile: BusinessTravelProfile,
    proposal: TripPlanProposal,
    evaluation: PolicyEvaluationResult,
) -> list[ApprovalReadinessCheck]:
    documentation_rules = profile.documentation_requirements
    checks = [
        ApprovalReadinessCheck(
            key="booking_channels",
            label="Booking channels documented",
            status=(
                "ready"
                if (
                    proposal.booking_channel_summaries
                    and all(item.approved for item in proposal.booking_channel_summaries)
                )
                else "attention"
            ),
            notes=(
                [
                    item.rationale or f"{item.category} uses {item.selected_channel}"
                    for item in proposal.booking_channel_summaries
                ]
                if proposal.booking_channel_summaries
                else ["No booking channels documented"]
            ),
        ),
        ApprovalReadinessCheck(
            key="comparables",
            label="Comparables attached when required",
            status=(
                "ready"
                if (not documentation_rules.comparable_capture_required or proposal.comparables)
                else "attention"
            ),
            notes=[
                (
                    f"{len(proposal.comparables)} comparable option(s) attached"
                    if proposal.comparables
                    else "No comparable options attached"
                )
            ],
        ),
        ApprovalReadinessCheck(
            key="justifications",
            label="Justifications captured",
            status="ready" if proposal.justifications else "attention",
            notes=(
                list(documentation_rules.justification_fields)
                if documentation_rules.justification_fields
                else ["No additional justification fields required by profile"]
            ),
        ),
        ApprovalReadinessCheck(
            key="approval_path",
            label="Approval path defined",
            status=(
                "ready"
                if (
                    evaluation.approval_requirements
                    or profile.approval_targets.approval_roles
                    or proposal.requested_exception is not None
                )
                else "not_applicable"
            ),
            notes=(
                [requirement.reason for requirement in evaluation.approval_requirements]
                or ["No explicit approval routing required"]
            ),
        ),
        ApprovalReadinessCheck(
            key="policy_posture",
            label="Policy posture captured",
            status="ready",
            notes=(
                list(evaluation.notes)
                if evaluation.notes
                else [f"Compliance score {evaluation.compliance_score:.0%}"]
            ),
        ),
    ]
    if proposal.requested_exception is not None or evaluation.status == "exception_required":
        checks.append(
            ApprovalReadinessCheck(
                key="exception_packet",
                label="Exception packet guidance attached",
                status="ready" if evaluation.exception_guidance else "attention",
                notes=(
                    list(evaluation.exception_guidance)
                    if evaluation.exception_guidance
                    else ["No exception guidance attached yet"]
                ),
            )
        )
    return checks
