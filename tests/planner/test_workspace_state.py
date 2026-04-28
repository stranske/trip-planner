from __future__ import annotations

import pytest

from trip_planner.app.services.workspace_state import persist_tpp_proposal_id


def test_persist_tpp_proposal_id_sets_workspace_state_field() -> None:
    state: dict[str, object] = {"existing": "value"}

    persist_tpp_proposal_id(state, "proposal-123")

    assert state["existing"] == "value"
    assert state["tpp_proposal_id"] == "proposal-123"


def test_persist_tpp_proposal_id_rejects_blank_ids() -> None:
    state: dict[str, object] = {}

    with pytest.raises(ValueError, match="proposal_id must be a non-empty string"):
        persist_tpp_proposal_id(state, "   ")

    assert "tpp_proposal_id" not in state
