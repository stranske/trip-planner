"""Travel-Plan-Permission integration contracts and client interfaces."""

from .client import (
    BaseTPPIntegrationClient,
    HTTPTPPIntegrationClient,
    TPPConfigurationError,
    TPPContractError,
    TPPIntegrationClient,
    TPPRuntimeSettings,
    TPPServiceUnavailableError,
    TPPTransportError,
    TPPTransportPolicy,
    tpp_transport_error_from_exception,
)
from .contracts import (
    TPPCorrelationId,
    TPPErrorRecord,
    TPPExecutionStatus,
    TPPOperationRequest,
    TPPRequestEnvelope,
    TPPResponseEnvelope,
    TPPRetryMetadata,
)
from .policy_sync import (
    OrganizationContextSnapshot,
    PolicyConstraintImport,
    PolicyFreshness,
    PolicySyncError,
    TPPPolicyRequirement,
    TPPPolicySyncService,
    summarize_policy_import,
)
from .reoptimization import (
    PolicyReoptimizationContext,
    PolicyReoptimizationPlan,
    ReoptimizationPlanningError,
    TPPReoptimizationService,
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
    "EvaluationResultIngestionError",
    "HTTPTPPIntegrationClient",
    "OrganizationContextSnapshot",
    "PersistedEvaluationResult",
    "PolicyConstraintImport",
    "PolicyFreshness",
    "PolicyReoptimizationContext",
    "PolicyReoptimizationPlan",
    "PolicySyncError",
    "ProposalEvaluationLinkage",
    "ProposalSubmissionError",
    "ProposalSubmissionLinkage",
    "ProposalSubmissionRecord",
    "ReoptimizationPlanningError",
    "TPPConfigurationError",
    "TPPContractError",
    "TPPCorrelationId",
    "TPPErrorRecord",
    "TPPEvaluationResultIngestionService",
    "TPPExecutionStatus",
    "TPPIntegrationClient",
    "TPPOperationRequest",
    "TPPPolicyRequirement",
    "TPPPolicySyncService",
    "TPPProposalSubmissionService",
    "TPPReoptimizationService",
    "TPPRequestEnvelope",
    "TPPResponseEnvelope",
    "TPPRetryMetadata",
    "TPPRuntimeSettings",
    "TPPServiceUnavailableError",
    "TPPTransportError",
    "TPPTransportPolicy",
    "summarize_policy_import",
    "tpp_transport_error_from_exception",
]
