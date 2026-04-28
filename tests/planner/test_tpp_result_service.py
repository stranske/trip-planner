from __future__ import annotations

import json

import pytest

from trip_planner.app.services.tpp_result_service import TPPResultService
from trip_planner.integrations.tpp.client import TPPContractError


def test_persist_result_stores_payload_with_exact_structure_preservation() -> None:
    service = TPPResultService()
    workspace_state: dict[str, object] = {}
    payload = {
        "execution_status": {"state": "succeeded", "terminal": True},
        "result_payload": {
            "trip_id": "trip-100",
            "proposal_id": "proposal-123",
            "evaluation_result": {
                "evaluation_id": "eval-001",
                "proposal_id": "proposal-123",
                "status": "compliant",
                "approval_requirements": [],
                "failure_reasons": [],
                "preferred_alternatives": [],
                "exception_guidance": ["none"],
                "notes": ["all good"],
                "compliance_score": 0.99,
            },
            "nested": {"a": [1, 2, {"deep": "value"}]},
        },
    }

    persisted = service.persist_result(workspace_state, payload)

    assert json.dumps(workspace_state["tpp_result"], sort_keys=True) == json.dumps(
        payload, sort_keys=True
    )
    assert json.dumps(persisted, sort_keys=True) == json.dumps(payload, sort_keys=True)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"execution_status": {"state": ""}, "result_payload": {"trip_id": "trip-1"}},
        {
            "execution_status": {"state": "succeeded"},
            "result_payload": {"proposal_id": "proposal-1"},
        },
        {
            "execution_status": {"state": "succeeded"},
            "result_payload": {"trip_id": "trip-1", "proposal_id": "proposal-1"},
        },
    ],
)
def test_persist_result_raises_domain_error_for_malformed_payload(
    payload: dict[str, object],
) -> None:
    service = TPPResultService()
    workspace_state: dict[str, object] = {}

    with pytest.raises(TPPContractError):
        service.persist_result(workspace_state, payload)

    assert "tpp_result" not in workspace_state
