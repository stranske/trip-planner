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
from .policy_sync import (
    OrganizationContextSnapshot,
    PolicyConstraintImport,
    PolicyFreshness,
    PolicySyncError,
    TPPPolicySyncService,
    summarize_policy_import,
)

__all__ = [
    "BaseTPPIntegrationClient",
    "OrganizationContextSnapshot",
    "PolicyConstraintImport",
    "PolicyFreshness",
    "PolicySyncError",
    "TPPCorrelationId",
    "TPPErrorRecord",
    "TPPExecutionStatus",
    "TPPIntegrationClient",
    "TPPOperationRequest",
    "TPPPolicySyncService",
    "TPPRequestEnvelope",
    "TPPResponseEnvelope",
    "TPPRetryMetadata",
    "summarize_policy_import",
]
