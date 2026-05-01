"""Travel-Plan-Permission integration contracts and client interfaces."""

from .client import (
    BaseTPPIntegrationClient,
    HTTPTPPIntegrationClient,
    TPPConfigurationError,
    TPPContractError,
    TPPIntegrationClient,
    TPPRuntimeSettings,
    TPPServiceUnavailableError,
    TPPTransportPolicy,
    TPPTransportError,
    tpp_transport_error_from_exception,
)
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
from .reoptimization import (
    PolicyReoptimizationContext,
    PolicyReoptimizationPlan,
    ReoptimizationPlanningError,
    TPPReoptimizationService,
)

__all__ = [
    "BaseTPPIntegrationClient",
    "HTTPTPPIntegrationClient",
    "OrganizationContextSnapshot",
    "PolicyConstraintImport",
    "PolicyFreshness",
    "PolicySyncError",
    "PersistedEvaluationResult",
    "ProposalEvaluationLinkage",
    "ProposalSubmissionError",
    "ProposalSubmissionLinkage",
    "ProposalSubmissionRecord",
    "PolicyReoptimizationContext",
    "PolicyReoptimizationPlan",
    "ReoptimizationPlanningError",
    "TPPCorrelationId",
    "TPPErrorRecord",
    "TPPEvaluationResultIngestionService",
    "TPPExecutionStatus",
    "TPPIntegrationClient",
    "TPPConfigurationError",
    "TPPContractError",
    "TPPOperationRequest",
    "TPPProposalSubmissionService",
    "TPPPolicySyncService",
    "TPPRuntimeSettings",
    "TPPServiceUnavailableError",
    "TPPTransportPolicy",
    "TPPTransportError",
    "tpp_transport_error_from_exception",
    "TPPReoptimizationService",
    "TPPRequestEnvelope",
    "TPPResponseEnvelope",
    "TPPRetryMetadata",
    "EvaluationResultIngestionError",
    "summarize_policy_import",
]
