"""Helpers for mutating workspace-scoped transient state payloads."""

from __future__ import annotations

from typing import Any, MutableMapping


def persist_tpp_proposal_id(workspace_state: MutableMapping[str, Any], proposal_id: str) -> None:
    """Persist the TPP proposal id onto workspace state."""
    normalized = proposal_id.strip()
    if not normalized:
        raise ValueError("proposal_id must be a non-empty string")
    workspace_state["tpp_proposal_id"] = normalized
