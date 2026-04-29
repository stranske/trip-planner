from __future__ import annotations

import pytest

from trip_planner.integrations.tpp.client import TPPContractError
from trip_planner.integrations.tpp.validation import validate_succeeded_response


def _valid_payload() -> dict[str, object]:
    return {
        "execution_status": {"state": "succeeded", "terminal": True},
        "result_payload": {
            "trip_id": "trip-1",
            "proposal_id": "proposal-1",
            "evaluation_result": {
                "evaluation_id": "eval-1",
                "proposal_id": "proposal-1",
                "status": "compliant",
                "approval_requirements": [],
                "failure_reasons": [],
                "preferred_alternatives": [],
                "exception_guidance": [],
                "notes": [],
                "compliance_score": 1.0,
            },
        },
    }


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("execution_status", "execution_status"),
        ("result_payload", "result_payload"),
        ("trip_id", "result_payload.trip_id"),
        ("proposal_id", "result_payload.proposal_id"),
    ],
)
def test_validate_succeeded_response_rejects_missing_required_fields(
    field: str, expected: str
) -> None:
    payload = _valid_payload()
    if field in {"execution_status", "result_payload"}:
        del payload[field]
    else:
        result_payload = payload["result_payload"]
        assert isinstance(result_payload, dict)
        del result_payload[field]

    with pytest.raises(TPPContractError, match=expected):
        validate_succeeded_response(payload)


def test_validate_succeeded_response_accepts_all_required_fields() -> None:
    payload = _valid_payload()
    assert validate_succeeded_response(payload) == payload
