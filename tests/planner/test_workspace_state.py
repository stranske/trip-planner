from __future__ import annotations

import json
from typing import Any

import pytest

from trip_planner.integrations.tpp.services.workspace_state import (
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
    # Mutating the caller's payload after persisting must not leak into workspace state.
    # (The reverse direction — mutating the persisted snapshot leaking into the caller —
    # is covered by ``test_load_tpp_result_returns_independent_copy`` below.)
    original_payload: dict[str, Any] = {
        "execution_status": {"state": "succeeded", "terminal": True},
        "result_payload": {
            "trip_id": "trip-100",
            "proposal_id": "proposal-123",
            "nested": {"flag": True, "items": [1, 2, 3]},
        },
    }
    workspace_state: dict[str, Any] = {}

    persist_tpp_result(workspace_state, original_payload)
    snapshot_before_mutation = json.dumps(workspace_state["tpp_result"], sort_keys=True)

    # Mutate caller's nested structures.
    original_payload["result_payload"]["nested"]["flag"] = False
    original_payload["result_payload"]["nested"]["items"].append(4)

    snapshot_after_mutation = json.dumps(workspace_state["tpp_result"], sort_keys=True)
    assert snapshot_before_mutation == snapshot_after_mutation


def test_persist_tpp_result_isolates_nested_mutations() -> None:
    payload: dict[str, Any] = {
        "result_payload": {"nested": {"status": "ok", "count": 1}},
    }
    workspace_state: dict[str, Any] = {}

    persist_tpp_result(workspace_state, payload)
    persisted = workspace_state["tpp_result"]

    # Persisted payload should not share nested references with caller payload.
    assert persisted["result_payload"] is not payload["result_payload"]
    assert persisted["result_payload"]["nested"] is not payload["result_payload"]["nested"]

    payload["result_payload"]["nested"]["status"] = "changed"
    payload["result_payload"]["nested"]["count"] = 2

    assert persisted["result_payload"]["nested"] == {"status": "ok", "count": 1}


def test_load_tpp_result_returns_independent_copy() -> None:
    original_result: dict[str, Any] = {
        "execution_status": {"state": "succeeded", "terminal": True},
        "result_payload": {
            "trip_id": "trip-100",
            "proposal_id": "proposal-123",
            "nested": {"items": [1, 2, 3]},
        },
    }
    workspace_state: dict[str, Any] = {}
    persist_tpp_result(workspace_state, original_result)

    rehydrated = load_tpp_result(workspace_state)
    assert rehydrated is not None
    rehydrated["result_payload"]["nested"]["items"].append(99)

    # Mutating the loaded copy must not affect the persisted snapshot.
    second_load = load_tpp_result(workspace_state)
    assert second_load is not None
    assert second_load["result_payload"]["nested"]["items"] == [1, 2, 3]


def test_load_tpp_result_isolates_nested_mutations() -> None:
    workspace_state: dict[str, Any] = {
        "tpp_result": {"result_payload": {"nested": {"items": [1, 2, 3]}}}
    }

    loaded = load_tpp_result(workspace_state)
    assert loaded is not None

    # Loaded payload should not share nested references with persisted state.
    assert loaded["result_payload"] is not workspace_state["tpp_result"]["result_payload"]
    assert (
        loaded["result_payload"]["nested"]
        is not workspace_state["tpp_result"]["result_payload"]["nested"]
    )

    loaded["result_payload"]["nested"]["items"].append(4)

    assert workspace_state["tpp_result"]["result_payload"]["nested"]["items"] == [1, 2, 3]


def test_round_trip_with_nested_lists() -> None:
    original_items = [{"id": "a"}, {"id": "b"}]
    payload: dict[str, Any] = {
        "result_payload": {"nested": {"items": original_items}},
    }
    workspace_state: dict[str, Any] = {}

    persist_tpp_result(workspace_state, payload)
    loaded = load_tpp_result(workspace_state)
    assert loaded is not None

    # Round-tripped list and its nested dict elements should be detached copies.
    assert (
        loaded["result_payload"]["nested"]["items"]
        is not payload["result_payload"]["nested"]["items"]
    )
    assert (
        loaded["result_payload"]["nested"]["items"][0]
        is not payload["result_payload"]["nested"]["items"][0]
    )

    loaded["result_payload"]["nested"]["items"].append({"id": "c"})
    loaded["result_payload"]["nested"]["items"][0]["id"] = "changed"

    assert payload["result_payload"]["nested"]["items"] == [{"id": "a"}, {"id": "b"}]
