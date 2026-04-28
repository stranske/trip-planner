from __future__ import annotations

from trip_planner.app.services.tpp_proposal_submission_service import (
    TPPWorkspaceProposalSubmissionService,
)
from trip_planner.integrations.tpp.client import BaseTPPIntegrationClient
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
    workspace_data = {
        "organization_id": "org-123",
        "trip_id": "trip-123",
        "proposal_id": "proposal-123",
        "request_id": "req-123",
        "correlation_id": "corr-123",
        "custom": {"priority": "high"},
    }

    response = service.submit(workspace_data)

    assert client.last_request is not None
    assert client.last_request.operation == "submit_proposal"
    assert client.last_request.request_id == "req-123"
    assert client.last_request.correlation_id == TPPCorrelationId(value="corr-123")
    assert client.last_request.organization_id == "org-123"
    assert client.last_request.trip_id == "trip-123"
    assert client.last_request.proposal_id == "proposal-123"
    assert client.last_request.payload == workspace_data
    assert response.result_payload["proposal_id"] == "proposal-123"
