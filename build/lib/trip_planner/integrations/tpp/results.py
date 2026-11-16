"""Evaluation-result ingestion scaffolding for Travel-Plan-Permission."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from trip_planner._validators import require_non_empty
from trip_planner.business.policy_contracts import PolicyEvaluationResult

from .client import (
    TPPIntegrationClient,
    TPPTransportError,
    tpp_transport_error_from_exception,
)
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
class ProposalEvaluationLinkage:
    trip_id: str
    proposal_id: str
    proposal_version: str
    scenario_id: str | None = None
    execution_id: str | None = None
    organization_id: str | None = None

    def __post_init__(self) -> None:
        require_non_empty(self.trip_id, "trip_id")
        require_non_empty(self.proposal_id, "proposal_id")
        require_non_empty(self.proposal_version, "proposal_version")
        for field_name in ("scenario_id", "execution_id", "organization_id"):
            value = getattr(self, field_name)
            if value is not None:
                require_non_empty(value, field_name)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PersistedEvaluationResult:
    linkage: ProposalEvaluationLinkage
    request_id: str
    correlation_id: str
    transport_pattern: str
    execution_status: TPPExecutionStatus
    evaluation_result: PolicyEvaluationResult | None = None
    status_endpoint: str | None = None
    request_payload: dict[str, Any] = field(default_factory=dict)
    response_payload: dict[str, Any] = field(default_factory=dict)
    retry: TPPRetryMetadata | None = None
    error: TPPErrorRecord | None = None
    received_at: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.linkage, ProposalEvaluationLinkage):
            raise ValueError("linkage must be a ProposalEvaluationLinkage")
        require_non_empty(self.request_id, "request_id")
        require_non_empty(self.correlation_id, "correlation_id")
        require_non_empty(self.transport_pattern, "transport_pattern")
        if not isinstance(self.execution_status, TPPExecutionStatus):
            raise ValueError("execution_status must be a TPPExecutionStatus")
        if self.evaluation_result is not None and not isinstance(
            self.evaluation_result, PolicyEvaluationResult
        ):
            raise ValueError("evaluation_result must be a PolicyEvaluationResult")
        self.request_payload = _optional_mapping(self.request_payload, "request_payload")
        self.response_payload = _optional_mapping(self.response_payload, "response_payload")
        if self.retry is not None and not isinstance(self.retry, TPPRetryMetadata):
            raise ValueError("retry must be a TPPRetryMetadata when provided")
        if self.error is not None and not isinstance(self.error, TPPErrorRecord):
            raise ValueError("error must be a TPPErrorRecord when provided")
        _optional_string(self.status_endpoint, "status_endpoint")
        _optional_string(self.received_at, "received_at")
        if self.execution_status.state == "succeeded" and self.evaluation_result is None:
            raise ValueError(
                "succeeded evaluation responses must include a normalized evaluation_result"
            )

    @property
    def is_pending(self) -> bool:
        return self.execution_status.state in {
            "accepted",
            "running",
            "deferred",
            "retry_scheduled",
        }

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["linkage"] = self.linkage.to_dict()
        payload["execution_status"] = self.execution_status.to_dict()
        if self.evaluation_result is not None:
            payload["evaluation_result"] = self.evaluation_result.to_dict()
        if self.retry is not None:
            payload["retry"] = self.retry.to_dict()
        if self.error is not None:
            payload["error"] = self.error.to_dict()
        return payload


class EvaluationResultIngestionError(ValueError):
    """Raised when a TPP evaluation-result payload cannot be normalized safely."""


class TPPEvaluationResultIngestionService:
    """Fetch and normalize policy-evaluation results for persistence."""

    def __init__(self, client: TPPIntegrationClient) -> None:
        self.client = client

    def fetch_evaluation_result(
        self,
        request: TPPRequestEnvelope,
        *,
        proposal_version: str,
        scenario_id: str | None = None,
    ) -> PersistedEvaluationResult:
        try:
            response = self.client.fetch_evaluation_result(request)
        except TPPTransportError:
            raise
        except Exception as exc:
            transport_error = tpp_transport_error_from_exception(
                exc,
                operation="fetch_evaluation_result",
            )
            if transport_error is None:
                transport_error = TPPTransportError(
                    f"TPP fetch_evaluation_result transport failed unexpectedly: {exc}.",
                    error_code="unknown",
                    status_code=502,
                    retryable=False,
                )
            raise transport_error from exc
        return self.normalize_response(
            request,
            response,
            proposal_version=proposal_version,
            scenario_id=scenario_id,
        )

    def normalize_response(
        self,
        request: TPPRequestEnvelope,
        response: TPPResponseEnvelope,
        *,
        proposal_version: str,
        scenario_id: str | None = None,
    ) -> PersistedEvaluationResult:
        if request.operation != "fetch_evaluation_result":
            raise EvaluationResultIngestionError(
                "request.operation must be 'fetch_evaluation_result'"
            )
        if response.operation != "fetch_evaluation_result":
            raise EvaluationResultIngestionError(
                "response.operation must be 'fetch_evaluation_result'"
            )
        if response.request_id != request.request_id:
            raise EvaluationResultIngestionError(
                "response.request_id does not match request.request_id"
            )
        if response.correlation_id.value != request.correlation_id.value:
            raise EvaluationResultIngestionError(
                "response.correlation_id does not match request.correlation_id"
            )

        payload = _optional_mapping(response.result_payload, "result_payload")
        payload_trip_id = _optional_string(
            payload.get("trip_id"),
            "result_payload.trip_id",
        )
        linkage_trip_id = payload_trip_id or request.trip_id
        if not linkage_trip_id:
            raise EvaluationResultIngestionError(
                "trip_id is required in result_payload.trip_id when request.trip_id is missing"
            )

        payload_proposal_id = _optional_string(
            payload.get("proposal_id"),
            "result_payload.proposal_id",
        )
        linkage_proposal_id = payload_proposal_id or request.proposal_id
        if not linkage_proposal_id:
            raise EvaluationResultIngestionError(
                "proposal_id is required in result_payload.proposal_id when request.proposal_id is missing"
            )

        linkage = ProposalEvaluationLinkage(
            trip_id=linkage_trip_id,
            proposal_id=linkage_proposal_id,
            proposal_version=(
                _optional_string(
                    payload.get("proposal_version"),
                    "result_payload.proposal_version",
                )
                or proposal_version
            ),
            scenario_id=(
                _optional_string(
                    payload.get("scenario_id"),
                    "result_payload.scenario_id",
                )
                or scenario_id
            ),
            execution_id=_optional_string(
                payload.get("execution_id"),
                "result_payload.execution_id",
            ),
            organization_id=request.organization_id,
        )

        evaluation_result: PolicyEvaluationResult | None = None
        if response.execution_status.state == "succeeded":
            result_payload = _optional_mapping(
                payload.get("evaluation_result"),
                "result_payload.evaluation_result",
            )
            if not result_payload:
                raise EvaluationResultIngestionError(
                    "result_payload.evaluation_result is required for succeeded responses"
                )
            evaluation_result = PolicyEvaluationResult.from_dict(result_payload)
            if evaluation_result.proposal_id != linkage.proposal_id:
                raise EvaluationResultIngestionError(
                    "evaluation_result.proposal_id does not match linked proposal_id"
                )

        return PersistedEvaluationResult(
            linkage=linkage,
            request_id=request.request_id,
            correlation_id=request.correlation_id.value,
            transport_pattern=response.transport_pattern,
            execution_status=response.execution_status,
            evaluation_result=evaluation_result,
            status_endpoint=response.status_endpoint,
            request_payload=request.payload,
            response_payload=payload,
            retry=response.retry,
            error=response.error,
            received_at=response.received_at,
        )
