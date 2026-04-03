"""Policy-facing contracts for business-trip proposal exchange."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from trip_planner._validators import (
    require_non_empty,
    require_non_negative,
    require_probability,
    require_string_mapping,
    require_strings,
)
from trip_planner._option_contracts import MoneyRange

from .profile import TravelerContext

POLICY_EVALUATION_STATUSES: tuple[str, ...] = (
    "compliant",
    "non_compliant",
    "exception_required",
)
FAILURE_SEVERITIES: tuple[str, ...] = ("warning", "blocking")


def _require_list_field(payload: dict[str, Any], key: str) -> list[Any]:
    if key not in payload:
        raise KeyError(key)
    value = payload[key]
    if not isinstance(value, list):
        raise ValueError(f"{key} must be provided as a list")
    return list(value)


def _optional_list_field(payload: dict[str, Any], key: str) -> list[Any]:
    if key not in payload:
        return []
    value = payload[key]
    if not isinstance(value, list):
        raise ValueError(f"{key} must be provided as a list")
    return list(value)


@dataclass(slots=True)
class PolicyConstraintSet:
    policy_id: str
    organization_id: str
    policy_version: str
    required_booking_channels: list[str] = field(default_factory=list)
    airfare_rules: dict[str, Any] = field(default_factory=dict)
    lodging_rules: dict[str, Any] = field(default_factory=dict)
    ground_transport_rules: dict[str, Any] = field(default_factory=dict)
    meal_rules: dict[str, Any] = field(default_factory=dict)
    approval_rules: list[str] = field(default_factory=list)
    documentation_rules: list[str] = field(default_factory=list)
    allowed_exception_types: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.policy_id, "policy_id")
        require_non_empty(self.organization_id, "organization_id")
        require_non_empty(self.policy_version, "policy_version")
        require_strings(self.required_booking_channels, "required_booking_channels")
        require_string_mapping(self.airfare_rules, "airfare_rules")
        require_string_mapping(self.lodging_rules, "lodging_rules")
        require_string_mapping(self.ground_transport_rules, "ground_transport_rules")
        require_string_mapping(self.meal_rules, "meal_rules")
        require_strings(self.approval_rules, "approval_rules")
        require_strings(self.documentation_rules, "documentation_rules")
        require_strings(self.allowed_exception_types, "allowed_exception_types")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ProposalCostSummary:
    currency: str = "USD"
    total_estimated_cost: float = 0.0
    category_estimates: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.currency, "currency")
        require_non_negative(self.total_estimated_cost, "total_estimated_cost")
        if any(not isinstance(key, str) or not key for key in self.category_estimates):
            raise ValueError("category_estimates must use non-empty string keys")
        for key, value in self.category_estimates.items():
            require_non_negative(value, f"category_estimates[{key}]")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SelectedOptionSummary:
    category: str
    option_id: str
    label: str
    vendor: str
    booking_channel: str
    estimated_cost: MoneyRange | None = None
    justification_refs: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.category, "category")
        require_non_empty(self.option_id, "option_id")
        require_non_empty(self.label, "label")
        require_non_empty(self.vendor, "vendor")
        require_non_empty(self.booking_channel, "booking_channel")
        if self.estimated_cost is not None and not isinstance(self.estimated_cost, MoneyRange):
            raise ValueError("estimated_cost must be a MoneyRange when provided")
        require_strings(self.justification_refs, "justification_refs")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ComparableOption:
    category: str
    label: str
    vendor: str
    booking_channel: str
    estimated_cost: MoneyRange
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.category, "category")
        require_non_empty(self.label, "label")
        require_non_empty(self.vendor, "vendor")
        require_non_empty(self.booking_channel, "booking_channel")
        if not isinstance(self.estimated_cost, MoneyRange):
            raise ValueError("estimated_cost must be a MoneyRange")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class JustificationRecord:
    category: str
    summary: str
    evidence: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.category, "category")
        require_non_empty(self.summary, "summary")
        require_strings(self.evidence, "evidence")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BookingChannelSummary:
    category: str
    selected_channel: str
    approved: bool
    rationale: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.category, "category")
        require_non_empty(self.selected_channel, "selected_channel")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ExceptionRequest:
    exception_type: str
    reason: str
    requested_approval_roles: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.exception_type, "exception_type")
        require_non_empty(self.reason, "reason")
        require_strings(self.requested_approval_roles, "requested_approval_roles")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TripPlanProposal:
    proposal_id: str
    trip_id: str
    mode: str
    traveler_context: TravelerContext
    selected_options: list[SelectedOptionSummary]
    cost_summary: ProposalCostSummary
    comparables: list[ComparableOption] = field(default_factory=list)
    justifications: list[JustificationRecord] = field(default_factory=list)
    booking_channel_summaries: list[BookingChannelSummary] = field(default_factory=list)
    approval_notes: list[str] = field(default_factory=list)
    requested_exception: ExceptionRequest | None = None
    constraint_set_id: str | None = None

    def __post_init__(self) -> None:
        require_non_empty(self.proposal_id, "proposal_id")
        require_non_empty(self.trip_id, "trip_id")
        if self.mode != "business":
            raise ValueError("TripPlanProposal mode must be 'business'")
        if not isinstance(self.traveler_context, TravelerContext):
            raise ValueError("traveler_context must be a TravelerContext")
        if not self.selected_options:
            raise ValueError("selected_options must contain at least one SelectedOptionSummary")
        if any(not isinstance(item, SelectedOptionSummary) for item in self.selected_options):
            raise ValueError("selected_options must contain SelectedOptionSummary instances")
        if not isinstance(self.cost_summary, ProposalCostSummary):
            raise ValueError("cost_summary must be a ProposalCostSummary")
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
        if self.requested_exception is not None and not isinstance(
            self.requested_exception, ExceptionRequest
        ):
            raise ValueError("requested_exception must be an ExceptionRequest when provided")
        require_strings(self.approval_notes, "approval_notes")
        if self.constraint_set_id is not None and not self.constraint_set_id:
            raise ValueError("constraint_set_id must be non-empty when provided")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TripPlanProposal":
        selected_options = _require_list_field(payload, "selected_options")
        comparables = _optional_list_field(payload, "comparables")
        justifications = _optional_list_field(payload, "justifications")
        booking_channel_summaries = _optional_list_field(payload, "booking_channel_summaries")
        approval_notes = _optional_list_field(payload, "approval_notes")

        return cls(
            proposal_id=payload["proposal_id"],
            trip_id=payload["trip_id"],
            mode=payload["mode"],
            traveler_context=TravelerContext(**payload["traveler_context"]),
            selected_options=[
                SelectedOptionSummary(
                    **{
                        **item,
                        "estimated_cost": (
                            MoneyRange(**item["estimated_cost"])
                            if item.get("estimated_cost")
                            else None
                        ),
                    }
                )
                for item in selected_options
            ],
            cost_summary=ProposalCostSummary(**payload["cost_summary"]),
            comparables=[
                ComparableOption(
                    **{
                        **item,
                        "estimated_cost": MoneyRange(**item["estimated_cost"]),
                    }
                )
                for item in comparables
            ],
            justifications=[JustificationRecord(**item) for item in justifications],
            booking_channel_summaries=[
                BookingChannelSummary(**item) for item in booking_channel_summaries
            ],
            approval_notes=approval_notes,
            requested_exception=(
                ExceptionRequest(**payload["requested_exception"])
                if payload.get("requested_exception")
                else None
            ),
            constraint_set_id=payload.get("constraint_set_id"),
        )


@dataclass(slots=True)
class ApprovalRequirement:
    role: str
    reason: str
    mandatory: bool = True

    def __post_init__(self) -> None:
        require_non_empty(self.role, "role")
        require_non_empty(self.reason, "reason")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PolicyFailureReason:
    code: str
    message: str
    severity: str = "blocking"
    related_category: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.code, "code")
        require_non_empty(self.message, "message")
        if self.severity not in FAILURE_SEVERITIES:
            raise ValueError(f"severity must be one of {FAILURE_SEVERITIES}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PreferredAlternative:
    category: str
    summary: str
    rationale: str
    comparable_ref: str | None = None

    def __post_init__(self) -> None:
        require_non_empty(self.category, "category")
        require_non_empty(self.summary, "summary")
        require_non_empty(self.rationale, "rationale")
        if self.comparable_ref is not None and not self.comparable_ref:
            raise ValueError("comparable_ref must be non-empty when provided")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PolicyEvaluationResult:
    evaluation_id: str
    proposal_id: str
    status: str
    approval_requirements: list[ApprovalRequirement] = field(default_factory=list)
    failure_reasons: list[PolicyFailureReason] = field(default_factory=list)
    preferred_alternatives: list[PreferredAlternative] = field(default_factory=list)
    exception_guidance: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    compliance_score: float = 1.0

    def __post_init__(self) -> None:
        require_non_empty(self.evaluation_id, "evaluation_id")
        require_non_empty(self.proposal_id, "proposal_id")
        if self.status not in POLICY_EVALUATION_STATUSES:
            raise ValueError(f"status must be one of {POLICY_EVALUATION_STATUSES}")
        if any(not isinstance(item, ApprovalRequirement) for item in self.approval_requirements):
            raise ValueError("approval_requirements must contain ApprovalRequirement instances")
        if any(not isinstance(item, PolicyFailureReason) for item in self.failure_reasons):
            raise ValueError("failure_reasons must contain PolicyFailureReason instances")
        if any(not isinstance(item, PreferredAlternative) for item in self.preferred_alternatives):
            raise ValueError("preferred_alternatives must contain PreferredAlternative instances")
        require_strings(self.exception_guidance, "exception_guidance")
        require_strings(self.notes, "notes")
        require_probability(self.compliance_score, "compliance_score")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PolicyEvaluationResult":
        approval_requirements = _optional_list_field(payload, "approval_requirements")
        failure_reasons = _optional_list_field(payload, "failure_reasons")
        preferred_alternatives = _optional_list_field(payload, "preferred_alternatives")
        exception_guidance = _optional_list_field(payload, "exception_guidance")
        notes = _optional_list_field(payload, "notes")

        return cls(
            evaluation_id=payload["evaluation_id"],
            proposal_id=payload["proposal_id"],
            status=payload["status"],
            approval_requirements=[ApprovalRequirement(**item) for item in approval_requirements],
            failure_reasons=[PolicyFailureReason(**item) for item in failure_reasons],
            preferred_alternatives=[
                PreferredAlternative(**item) for item in preferred_alternatives
            ],
            exception_guidance=exception_guidance,
            notes=notes,
            compliance_score=payload.get("compliance_score", 1.0),
        )
