"""Proposal submission scaffolding for Travel-Plan-Permission."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from trip_planner._validators import require_non_empty
from trip_planner.business.policy_contracts import TripPlanProposal

from .client import TPPIntegrationClient
from .contracts import (
    TPPErrorRecord,
    TPPExecutionStatus,
    TPPRequestEnvelope,
    TPPResponseEnvelope,
    TPPRetryMetadata,
)


def _optional_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be provided as a mapping")
    return dict(value)


def _optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be provided as a string")
    require_non_empty(value, field_name)
    return value


@dataclass(slots=True)
class ProposalSubmissionLinkage:
    trip_id: str
    proposal_id: str
    proposal_version: str
    scenario_id: str | None = None
    constraint_set_id: str | None = None
    organization_id: str | None = None

    def __post_init__(self) -> None:
        require_non_empty(self.trip_id, "trip_id")
        require_non_empty(self.proposal_id, "proposal_id")
        require_non_empty(self.proposal_version, "proposal_version")
        for field_name in ("scenario_id", "constraint_set_id", "organization_id"):
            value = getattr(self, field_name)
            if value is not None:
                require_non_empty(value, field_name)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ProposalSubmissionRecord:
    proposal: TripPlanProposal
    linkage: ProposalSubmissionLinkage
    request_id: str
    correlation_id: str
    transport_pattern: str
    execution_status: TPPExecutionStatus
    execution_id: str | None = None
    queue_state: str | None = None
    status_endpoint: str | None = None
    request_payload: dict[str, Any] = field(default_factory=dict)
    response_payload: dict[str, Any] = field(default_factory=dict)
    retry: TPPRetryMetadata | None = None
    error: TPPErrorRecord | None = None
    submitted_at: str | None = None
    received_at: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.proposal, TripPlanProposal):
            raise ValueError("proposal must be a TripPlanProposal")
        if not isinstance(self.linkage, ProposalSubmissionLinkage):
            raise ValueError("linkage must be a ProposalSubmissionLinkage")
        require_non_empty(self.request_id, "request_id")
        require_non_empty(self.correlation_id, "correlation_id")
        require_non_empty(self.transport_pattern, "transport_pattern")
        if not isinstance(self.execution_status, TPPExecutionStatus):
            raise ValueError("execution_status must be a TPPExecutionStatus")
        self.request_payload = _optional_mapping(self.request_payload, "request_payload")
        self.response_payload = _optional_mapping(self.response_payload, "response_payload")
        for field_name in (
            "execution_id",
            "queue_state",
            "status_endpoint",
            "submitted_at",
            "received_at",
        ):
            _optional_string(getattr(self, field_name), field_name)
        if self.retry is not None and not isinstance(self.retry, TPPRetryMetadata):
            raise ValueError("retry must be a TPPRetryMetadata when provided")
        if self.error is not None and not isinstance(self.error, TPPErrorRecord):
            raise ValueError("error must be a TPPErrorRecord when provided")

    @property
    def requires_polling(self) -> bool:
        return self.execution_status.state in {
            "accepted",
            "running",
            "deferred",
            "retry_scheduled",
        }

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["proposal"] = self.proposal.to_dict()
        payload["linkage"] = self.linkage.to_dict()
        payload["execution_status"] = self.execution_status.to_dict()
        if self.retry is not None:
            payload["retry"] = self.retry.to_dict()
        if self.error is not None:
            payload["error"] = self.error.to_dict()
        return payload


class ProposalSubmissionError(ValueError):
    """Raised when a TPP proposal submission cannot be normalized safely."""


class TPPProposalSubmissionService:
    """Submit business proposals and persist their transport metadata."""

    def __init__(self, client: TPPIntegrationClient) -> None:
        self.client = client

    def submit_proposal(
        self,
        request: TPPRequestEnvelope,
        proposal: TripPlanProposal,
        *,
        proposal_version: str,
        scenario_id: str | None = None,
    ) -> ProposalSubmissionRecord:
        response = self.client.submit_proposal(request)
        return self.normalize_response(
            request,
            proposal,
            response,
            proposal_version=proposal_version,
            scenario_id=scenario_id,
        )

    def normalize_response(
        self,
        request: TPPRequestEnvelope,
        proposal: TripPlanProposal,
        response: TPPResponseEnvelope,
        *,
        proposal_version: str,
        scenario_id: str | None = None,
    ) -> ProposalSubmissionRecord:
        if request.operation != "submit_proposal":
            raise ProposalSubmissionError("request.operation must be 'submit_proposal'")
        if response.operation != "submit_proposal":
            raise ProposalSubmissionError("response.operation must be 'submit_proposal'")
        if response.request_id != request.request_id:
            raise ProposalSubmissionError("response.request_id does not match request.request_id")
        if response.correlation_id.value != request.correlation_id.value:
            raise ProposalSubmissionError(
                "response.correlation_id does not match request.correlation_id"
            )
        if request.proposal_id is not None and request.proposal_id != proposal.proposal_id:
            raise ProposalSubmissionError("request.proposal_id does not match proposal.proposal_id")
        if request.trip_id is not None and request.trip_id != proposal.trip_id:
            raise ProposalSubmissionError("request.trip_id does not match proposal.trip_id")

        response_payload = _optional_mapping(response.result_payload, "result_payload")
        linkage = ProposalSubmissionLinkage(
            trip_id=proposal.trip_id,
            proposal_id=proposal.proposal_id,
            proposal_version=proposal_version,
            scenario_id=(
                _optional_string(
                    response_payload.get("scenario_id"),
                    "result_payload.scenario_id",
                )
                or scenario_id
            ),
            constraint_set_id=proposal.constraint_set_id,
            organization_id=request.organization_id,
        )

        execution_id = _optional_string(
            response_payload.get("execution_id"),
            "result_payload.execution_id",
        )
        if response.execution_status.state in {"accepted", "running", "deferred"}:
            if execution_id is None:
                raise ProposalSubmissionError(
                    "result_payload.execution_id is required for non-terminal submissions"
                )

        return ProposalSubmissionRecord(
            proposal=proposal,
            linkage=linkage,
            request_id=request.request_id,
            correlation_id=request.correlation_id.value,
            transport_pattern=response.transport_pattern,
            execution_status=response.execution_status,
            execution_id=execution_id,
            queue_state=_optional_string(
                response_payload.get("queue_state"),
                "result_payload.queue_state",
            ),
            status_endpoint=response.status_endpoint,
            request_payload=request.payload,
            response_payload=response_payload,
            retry=response.retry,
            error=response.error,
            submitted_at=request.submitted_at,
            received_at=response.received_at,
        )
