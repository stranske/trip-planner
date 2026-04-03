"""Transport-neutral execution contracts for Travel-Plan-Permission."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from trip_planner.contracts._validators import require_non_empty, require_non_negative

TPP_OPERATION_TYPES: tuple[str, ...] = (
    "fetch_policy_constraints",
    "submit_proposal",
    "fetch_evaluation_result",
    "poll_execution_status",
)
TPP_TRANSPORT_PATTERNS: tuple[str, ...] = ("sync", "async", "deferred")
TPP_EXECUTION_STATES: tuple[str, ...] = (
    "accepted",
    "running",
    "succeeded",
    "failed",
    "deferred",
    "retry_scheduled",
    "cancelled",
)


def _require_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be provided as a mapping")
    return dict(value)


def _optional_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    return _require_mapping(value, field_name)


@dataclass(slots=True)
class TPPCorrelationId:
    value: str
    issued_by: str = "trip-planner"

    def __post_init__(self) -> None:
        require_non_empty(self.value, "value")
        require_non_empty(self.issued_by, "issued_by")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_value(cls, value: str | dict[str, Any]) -> "TPPCorrelationId":
        if isinstance(value, str):
            return cls(value=value)
        if isinstance(value, dict):
            return cls(**value)
        raise ValueError("correlation_id must be provided as a string or mapping")


@dataclass(slots=True)
class TPPRetryMetadata:
    attempt: int
    max_attempts: int
    retryable: bool
    backoff_seconds: float | None = None
    next_retry_at: str | None = None
    reason: str = ""

    def __post_init__(self) -> None:
        if self.attempt < 0:
            raise ValueError("attempt must be non-negative")
        if self.max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        if self.attempt > self.max_attempts:
            raise ValueError("attempt must not exceed max_attempts")
        if self.backoff_seconds is not None:
            require_non_negative(self.backoff_seconds, "backoff_seconds")
        if self.next_retry_at is not None and not self.next_retry_at:
            raise ValueError("next_retry_at must be non-empty when provided")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TPPErrorRecord:
    code: str
    message: str
    category: str = "transport"
    retryable: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.code, "code")
        require_non_empty(self.message, "message")
        require_non_empty(self.category, "category")
        self.details = _optional_mapping(self.details, "details")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TPPExecutionStatus:
    state: str
    terminal: bool
    summary: str = ""
    external_status: str = ""
    poll_after_seconds: float | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if self.state not in TPP_EXECUTION_STATES:
            raise ValueError(f"state must be one of {TPP_EXECUTION_STATES}")
        if self.poll_after_seconds is not None:
            require_non_negative(self.poll_after_seconds, "poll_after_seconds")
        if self.updated_at is not None and not self.updated_at:
            raise ValueError("updated_at must be non-empty when provided")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TPPRequestEnvelope:
    operation: str
    request_id: str
    correlation_id: TPPCorrelationId
    payload: dict[str, Any]
    transport_pattern: str = "sync"
    organization_id: str | None = None
    trip_id: str | None = None
    proposal_id: str | None = None
    submitted_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.operation not in TPP_OPERATION_TYPES:
            raise ValueError(f"operation must be one of {TPP_OPERATION_TYPES}")
        require_non_empty(self.request_id, "request_id")
        if not isinstance(self.correlation_id, TPPCorrelationId):
            raise ValueError("correlation_id must be a TPPCorrelationId")
        if self.transport_pattern not in TPP_TRANSPORT_PATTERNS:
            raise ValueError(
                f"transport_pattern must be one of {TPP_TRANSPORT_PATTERNS}"
            )
        self.payload = _require_mapping(self.payload, "payload")
        self.metadata = _optional_mapping(self.metadata, "metadata")
        for field_name in ("organization_id", "trip_id", "proposal_id", "submitted_at"):
            value = getattr(self, field_name)
            if value is not None and not value:
                raise ValueError(f"{field_name} must be non-empty when provided")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["correlation_id"] = self.correlation_id.to_dict()
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TPPRequestEnvelope":
        request = _require_mapping(payload, "payload")
        return cls(
            operation=request["operation"],
            request_id=request["request_id"],
            correlation_id=TPPCorrelationId.from_value(request["correlation_id"]),
            payload=_require_mapping(request["payload"], "payload.payload"),
            transport_pattern=request.get("transport_pattern", "sync"),
            organization_id=request.get("organization_id"),
            trip_id=request.get("trip_id"),
            proposal_id=request.get("proposal_id"),
            submitted_at=request.get("submitted_at"),
            metadata=_optional_mapping(request.get("metadata"), "metadata"),
        )


TPPOperationRequest = TPPRequestEnvelope


@dataclass(slots=True)
class TPPResponseEnvelope:
    operation: str
    request_id: str
    correlation_id: TPPCorrelationId
    transport_pattern: str
    execution_status: TPPExecutionStatus
    result_payload: dict[str, Any] = field(default_factory=dict)
    error: TPPErrorRecord | None = None
    retry: TPPRetryMetadata | None = None
    received_at: str | None = None
    status_endpoint: str | None = None

    def __post_init__(self) -> None:
        if self.operation not in TPP_OPERATION_TYPES:
            raise ValueError(f"operation must be one of {TPP_OPERATION_TYPES}")
        require_non_empty(self.request_id, "request_id")
        if not isinstance(self.correlation_id, TPPCorrelationId):
            raise ValueError("correlation_id must be a TPPCorrelationId")
        if self.transport_pattern not in TPP_TRANSPORT_PATTERNS:
            raise ValueError(
                f"transport_pattern must be one of {TPP_TRANSPORT_PATTERNS}"
            )
        if not isinstance(self.execution_status, TPPExecutionStatus):
            raise ValueError("execution_status must be a TPPExecutionStatus")
        self.result_payload = _optional_mapping(self.result_payload, "result_payload")
        if self.error is not None and not isinstance(self.error, TPPErrorRecord):
            raise ValueError("error must be a TPPErrorRecord when provided")
        if self.retry is not None and not isinstance(self.retry, TPPRetryMetadata):
            raise ValueError("retry must be a TPPRetryMetadata when provided")
        if self.execution_status.state == "failed" and self.error is None:
            raise ValueError("failed execution_status entries must include an error")
        for field_name in ("received_at", "status_endpoint"):
            value = getattr(self, field_name)
            if value is not None and not value:
                raise ValueError(f"{field_name} must be non-empty when provided")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["correlation_id"] = self.correlation_id.to_dict()
        payload["execution_status"] = self.execution_status.to_dict()
        if self.error is not None:
            payload["error"] = self.error.to_dict()
        if self.retry is not None:
            payload["retry"] = self.retry.to_dict()
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TPPResponseEnvelope":
        response = _require_mapping(payload, "payload")
        return cls(
            operation=response["operation"],
            request_id=response["request_id"],
            correlation_id=TPPCorrelationId.from_value(response["correlation_id"]),
            transport_pattern=response.get("transport_pattern", "sync"),
            execution_status=TPPExecutionStatus(**response["execution_status"]),
            result_payload=_optional_mapping(
                response.get("result_payload"), "result_payload"
            ),
            error=(
                TPPErrorRecord(**response["error"])
                if response.get("error") is not None
                else None
            ),
            retry=(
                TPPRetryMetadata(**response["retry"])
                if response.get("retry") is not None
                else None
            ),
            received_at=response.get("received_at"),
            status_endpoint=response.get("status_endpoint"),
        )
