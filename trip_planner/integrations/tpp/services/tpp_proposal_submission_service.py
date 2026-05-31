"""Workspace-level TPP proposal submission service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping, MutableMapping
from uuid import uuid4

from trip_planner.integrations.tpp.client import TPPIntegrationClient
from trip_planner.integrations.tpp.contracts import (
    TPPCorrelationId,
    TPPRequestEnvelope,
)
from trip_planner.integrations.tpp.services.workspace_state import (
    persist_tpp_proposal_id,
)
from trip_planner.integrations.tpp.validation import (
    validate_submit_response_proposal_id,
)


@dataclass(frozen=True, slots=True)
class ProposalSubmissionResult:
    proposal_id: str
    success: bool


class TPPWorkspaceProposalSubmissionService:
    """Build submit-proposal requests from workspace data and dispatch via TPP client."""

    def __init__(self, client: TPPIntegrationClient) -> None:
        self._client = client

    def submit(
        self, workspace_data: Mapping[str, Any], workspace_state: MutableMapping[str, Any]
    ) -> ProposalSubmissionResult:
        payload = dict(workspace_data)
        request_id = str(payload.get("request_id") or f"req-{uuid4()}")
        correlation_value = str(payload.get("correlation_id") or request_id)
        organization_id = _optional_non_empty_string(payload.get("organization_id"))
        trip_id = _optional_non_empty_string(payload.get("trip_id"))
        proposal_id = _optional_non_empty_string(payload.get("proposal_id"))
        submitted_at = (
            _optional_non_empty_string(payload.get("submitted_at")) or datetime.now(UTC).isoformat()
        )

        request = TPPRequestEnvelope(
            operation="submit_proposal",
            request_id=request_id,
            correlation_id=TPPCorrelationId(value=correlation_value),
            payload=payload,
            transport_pattern="sync",
            organization_id=organization_id,
            trip_id=trip_id,
            proposal_id=proposal_id,
            submitted_at=submitted_at,
        )
        response = self._client.submit_proposal(request)
        extracted_proposal_id = validate_submit_response_proposal_id(response.to_dict())
        persist_tpp_proposal_id(workspace_state, extracted_proposal_id)
        return ProposalSubmissionResult(proposal_id=extracted_proposal_id, success=True)


def _optional_non_empty_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
