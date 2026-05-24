import json
import os

from trip_planner.observability.langsmith_fleet import (
    PlannerFleetContext,
    build_langsmith_run_config,
    build_planner_fleet_records,
    ensure_langsmith_project_defaults,
    write_fleet_records,
)


def test_langsmith_defaults_are_noop_without_secret(monkeypatch):
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    monkeypatch.delenv("LANGCHAIN_PROJECT", raising=False)
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)

    assert ensure_langsmith_project_defaults() is False
    assert "LANGCHAIN_TRACING_V2" not in os.environ
    assert (
        build_langsmith_run_config(
            context=PlannerFleetContext(run_id="run-1", session_id="session-1", trip_id="trip-1"),
            metadata={"task_class": "first_turn_triage"},
        )
        is None
    )


def test_langsmith_config_hashes_trip_id_and_sets_project_defaults(monkeypatch):
    monkeypatch.setenv("LANGSMITH_API_KEY", "secret-test-key")
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    monkeypatch.delenv("LANGCHAIN_PROJECT", raising=False)
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)

    config = build_langsmith_run_config(
        context=PlannerFleetContext(
            run_id="run-1",
            session_id="session-1",
            trip_id="trip-private",
            planning_mode="collaborative",
            provider="openai",
            model="gpt-test",
        ),
        metadata={"task_class": "route_comparison", "plan_maturity": "coherent_plan"},
    )

    assert config is not None
    assert config["metadata"]["trip_id_hash"] != "trip-private"
    assert config["metadata"]["provider"] == "openai"
    assert config["metadata"]["model"] == "gpt-test"
    assert "planning_mode:collaborative" in config["tags"]
    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    assert os.environ["LANGCHAIN_PROJECT"] == "trip-planner"
    assert os.environ["LANGCHAIN_API_KEY"] == "secret-test-key"


def test_planner_fleet_record_summarizes_domain_metadata_without_raw_payload(monkeypatch):
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    context = PlannerFleetContext(
        run_id="run-2",
        session_id="session-private",
        trip_id="trip-private",
        planning_mode="delegated",
        provider="openai",
        model="gpt-test",
        trace_id="trace-1",
    )

    records = build_planner_fleet_records(
        context=context,
        runtime_mode="fallback",
        turn_metadata={
            "task_class": "planning_synthesis",
            "plan_maturity": "coherent_plan",
            "provider_state": "fallback",
            "fallback_reason": "missing_model_config",
        },
        tool_calls=[
            {"tool_name": "refresh_inventory", "status": "completed", "mutates_state": False},
            {"tool_name": "update_budget_plan", "status": "completed", "mutates_state": True},
        ],
        context_readiness={
            "status": "partial",
            "missing_sections": ["policy_state", "raw traveler note: private details"],
        },
        artifact_ref="artifacts/langsmith/langsmith-fleet.ndjson",
    )

    assert len(records) == 1
    record = records[0]
    assert record["status"] == "no_secret"
    assert record["trace_id"] == "trace-1"
    assert record["domain"]["planner_action"] == "planning_synthesis"
    assert record["domain"]["inventory_usage"] == "used"
    assert record["domain"]["budget_constraint_status"] == "used"
    assert record["domain"]["mutating_tool_call_count"] == 1
    assert record["domain"]["context_readiness_status"] == "partial"
    assert record["domain"]["missing_context_sections"] == ["policy_state", "other"]
    serialized = json.dumps(record)
    assert "trip-private" not in serialized
    assert "session-private" not in serialized
    assert "raw traveler note: private details" not in serialized
    assert record["domain"]["fallback_state"] == "missing_model_config"


def test_write_fleet_records_uses_deterministic_ndjson(tmp_path):
    path = tmp_path / "langsmith-fleet.ndjson"
    write_fleet_records(
        path,
        [
            {
                "schema_version": "langsmith-fleet/v1",
                "repo": "stranske/trip-planner",
                "status": "no_secret",
            }
        ],
    )

    assert path.read_text(encoding="utf-8") == (
        '{"repo":"stranske/trip-planner","schema_version":"langsmith-fleet/v1",'
        '"status":"no_secret"}\n'
    )
