"""Travel-Plan-Permission integration contracts and client interfaces."""

from .client import BaseTPPIntegrationClient, TPPIntegrationClient
from .contracts import (
    TPPErrorRecord,
    TPPExecutionStatus,
    TPPOperationRequest,
    TPPRequestEnvelope,
    TPPResponseEnvelope,
    TPPRetryMetadata,
    TPPCorrelationId,
)

__all__ = [
    "BaseTPPIntegrationClient",
    "TPPCorrelationId",
    "TPPErrorRecord",
    "TPPExecutionStatus",
    "TPPIntegrationClient",
    "TPPOperationRequest",
    "TPPRequestEnvelope",
    "TPPResponseEnvelope",
    "TPPRetryMetadata",
]
