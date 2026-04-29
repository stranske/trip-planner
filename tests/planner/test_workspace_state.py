from __future__ import annotations

import json

import pytest

from trip_planner.app.services.workspace_state import (
    load_tpp_result,
    persist_tpp_proposal_id,
    persist_tpp_result,
)


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


def test_persist_tpp_result_isolates_persisted_snapshot_from_caller_mutation() -> None:
    # Mutating the original payload after persisting must not leak into workspace state,
    # and mutating the persisted snapshot must not leak back into the caller's payload.
    original_payload = {
        "execution_status": {"state": "succeeded", "terminal": True},
        "result_payload": {
            "trip_id": "trip-100",
            "proposal_id": "proposal-123",
            "nested": {"flag": True, "items": [1, 2, 3]},
        },
    }
    workspace_state: dict[str, object] = {}

    persist_tpp_result(workspace_state, original_payload)
    snapshot_before_mutation = json.dumps(workspace_state["tpp_result"], sort_keys=True)

    # Mutate caller's nested structures.
    original_payload["result_payload"]["nested"]["flag"] = False
    original_payload["result_payload"]["nested"]["items"].append(4)

    snapshot_after_mutation = json.dumps(workspace_state["tpp_result"], sort_keys=True)
    assert snapshot_before_mutation == snapshot_after_mutation


def test_load_tpp_result_returns_independent_copy() -> None:
    original_result = {
        "execution_status": {"state": "succeeded", "terminal": True},
        "result_payload": {
            "trip_id": "trip-100",
            "proposal_id": "proposal-123",
            "nested": {"items": [1, 2, 3]},
        },
    }
    workspace_state: dict[str, object] = {}
    persist_tpp_result(workspace_state, original_result)

    rehydrated = load_tpp_result(workspace_state)
    assert rehydrated is not None
    rehydrated["result_payload"]["nested"]["items"].append(99)

    # Mutating the loaded copy must not affect the persisted snapshot.
    second_load = load_tpp_result(workspace_state)
    assert second_load is not None
    assert second_load["result_payload"]["nested"]["items"] == [1, 2, 3]
