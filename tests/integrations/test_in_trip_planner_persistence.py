"""The typed planner entry point keeps one canonical decision, scenario, and turn."""

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier

from tests.app.test_policy_sync_route import _business_trip
from tests.orchestration.test_in_trip import _load_event
from tests.restart_harness import (
    clear_inter_app_restart_caches,
    sequential_restart_clients,
)
from trip_planner.app.services import planner, policy
from trip_planner.integrations.tpp import TPPResponseEnvelope


def _checked(response):
    assert response.is_success, response.text
    return response.json()


def _revision_and_turn(client, trip_id, event_id):
    workspace = _checked(client.get(f"/api/workspace/{trip_id}"))
    planner = _checked(client.get(f"/api/planner/{trip_id}/session"))
    revisions = [
        row
        for row in workspace["saved_scenarios"]
        if row["versions"][0]["label"] == "in_trip_revision"
    ]
    turns = [
        block["metadata"]
        for message in planner["messages"]
        for block in message["structured_blocks"]
        if block["kind"] == "in_trip_turn" and block["metadata"]["trigger_event_id"] == event_id
    ]
    assert len(revisions) == len(turns) == 1
    activity_id = turns[0]["activity_event_id"]
    activities = [
        row for row in workspace["activity_log"] if row["activity_event_id"] == activity_id
    ]
    assert len(activities) == 1
    decisions = [
        row
        for row in workspace["session"]["pending_decisions"]
        if row["decision_id"] == activities[0]["related_decision_id"]
    ]
    assert len(decisions) == 1 and decisions[0]["blocking"]
    return revisions[0], turns[0], workspace["session"]["current_saved_scenario_id"]


def _submit_concurrently(client, path, event, monkeypatch):
    barrier = Barrier(2)

    persist = planner.persist_in_trip_event

    def reach_writer_together(*args, **kwargs):
        barrier.wait(timeout=5)
        return persist(*args, **kwargs)

    with monkeypatch.context() as concurrent:
        concurrent.setattr(planner, "persist_in_trip_event", reach_writer_together)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = [pool.submit(client.post, path, json=event.to_dict()) for _ in range(2)]
            return [_checked(response.result(timeout=10)) for response in responses]


def test_typed_closure_deduplicates_concurrent_requests_and_survives_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("TPP_ORGANIZATION_ID", "org-acme")
    monkeypatch.setenv("TPP_BASE_URL", "http://tpp.invalid")
    monkeypatch.setenv("TPP_ACCESS_TOKEN", "test-token-long-enough")
    fixture = Path("tests/fixtures/integrations/tpp/policy/standard_policy_sync.json")
    policy_response = json.loads(fixture.read_text())["response"]

    def fixture_policy(request, _response, *, trip_plan_payload):
        assert trip_plan_payload
        return TPPResponseEnvelope.from_dict(
            {
                **policy_response,
                "request_id": request.request_id,
                "correlation_id": request.correlation_id.to_dict(),
            }
        )

    monkeypatch.setattr(policy, "_resolve_policy_response", fixture_policy)
    with sequential_restart_clients(
        tmp_path / "in-trip.sqlite", monkeypatch, email="in-trip-owner@example.test"
    ) as (clients, lifecycle):
        with clients() as writer:
            trip_id = _business_trip(writer)
            _checked(writer.post(f"/api/workspace/{trip_id}/policy/sync", json={}))
            workspace = _checked(writer.get(f"/api/workspace/{trip_id}"))
            policy_before = workspace["policy_state"]
            assert policy_before["constraint_set"]["policy_id"] == "policy-standard-2026-02"
            session = workspace["session"]
            original_id = session["current_saved_scenario_id"]
            original = next(
                row
                for row in workspace["saved_scenarios"]
                if row["saved_scenario_id"] == original_id
            )
            event = replace(
                _load_event("closure_driven_replan.json"),
                trip_id=trip_id,
                session_state_id=session["session_state_id"],
                affected_saved_scenario_id=original_id,
                affected_checkpoint_id=session["current_checkpoint_id"],
            )
            path = f"/api/planner/{trip_id}/in-trip-events"
            results = _submit_concurrently(writer, path, event, monkeypatch)
            assert results[0]["messages"] == results[1]["messages"]
            revision, turn, active_id = _revision_and_turn(writer, trip_id, event.trigger_event_id)
            assert active_id == original_id
            assert revision["versions"][0]["based_on_version_id"] == original["current_version_id"]
            assert turn["saved_scenario_id"] == revision["saved_scenario_id"]
            assert turn["planner_turn"]["workflow_state"]["current_stage"] == "replanning"
        clear_inter_app_restart_caches(lifecycle)
        with clients(reload=True) as reader:
            assert _revision_and_turn(reader, trip_id, event.trigger_event_id) == (
                revision,
                turn,
                original_id,
            )
            assert (
                _checked(reader.get(f"/api/workspace/{trip_id}"))["policy_state"] == policy_before
            )
            replays = _submit_concurrently(reader, path, event, monkeypatch)
            assert replays[0]["messages"] == replays[1]["messages"] == results[0]["messages"]
            conflicting_event = replace(event, summary="Different closure with the same ID")
            assert reader.post(path, json=conflicting_event.to_dict()).status_code == 409
            assert _revision_and_turn(reader, trip_id, event.trigger_event_id) == (
                revision,
                turn,
                original_id,
            )
        assert lifecycle == [
            "first_started",
            "first_closed",
            "caches_cleared",
            "second_started",
            "second_closed",
        ]
