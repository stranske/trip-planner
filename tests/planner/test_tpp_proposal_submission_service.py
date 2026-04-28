from __future__ import annotations

import pytest

from trip_planner.app.services.tpp_proposal_submission_service import (
    ProposalSubmissionResult,
    TPPWorkspaceProposalSubmissionService,
)
from trip_planner.integrations.tpp.client import BaseTPPIntegrationClient
from trip_planner.integrations.tpp.client import TPPContractError
from trip_planner.integrations.tpp.contracts import (
    TPPCorrelationId,
    TPPExecutionStatus,
    TPPRequestEnvelope,
    TPPResponseEnvelope,
)


class _FakeTPPClient(BaseTPPIntegrationClient):
    def __init__(self) -> None:
        self.last_request: TPPRequestEnvelope | None = None

    def execute(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        self.last_request = request
        return TPPResponseEnvelope(
            operation="submit_proposal",
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            transport_pattern="sync",
            execution_status=TPPExecutionStatus(state="accepted", terminal=False),
            result_payload={"proposal_id": request.proposal_id or "proposal-fallback"},
        )


def test_submit_builds_submit_proposal_request_from_workspace_data() -> None:
    client = _FakeTPPClient()
    service = TPPWorkspaceProposalSubmissionService(client)
    workspace_state: dict[str, object] = {}
    workspace_data = {
        "organization_id": "org-123",
        "trip_id": "trip-123",
        "proposal_id": "proposal-123",
        "request_id": "req-123",
        "correlation_id": "corr-123",
        "custom": {"priority": "high"},
    }

    response = service.submit(workspace_data, workspace_state)

    assert client.last_request is not None
    assert client.last_request.operation == "submit_proposal"
    assert client.last_request.request_id == "req-123"
    assert client.last_request.correlation_id == TPPCorrelationId(value="corr-123")
    assert client.last_request.organization_id == "org-123"
    assert client.last_request.trip_id == "trip-123"
    assert client.last_request.proposal_id == "proposal-123"
    assert client.last_request.payload == workspace_data
    assert response == ProposalSubmissionResult(proposal_id="proposal-123", success=True)
    assert workspace_state["tpp_proposal_id"] == "proposal-123"


def test_submit_raises_domain_error_and_does_not_persist_proposal_id_for_bad_contract() -> None:
    class _MalformedTPPClient(_FakeTPPClient):
        def execute(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope:
            self.last_request = request
            return TPPResponseEnvelope(
                operation="submit_proposal",
                request_id=request.request_id,
                correlation_id=request.correlation_id,
                transport_pattern="sync",
                execution_status=TPPExecutionStatus(state="accepted", terminal=False),
                result_payload={},
            )

    client = _MalformedTPPClient()
    service = TPPWorkspaceProposalSubmissionService(client)
    workspace_state: dict[str, object] = {}

    with pytest.raises(TPPContractError, match="result_payload.proposal_id"):
        service.submit({"trip_id": "trip-123"}, workspace_state)

    assert "tpp_proposal_id" not in workspace_state
