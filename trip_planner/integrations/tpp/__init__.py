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
from .results import (
    EvaluationResultIngestionError,
    PersistedEvaluationResult,
    ProposalEvaluationLinkage,
    TPPEvaluationResultIngestionService,
)
from .submission import (
    ProposalSubmissionError,
    ProposalSubmissionLinkage,
    ProposalSubmissionRecord,
    TPPProposalSubmissionService,
)

__all__ = [
    "BaseTPPIntegrationClient",
    "OrganizationContextSnapshot",
    "PolicyConstraintImport",
    "PolicyFreshness",
    "PolicySyncError",
    "PersistedEvaluationResult",
    "ProposalEvaluationLinkage",
    "ProposalSubmissionError",
    "ProposalSubmissionLinkage",
    "ProposalSubmissionRecord",
    "TPPCorrelationId",
    "TPPErrorRecord",
    "TPPEvaluationResultIngestionService",
    "TPPExecutionStatus",
    "TPPIntegrationClient",
    "TPPOperationRequest",
    "TPPProposalSubmissionService",
    "TPPPolicySyncService",
    "TPPRequestEnvelope",
    "TPPResponseEnvelope",
    "TPPRetryMetadata",
    "EvaluationResultIngestionError",
    "summarize_policy_import",
]
