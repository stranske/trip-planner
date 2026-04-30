"""Workspace-level TPP evaluation result validation and persistence."""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping

from trip_planner.integrations.tpp.validation import validate_succeeded_response
from trip_planner.integrations.tpp.services.workspace_state import persist_tpp_result


class TPPResultService:
    """Validate contract-critical fields and persist raw result payloads."""

    def persist_result(
        self, workspace_state: MutableMapping[str, Any], result_response_payload: Mapping[str, Any]
    ) -> dict[str, Any]:
        normalized_payload = _validate_result_response_payload(result_response_payload)
        persist_tpp_result(workspace_state, normalized_payload)
        return normalized_payload


def _validate_result_response_payload(result_response_payload: Mapping[str, Any]) -> dict[str, Any]:
    return validate_succeeded_response(result_response_payload)
