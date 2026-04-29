"""Workspace-level TPP evaluation result validation and persistence."""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping

from trip_planner.integrations.tpp.services.workspace_state import persist_tpp_result
from trip_planner.business.policy_contracts import PolicyEvaluationResult
from trip_planner.integrations.tpp.client import TPPContractError


class TPPResultService:
    """Validate contract-critical fields and persist raw result payloads."""

    def persist_result(
        self, workspace_state: MutableMapping[str, Any], result_response_payload: Mapping[str, Any]
    ) -> dict[str, Any]:
        normalized_payload = _validate_result_response_payload(result_response_payload)
        persist_tpp_result(workspace_state, normalized_payload)
        return normalized_payload


def _validate_result_response_payload(result_response_payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(result_response_payload, Mapping):
        raise TPPContractError("TPP result response contract requires an object payload.")

    execution_status = result_response_payload.get("execution_status")
    if not isinstance(execution_status, Mapping):
        raise TPPContractError("TPP result response contract requires 'execution_status'.")

    state = execution_status.get("state")
    if not isinstance(state, str) or not state.strip():
        raise TPPContractError(
            "TPP result response contract requires non-empty 'execution_status.state'."
        )

    result_payload = result_response_payload.get("result_payload")
    if not isinstance(result_payload, Mapping):
        raise TPPContractError("TPP result response contract requires 'result_payload'.")

    for required_field in ("trip_id", "proposal_id"):
        value = result_payload.get(required_field)
        if not isinstance(value, str) or not value.strip():
            raise TPPContractError(
                f"TPP result response contract requires non-empty 'result_payload.{required_field}'."
            )

    if state.strip().lower() == "succeeded":
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
