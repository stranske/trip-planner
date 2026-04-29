"""Helpers for mutating workspace-scoped transient state payloads."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, MutableMapping


def persist_tpp_proposal_id(workspace_state: MutableMapping[str, Any], proposal_id: str) -> None:
    """Persist the TPP proposal id onto workspace state."""
    normalized = proposal_id.strip()
    if not normalized:
        raise ValueError("proposal_id must be a non-empty string")
    workspace_state["tpp_proposal_id"] = normalized


def persist_tpp_result(
    workspace_state: MutableMapping[str, Any], result_payload: Mapping[str, Any]
) -> None:
    """Persist a TPP evaluation/result payload exactly as received.

    Uses ``deepcopy`` so that later mutations of the caller's payload (or of
    the stored copy) cannot leak through nested structures and corrupt the
    persisted snapshot.
    """
    workspace_state["tpp_result"] = deepcopy(dict(result_payload))


def load_tpp_result(workspace_state: Mapping[str, Any]) -> dict[str, Any] | None:
    """Reload a previously persisted TPP evaluation/result payload."""
    result_payload = workspace_state.get("tpp_result")
    if result_payload is None:
        return None
    if not isinstance(result_payload, dict):
        raise ValueError("workspace_state.tpp_result must be a mapping when present")
    return deepcopy(result_payload)
