"""Shared contract validators for TPP response payload envelopes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from trip_planner.business.policy_contracts import PolicyEvaluationResult
from trip_planner.integrations.tpp.client import TPPContractError
from trip_planner.integrations.tpp.contracts import (
    TPPCorrelationId,
    TPPExecutionStatus,
    TPPResponseEnvelope,
)


def validate_succeeded_response(
    result_response_payload: Mapping[str, Any],
    *,
    required_result_fields: tuple[str, ...] = ("trip_id", "proposal_id"),
) -> dict[str, Any]:
    if not isinstance(result_response_payload, Mapping):
        raise TPPContractError("TPP result response contract requires an object payload.")

    execution_status = _extract_execution_status(result_response_payload)
    state = execution_status.state.strip().lower()
    result_payload = _extract_result_payload(result_response_payload)

    for required_field in required_result_fields:
        value = result_payload.get(required_field)
        if not isinstance(value, str) or not value.strip():
            raise TPPContractError(
                f"TPP result response contract requires non-empty 'result_payload.{required_field}'."
            )

    if state == "succeeded":
        evaluation_result = result_payload.get("evaluation_result")
        if not isinstance(evaluation_result, dict):
            raise TPPContractError(
                "TPP result response contract requires 'result_payload.evaluation_result' when succeeded."
            )
        try:
            PolicyEvaluationResult.from_dict(evaluation_result)
        except (KeyError, ValueError, TypeError) as exc:
            raise TPPContractError(
                "Malformed 'result_payload.evaluation_result' contract."
            ) from exc

    return dict(result_response_payload)


def _extract_execution_status(result_response_payload: Mapping[str, Any]) -> TPPExecutionStatus:
    execution_status_payload = result_response_payload.get("execution_status")
    if not isinstance(execution_status_payload, Mapping):
        raise TPPContractError("TPP result response contract requires 'execution_status'.")

    try:
        return TPPExecutionStatus(**dict(execution_status_payload))
    except (TypeError, ValueError) as exc:
        raise TPPContractError("Malformed 'execution_status' contract.") from exc


def _extract_result_payload(result_response_payload: Mapping[str, Any]) -> dict[str, Any]:
    result_payload = result_response_payload.get("result_payload")
    if not isinstance(result_payload, Mapping):
        raise TPPContractError("TPP result response contract requires 'result_payload'.")
    try:
        return TPPResponseEnvelope(
            operation="fetch_evaluation_result",
            request_id="validation-request",
            correlation_id=TPPCorrelationId(value="validation-correlation"),
            transport_pattern="sync",
            execution_status=TPPExecutionStatus(state="accepted", terminal=False),
            result_payload=dict(result_payload),
        ).result_payload
    except (TypeError, ValueError) as exc:
        raise TPPContractError("Malformed 'result_payload' contract.") from exc


def validate_poll_response_state(poll_response_payload: Mapping[str, Any]) -> str:
    state = poll_response_payload.get("state")
    if not isinstance(state, str) or not state.strip():
        raise TPPContractError("TPP poll response contract requires non-empty 'state'.")
    return state


def validate_submit_response_proposal_id(result_response_payload: Mapping[str, Any]) -> str:
    normalized = validate_succeeded_response(
        result_response_payload,
        required_result_fields=("proposal_id",),
    )
    result_payload = normalized["result_payload"]
    return str(result_payload["proposal_id"]).strip()
