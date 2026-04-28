from __future__ import annotations

import json

import pytest

from trip_planner.app.services.workspace_state import load_tpp_result, persist_tpp_proposal_id


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


def test_load_tpp_result_rehydrates_payload_with_exact_structure_preservation() -> None:
    original_result = {
        "execution_status": {"state": "succeeded", "terminal": True},
        "result_payload": {
            "trip_id": "trip-100",
            "proposal_id": "proposal-123",
            "nested": {"a": [1, {"deep": ["x", "y"]}]},
        },
    }
    workspace_state: dict[str, object] = {"tpp_result": original_result}

    rehydrated_result = load_tpp_result(workspace_state)

    assert rehydrated_result is not None
    assert json.dumps(rehydrated_result, sort_keys=True) == json.dumps(
        original_result, sort_keys=True
    )
