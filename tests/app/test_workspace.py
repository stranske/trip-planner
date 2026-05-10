from collections.abc import Iterator
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from trip_planner.app.main import create_app
from trip_planner.app.services.auth import AuthenticatedUser, create_account
from trip_planner.app.services.feasibility import (
    build_feasibility_planner_outputs,
    build_feasibility_summary_payload,
)
from trip_planner.app.services import proposal as proposal_service
from trip_planner.app.services.scenarios import _runtime_business_profile
from trip_planner.app.services.trips import create_trip
from trip_planner.app.services import workspace as workspace_service
from trip_planner.app.services.workspace import get_workspace_payload
from trip_planner.integrations.tpp import TPPTransportError
from trip_planner.options import InventoryBundle
from trip_planner.persistence.db import (
    ensure_database_ready,
    get_session_factory,
    reset_database_state,
)
from trip_planner.persistence.models.activity import PersistedPlannerAction
from trip_planner.persistence.models.policy import PersistedPolicyState
from trip_planner.persistence.models.trip import PersistedTrip

_LEGACY_FIXTURE_BUNDLE_IDS = {
    "bundle-osaka-gateway",
    "bundle-kyoto-culture-day",
    "bundle-osaka-arrival",
}
_FIXTURE_ADAPTER_MARKERS = {
    "PersistedTripInventoryFixtureAdapter",
    "persisted-trip-fixture-inventory",
    "urban-historian",
    "client_meeting_profile",
    "policy_round_trip_exception",
    "Kyoto ranked scenario workspace",
    "Client summit ranked scenarios",
}


def _assert_payload_avoids_fixture_or_default_inventory_data(payload: dict[str, Any]) -> None:
    bundle_ids = {bundle["bundle_id"] for bundle in payload["inventory_summary"]["bundles"]}
    assert bundle_ids.isdisjoint(_LEGACY_FIXTURE_BUNDLE_IDS)

    serialized_payload = json.dumps(payload, sort_keys=True).lower()
    for marker in _FIXTURE_ADAPTER_MARKERS:
        assert marker.lower() not in serialized_payload
    for seeded_trip_id in ("trip-leisure-kyoto-draft", "trip-business-client-summit"):
        assert seeded_trip_id not in serialized_payload


def _assert_runtime_ranking_and_route_comparison(payload: dict[str, Any]) -> None:
    assert payload["ranking"]["rows"]
    assert (
        payload["ranking"]["lead_scenario_id"]
        == payload["scenario_search"]["scenarios"][0]["scenario_id"]
    )
    assert payload["ranking"]["rows"][0]["scenario_id"] == payload["ranking"]["lead_scenario_id"]
    assert payload["ranking"]["source_refs"]
    assert payload["route_comparison"] == payload["runtime_scenario_comparison"]
    assert (
        payload["route_comparison"]["lead_scenario_id"]
        == payload["scenario_search"]["scenarios"][0]["scenario_id"]
    )
    assert payload["route_comparison"]["scenarios"]
    assert payload["route_comparison"]["source_refs"]


def test_runtime_business_profile_normalizes_punctuated_regions_to_home_airports() -> None:
    profile = _runtime_business_profile(
        trip_title="Kyoto kickoff",
        primary_regions=("Kyoto, Japan",),
        traveler_party_kind="team",
    )

    assert profile.traveler_context.home_airport == "KIX"


def test_runtime_business_profile_uses_valid_default_home_airport_for_unknown_regions() -> None:
    profile = _runtime_business_profile(
        trip_title="Regional kickoff",
        primary_regions=("Remote client campus",),
        traveler_party_kind=None,
    )

    assert profile.traveler_context.home_airport == "ORD"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'workspace.db'}")
    reset_database_state()
    ensure_database_ready()
    app = create_app()

    with TestClient(app) as test_client:
        test_client.post(
            "/api/auth/signup",
            json={
                "email": "workspace@example.com",
                "password": "password123",
                "display_name": "Workspace Owner",
            },
        )
        yield test_client

    reset_database_state()


def test_workspace_endpoint_returns_trip_scenario_payload(client: TestClient) -> None:
    response = client.get("/api/workspace/trip-leisure-kyoto-draft")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trip_record"]["trip"]["trip_id"] == "trip-leisure-kyoto-draft"
    assert payload["session"]["selected_planning_mode"] == "collaborative"
    _assert_runtime_ranking_and_route_comparison(payload)
    assert payload["session"]["current_saved_scenario_id"] == "saved-scenario:kyoto-baseline"
    assert payload["scenario_search"]["title"] == "Kyoto ranked scenario workspace"
    assert payload["scenario_search"]["scenarios"][0]["title"] == "Kyoto cultural anchor"
    assert payload["scenario_search"]["scenarios"][0]["scenario_summary"]["route_sequence"] == [
        "dest-city-osaka",
        "dest-city-kyoto",
    ]
    assert payload["inventory_summary"]["bundle_count"] == 2
    assert payload["inventory_summary"]["bundles"][0]["title"] == "Osaka arrival buffer"
    assert payload["feasibility_summary"]["assessment_count"] == 2
    assert payload["feasibility_summary"]["attention_bundle_count"] == 2
    assert payload["planner_panel_state"]["outputs"][0]["output_id"].endswith(
        ":feasibility-summary"
    )
    assert payload["planner_panel_state"]["outputs"][0]["tags"][0] == "feasibility"
    assert payload["planner_panel_state"]["outputs"][3]["title"] == "Scenario ranking summary"
    assert payload["planner_panel_state"]["outputs"][4]["title"].startswith("Rank #1 ")
    assert (
        payload["runtime_scenario_comparison"]["lead_scenario_id"]
        == payload["scenario_search"]["scenarios"][0]["scenario_id"]
    )
    assert payload["runtime_state"]["status"] == "ready"
    assert payload["inventory_summary"]["runtime_state"]["status"] == "ready"
    assert payload["runtime_scenario_comparison"]["comparison_axes"][-1]["key"] == "estimated_total"
    assert payload["runtime_scenario_comparison"]["scenarios"][0]["delta"]["transfers_delta"] == 0
    assert payload["runtime_scenario_comparison"]["scenarios"][0]["route_summary"] == (
        "dest-city-osaka -> dest-city-kyoto"
    )
    assert payload["planner_panel_state"]["trip"]["trip_id"] == "trip-leisure-kyoto-draft"
    assert payload["planner_panel_state"]["option_set"]["options"][0]["option_id"].startswith(
        "scenario:"
    )
    assert payload["activity_log"] == []
    assert payload["planner_panel_state"]["pending_decisions"][0]["choices"] == [
        "save baseline",
        "keep exploring",
    ]
    assert payload["budget_state"]["summary"]["planned_total"] > 0
    assert payload["budget_state"]["summary"]["actual_total"] > 0
    assert payload["budget_state"]["summary"]["current_scenario_title"]


def test_workspace_planning_mode_route_persists_mode(client: TestClient) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Planning mode workshop",
            "summary": "Persist the selected planner mode.",
            "mode": "leisure",
            "trip_frame": {
                "start_date": "2026-06-04",
                "end_date": "2026-06-07",
                "duration_days": 4,
                "primary_regions": ["Lisbon"],
            },
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]

    updated = client.put(
        f"/api/workspace/{trip_id}/planning-mode",
        json={"planning_mode": "revealed-preference"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["session"]["selected_planning_mode"] == "revealed-preference"

    reloaded = client.get(f"/api/workspace/{trip_id}")
    assert reloaded.status_code == 200
    assert reloaded.json()["session"]["selected_planning_mode"] == "revealed-preference"

    rejected = client.put(
        f"/api/workspace/{trip_id}/planning-mode",
        json={"planning_mode": "solo-auto"},
    )
    assert rejected.status_code == 400


def test_workspace_planning_ledger_api_persists_entries_across_reload(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Ledger workshop",
            "summary": "Persist trip planning decisions and questions.",
            "mode": "leisure",
            "trip_frame": {
                "start_date": "2026-06-04",
                "end_date": "2026-06-07",
                "duration_days": 4,
                "primary_regions": ["Lisbon"],
            },
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]

    saved = client.post(
        f"/api/workspace/{trip_id}/planning-ledger",
        json={
            "item_type": "open_question",
            "category": "lodging",
            "summary": "Should the apartment be near Baixa or Alfama?",
            "detail": "Traveler wants quieter evenings but quick transit.",
        },
    )
    assert saved.status_code == 200, saved.text
    entry = saved.json()
    assert entry["status"] == "active"
    assert entry["ledger_entry_id"].startswith("ledger:")
    assert len(entry["ledger_entry_id"]) <= 64
    assert trip_id not in entry["ledger_entry_id"]

    patched = client.patch(
        f"/api/workspace/{trip_id}/planning-ledger/{entry['ledger_entry_id']}",
        json={
            "status": "completed",
            "related_option_id": "option:lisbon-central",
            "related_decision_id": "decision:lodging-area",
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["status"] == "completed"
    assert patched.json()["related_option_id"] == "option:lisbon-central"
    assert patched.json()["related_decision_id"] == "decision:lodging-area"

    reloaded = client.get(f"/api/workspace/{trip_id}")
    assert reloaded.status_code == 200
    ledger_entries = reloaded.json()["planning_ledger"]["entries"]
    assert ledger_entries[0]["summary"] == "Should the apartment be near Baixa or Alfama?"
    assert ledger_entries[0]["status"] == "completed"
    assert ledger_entries[0]["related_option_id"] == "option:lisbon-central"
    assert ledger_entries[0]["related_decision_id"] == "decision:lodging-area"


def test_route_option_actions_create_durable_ledger_history(client: TestClient) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Ledger route trip",
            "summary": "Track rejected route options.",
            "mode": "leisure",
            "trip_frame": {
                "start_date": "2026-06-04",
                "end_date": "2026-06-07",
                "duration_days": 4,
                "primary_regions": ["Lisbon"],
            },
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]
    response = client.get(f"/api/workspace/{trip_id}")
    assert response.status_code == 200
    scenario_id = response.json()["route_comparison"]["scenarios"][1]["scenario_id"]

    updated = client.post(
        f"/api/workspace/{trip_id}/route-options/{scenario_id}/action",
        json={"action_type": "reject"},
    )

    assert updated.status_code == 200, updated.text
    ledger = updated.json()["planning_ledger"]
    assert ledger["summary"]["rejected_options"]
    assert ledger["summary"]["rejected_options"][0]["related_option_id"] == scenario_id

    reloaded = client.get(f"/api/workspace/{trip_id}")
    assert reloaded.status_code == 200
    assert reloaded.json()["planning_ledger"]["summary"]["rejected_options"][0][
        "related_option_id"
    ] == scenario_id


def test_planner_turn_extracts_constraints_into_planning_ledger(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Planner ledger trip",
            "summary": "Capture planner turn signals.",
            "mode": "leisure",
            "trip_frame": {
                "start_date": "2026-07-01",
                "end_date": "2026-07-06",
                "duration_days": 6,
                "primary_regions": ["Kyoto"],
            },
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]

    turn = client.post(
        f"/api/planner/{trip_id}/turns",
        json={
            "message": (
                "Remember we need a hotel near transit; budget should stay under 3500. "
                "Maybe add a quiet food-focused day?"
            )
        },
    )
    assert turn.status_code == 200, turn.text
    planner_payload = turn.json()
    planner_ledger_summary = planner_payload["planning_ledger"]["summary"]
    assert planner_ledger_summary["constraints"]
    planner_reply = planner_payload["messages"][-1]
    assert "Planning ledger remembers" in planner_reply["content"]
    structured_kinds = {block["kind"] for block in planner_reply["structured_blocks"]}
    assert "planning_ledger" in structured_kinds

    reloaded = client.get(f"/api/workspace/{trip_id}")
    assert reloaded.status_code == 200
    ledger_summary = reloaded.json()["planning_ledger"]["summary"]
    assert ledger_summary["constraints"]
    assert ledger_summary["open_questions"]


def test_workspace_endpoint_surfaces_business_ranked_scenarios(client: TestClient) -> None:
    response = client.get("/api/workspace/trip-business-client-summit")

    assert response.status_code == 200
    payload = response.json()
    _assert_runtime_ranking_and_route_comparison(payload)
    assert payload["scenario_search"]["title"] == "Client summit ranked scenarios"
    assert payload["scenario_search"]["scenarios"][0]["title"] == "Airport arrival bundle"
    assert (
        payload["runtime_scenario_comparison"]["lead_scenario_id"]
        == payload["runtime_scenario_comparison"]["scenarios"][0]["scenario_id"]
    )
    assert payload["runtime_scenario_comparison"]["scenarios"][0]["status"] == "fallback"
    assert payload["planner_panel_state"]["outputs"][2]["title"] == "Scenario ranking summary"
    assert payload["planner_panel_state"]["outputs"][3]["title"] == "Rank #1 Airport arrival bundle"
    assert (
        payload["planner_panel_state"]["option_set"]["options"][0]["label"]
        == "Airport arrival bundle"
    )


def test_workspace_scenario_comparison_endpoint_returns_runtime_surface(
    client: TestClient,
) -> None:
    response = client.get("/api/workspace/trip-leisure-kyoto-draft/scenarios/compare")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trip_id"] == "trip-leisure-kyoto-draft"
    assert payload["comparison_axes"][0]["key"] == "score"
    assert payload["comparison_axes"][-1]["key"] == "estimated_total"
    assert payload["scenarios"][0]["delta"]["transfers_delta"] == 0
    assert payload["lead_scenario_id"] == payload["scenarios"][0]["scenario_id"]
    assert payload["scenarios"][0]["map_view"]["active_scope"] == "regional"
    assert payload["scenarios"][0]["map_view"]["active_route_option_id"] == payload["scenarios"][0][
        "scenario_id"
    ]
    assert "provider" in payload["scenarios"][0]["map_diagnostics"]
    assert "provider" not in payload["scenarios"][0]["map_view"]
    assert "runtime scenario" in payload["summary"].lower()


def test_workspace_endpoint_returns_not_found_for_unknown_trip(
    client: TestClient,
) -> None:
    response = client.get("/api/workspace/trip-unknown")

    assert response.status_code == 404

    comparison_response = client.get("/api/workspace/trip-unknown/scenarios/compare")

    assert comparison_response.status_code == 404


def test_workspace_openapi_documents_inventory_runtime_state_issue_schema() -> None:
    app = create_app()
    openapi_payload = app.openapi()
    schemas = openapi_payload["components"]["schemas"]
    workspace_schema = schemas["WorkspaceResponse"]
    inventory_ref = workspace_schema["properties"]["inventory_summary"]["$ref"]
    inventory_schema = schemas[inventory_ref.rsplit("/", maxsplit=1)[-1]]

    runtime_state_ref = inventory_schema["properties"]["runtime_state"]["$ref"]
    runtime_state_schema = schemas[runtime_state_ref.rsplit("/", maxsplit=1)[-1]]
    assert runtime_state_schema["properties"]["issues"]["type"] == "array"

    issue_ref = runtime_state_schema["properties"]["issues"]["items"]["$ref"]
    issue_schema = schemas[issue_ref.rsplit("/", maxsplit=1)[-1]]
    assert issue_schema["properties"]["code"]["anyOf"]
    assert issue_schema["properties"]["reason"]["anyOf"]
    assert issue_schema["properties"]["message"]["anyOf"]


def test_workspace_endpoint_bootstraps_persisted_workspace_scaffolding_for_business_trip(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Chicago kickoff",
            "summary": "Get into the workspace quickly.",
            "mode": "business",
            "trip_frame": {
                "start_date": "2026-05-04",
                "end_date": "2026-05-06",
                "duration_days": 3,
                "primary_regions": ["Chicago"],
                "traveler_party": {
                    "kind": "team",
                    "traveler_count": 3,
                    "notes": "Customer kickoff",
                },
            },
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]

    response = client.get(f"/api/workspace/{trip_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trip_record"]["trip"]["trip_id"] == trip_id
    assert payload["trip_record"]["trip"]["title"] == "Chicago kickoff"
    assert payload["trip_record"]["artifact_refs"]["session_state_id"] == f"session:{trip_id}"
    assert payload["session"]["trip_id"] == trip_id
    assert (
        payload["session"]["current_saved_scenario_id"]
        == payload["saved_scenarios"][0]["saved_scenario_id"]
    )
    assert payload["session"]["pending_decisions"][0]["decision_id"].startswith("decision:")
    assert len(payload["saved_scenarios"]) == 2
    lead_saved_scenario_id = payload["saved_scenarios"][0]["saved_scenario_id"]
    assert payload["saved_scenarios"][0]["versions"][0]["label"] == "baseline"
    assert payload["saved_scenarios"][1]["versions"][0]["label"] == "fallback"
    assert payload["scenario_comparison"]["baseline_scenario_id"] == lead_saved_scenario_id
    assert payload["runtime_state"]["status"] == "ready"
    assert payload["inventory_summary"]["runtime_state"]["status"] == "ready"
    assert payload["inventory_summary"]["bundle_count"] > 0
    assert payload["inventory_summary"]["bundles"][0]["option_count"] > 0
    assert len(payload["scenario_search"]["scenarios"]) > 0
    assert payload["scenario_search"]["scenarios"][0]["scenario_id"].startswith("scenario:")
    assert payload["scenario_search"]["source_refs"]
    _assert_runtime_ranking_and_route_comparison(payload)
    assert payload["runtime_scenario_comparison"]["lead_scenario_id"].startswith("scenario:")
    assert len(payload["runtime_scenario_comparison"]["scenarios"]) > 0
    assert payload["runtime_scenario_comparison"]["source_refs"]
    assert "->" in payload["runtime_scenario_comparison"]["scenarios"][0]["route_summary"]
    assert all(
        seeded_id not in payload["trip_record"]["trip"]["trip_id"]
        for seeded_id in ("trip-leisure-kyoto-draft", "trip-business-client-summit")
    )
    assert payload["feasibility_summary"]["assessment_count"] > 0
    assert payload["activity_log"] == []
    assert payload["budget_state"]["summary"]["planned_total"] == 0
    assert payload["budget_state"]["summary"]["actual_total"] == 0
    assert payload["budget_state"]["summary"]["has_budget_plan"] is False
    assert payload["planner_panel_state"]["trip"]["trip_id"] == trip_id
    assert payload["planner_panel_state"]["option_set"]["purpose"] == "workspace_review"
    planner_output_titles = [item["title"] for item in payload["planner_panel_state"]["outputs"]]
    assert "Scenario ranking summary" in planner_output_titles
    assert payload["policy_state"] is None
    assert payload["proposal_state"] is None

    scenario_history = client.get(f"/api/trips/{trip_id}/scenario-history")
    assert scenario_history.status_code == 200
    history_payload = scenario_history.json()
    assert len(history_payload["saved_scenarios"]) == 2
    assert (
        history_payload["planning_sessions"][0]["current_saved_scenario_id"]
        == payload["session"]["current_saved_scenario_id"]
    )


def test_workspace_endpoint_bootstraps_persisted_workspace_scaffolding_for_leisure_trip(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Lisbon weekend",
            "summary": "Bootstrap a new leisure workspace.",
            "mode": "leisure",
            "trip_frame": {
                "start_date": "2026-06-04",
                "end_date": "2026-06-07",
                "duration_days": 4,
                "primary_regions": ["Lisbon"],
            },
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]

    payload = client.get(f"/api/workspace/{trip_id}").json()

    assert payload["runtime_state"]["status"] == "ready"
    assert payload["saved_scenarios"][0]["versions"][0]["title"].startswith("Lisbon")
    assert payload["inventory_summary"]["bundle_count"] > 0
    assert payload["scenario_search"]["scenarios"]
    _assert_runtime_ranking_and_route_comparison(payload)
    assert payload["scenario_search"]["title"] == "Lisbon weekend runtime scenarios"
    assert payload["scenario_search"]["source_refs"]
    assert payload["runtime_scenario_comparison"]["lead_scenario_id"].startswith("scenario:")
    assert payload["runtime_scenario_comparison"]["scenarios"][0]["scenario_id"].startswith(
        "scenario:"
    )
    assert payload["runtime_scenario_comparison"]["source_refs"]
    assert "->" in payload["runtime_scenario_comparison"]["scenarios"][0]["route_summary"]
    assert all(
        seeded_id not in payload["trip_record"]["trip"]["trip_id"]
        for seeded_id in ("trip-leisure-kyoto-draft", "trip-business-client-summit")
    )
    assert payload["planner_panel_state"]["option_set"]["purpose"] == "workspace_review"
    assert payload["planner_memory"]["current_checkpoint_id"] is None


def test_workspace_endpoint_creates_non_seeded_persisted_leisure_trip_with_runtime_frame(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Lisbon solo long weekend",
            "summary": "Create a persisted leisure trip from runtime context.",
            "mode": "leisure",
            "trip_frame": {
                "start_date": "2026-07-18",
                "end_date": "2026-07-21",
                "duration_days": 4,
                "primary_regions": ["Lisbon"],
                "traveler_party": {
                    "kind": "solo",
                    "traveler_count": 1,
                    "notes": "Prioritize museums and walkable neighborhoods.",
                },
            },
        },
    )
    assert created.status_code == 201

    trip = created.json()["trip"]
    trip_id = trip["trip_id"]
    assert trip_id
    assert all(
        seeded_id not in trip_id
        for seeded_id in ("trip-leisure-kyoto-draft", "trip-business-client-summit")
    )
    assert trip["trip_frame"]["primary_regions"] == ["Lisbon"]
    assert trip["trip_frame"]["start_date"] == "2026-07-18"
    assert trip["trip_frame"]["end_date"] == "2026-07-21"
    assert trip["trip_frame"]["traveler_party"]["kind"] == "solo"
    assert trip["trip_frame"]["traveler_party"]["traveler_count"] == 1

    workspace = client.get(f"/api/workspace/{trip_id}")
    assert workspace.status_code == 200
    workspace_payload = workspace.json()
    workspace_trip = workspace_payload["trip_record"]["trip"]
    assert workspace_trip["trip_id"] == trip_id
    assert workspace_trip["trip_frame"]["primary_regions"] == ["Lisbon"]
    assert workspace_trip["trip_frame"]["start_date"] == "2026-07-18"
    assert workspace_trip["trip_frame"]["end_date"] == "2026-07-21"
    assert workspace_trip["trip_frame"]["traveler_party"]["kind"] == "solo"
    assert workspace_trip["trip_frame"]["traveler_party"]["traveler_count"] == 1
    assert isinstance(workspace_payload["inventory_summary"]["bundle_count"], int)
    assert workspace_payload["inventory_summary"]["bundle_count"] > 0
    assert workspace_payload["scenario_comparison"] is not None
    assert workspace_payload["scenario_comparison"]["baseline_scenario_id"]
    assert workspace_payload["scenario_comparison"]["candidate_scenario_id"]
    runtime_comparison = workspace_payload["runtime_scenario_comparison"]
    runtime_scenarios = runtime_comparison["scenarios"]
    assert runtime_scenarios
    for scenario in runtime_scenarios:
        assert scenario["scenario_id"]
        assert scenario["metrics"]["estimated_total"] is not None
        assert any(
            scenario["metrics"][key] is not None for key in ("score", "travel_minutes", "transfers")
        )
    source_metadata = workspace_payload["inventory_summary"]["source_metadata"]
    assert source_metadata["source_type"] == "persisted_trip"
    assert source_metadata["origin"] == "runtime"
    assert source_metadata["adapter_name"] == "persisted-trip-source-inventory"
    provenance_context = source_metadata["provenance_context"]
    assert provenance_context["trip_id"] == trip_id
    assert provenance_context["trip_mode"] == "leisure"
    assert provenance_context["source_id"] == "persisted-trip-runtime-source"
    assert provenance_context["query_id"] == f"inventory-query:{trip_id}"
    assert provenance_context["handoff_id"] == f"handoff:{trip_id}:inventory"
    assert provenance_context["input_record_ids"]
    assert provenance_context["issue_codes"] == []
    assert provenance_context["filters"]["trip_mode"] == "leisure"
    assert provenance_context["notes"]
    serialized_source_metadata = json.dumps(source_metadata, sort_keys=True).lower()
    for forbidden_marker in ("fixture", "seed", "demo", "persistedtripinventoryfixtureadapter"):
        assert forbidden_marker not in serialized_source_metadata


def test_workspace_endpoint_creates_non_seeded_persisted_business_trip_with_runtime_frame(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Chicago client renewal sprint",
            "summary": "Business purpose: prepare Q3 renewal strategy with client stakeholders.",
            "mode": "business",
            "trip_frame": {
                "start_date": "2026-08-11",
                "end_date": "2026-08-14",
                "duration_days": 4,
                "primary_regions": ["Chicago"],
                "traveler_party": {
                    "kind": "team",
                    "traveler_count": 4,
                    "notes": "Client workshops and executive readout.",
                },
            },
        },
    )
    assert created.status_code == 201

    trip = created.json()["trip"]
    trip_id = trip["trip_id"]
    assert trip_id
    assert all(
        seeded_id not in trip_id
        for seeded_id in ("trip-leisure-kyoto-draft", "trip-business-client-summit")
    )
    assert trip["trip_frame"]["primary_regions"] == ["Chicago"]
    assert trip["trip_frame"]["start_date"] == "2026-08-11"
    assert trip["trip_frame"]["end_date"] == "2026-08-14"
    assert trip["trip_frame"]["traveler_party"]["kind"] == "team"
    assert trip["trip_frame"]["traveler_party"]["traveler_count"] == 4
    assert "Business purpose:" in trip["summary"]

    workspace = client.get(f"/api/workspace/{trip_id}")
    assert workspace.status_code == 200
    workspace_payload = workspace.json()

    assert isinstance(workspace_payload["inventory_summary"]["bundle_count"], int)
    assert workspace_payload["inventory_summary"]["bundle_count"] > 0
    assert workspace_payload["inventory_summary"]["bundles"]

    assert workspace_payload["scenario_comparison"] is not None
    assert workspace_payload["scenario_comparison"]["baseline_scenario_id"]
    assert workspace_payload["scenario_comparison"]["candidate_scenario_id"]
    runtime_comparison = workspace_payload["runtime_scenario_comparison"]
    runtime_scenarios = runtime_comparison["scenarios"]
    assert runtime_scenarios
    for scenario in runtime_scenarios:
        assert scenario["scenario_id"]
        assert scenario["metrics"]["estimated_total"] is not None
        assert any(
            scenario["metrics"][key] is not None for key in ("score", "travel_minutes", "transfers")
        )

    budget_summary = workspace_payload["budget_state"]["summary"]
    for numeric_field in ("planned_total", "actual_total", "remaining_total"):
        assert budget_summary[numeric_field] is not None
        assert isinstance(budget_summary[numeric_field], (int, float))
    category_totals = budget_summary["category_summaries"]
    assert category_totals
    for category in category_totals:
        for numeric_field in ("planned_amount", "actual_amount", "remaining_amount"):
            assert category[numeric_field] is not None
            assert isinstance(category[numeric_field], (int, float))

    source_metadata = workspace_payload["inventory_summary"]["source_metadata"]
    assert source_metadata["source_type"] == "persisted_trip"
    assert source_metadata["origin"] == "runtime"
    assert source_metadata["adapter_name"] == "persisted-trip-source-inventory"
    provenance_context = source_metadata["provenance_context"]
    assert provenance_context["trip_id"] == trip_id
    assert provenance_context["trip_mode"] == "business"
    assert provenance_context["source_id"] == "persisted-trip-runtime-source"
    assert provenance_context["query_id"] == f"inventory-query:{trip_id}"
    assert provenance_context["handoff_id"] == f"handoff:{trip_id}:inventory"
    assert provenance_context["input_record_ids"]
    assert provenance_context["issue_codes"] == []
    assert provenance_context["filters"]["trip_mode"] == "business"
    assert provenance_context["notes"]
    serialized_source_metadata = json.dumps(source_metadata, sort_keys=True).lower()
    for forbidden_marker in ("fixture", "seed", "demo", "persistedtripinventoryfixtureadapter"):
        assert forbidden_marker not in serialized_source_metadata
    serialized_business_metadata = json.dumps(
        {"source_metadata": source_metadata, "provenance_context": provenance_context},
        sort_keys=True,
    ).lower()
    for business_fixture_marker in (
        "client_meeting_profile",
        "conference_profile",
        "site_visit_profile",
        "policy_round_trip_exception",
    ):
        assert business_fixture_marker not in serialized_business_metadata


@pytest.mark.parametrize(
    ("mode", "title", "summary", "trip_frame"),
    [
        (
            "leisure",
            "Lisbon weekend",
            "Runtime workspace should avoid fixture bundle IDs.",
            {
                "start_date": "2026-06-04",
                "end_date": "2026-06-07",
                "duration_days": 4,
                "primary_regions": ["Lisbon"],
            },
        ),
        (
            "business",
            "Chicago kickoff",
            "Runtime workspace should avoid fixture adapter identities.",
            {
                "start_date": "2026-05-04",
                "end_date": "2026-05-06",
                "duration_days": 3,
                "primary_regions": ["Chicago"],
                "traveler_party": {
                    "kind": "team",
                    "traveler_count": 3,
                    "notes": "Customer kickoff",
                },
            },
        ),
    ],
)
def test_workspace_endpoint_avoids_fixture_bundle_ids_and_fixture_adapter_markers_for_persisted_trips(
    client: TestClient,
    mode: str,
    title: str,
    summary: str,
    trip_frame: dict[str, Any],
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": title,
            "summary": summary,
            "mode": mode,
            "trip_frame": trip_frame,
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]

    response = client.get(f"/api/workspace/{trip_id}")

    assert response.status_code == 200
    payload = response.json()
    bundle_ids = {bundle["bundle_id"] for bundle in payload["inventory_summary"]["bundles"]}
    assert bundle_ids
    assert bundle_ids.isdisjoint(_LEGACY_FIXTURE_BUNDLE_IDS)

    serialized_runtime_payload = json.dumps(
        {
            "inventory_summary": payload["inventory_summary"],
            "scenario_search": payload["scenario_search"],
            "runtime_scenario_comparison": payload["runtime_scenario_comparison"],
        },
        sort_keys=True,
    )
    for marker in _FIXTURE_ADAPTER_MARKERS:
        assert marker not in serialized_runtime_payload


def test_workspace_scenario_comparison_endpoint_returns_runtime_surface_for_persisted_leisure_trip(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Lisbon weekend",
            "summary": "Comparison endpoint should use persisted runtime inputs.",
            "mode": "leisure",
            "trip_frame": {
                "start_date": "2026-06-04",
                "end_date": "2026-06-07",
                "duration_days": 4,
                "primary_regions": ["Lisbon"],
            },
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]

    response = client.get(f"/api/workspace/{trip_id}/scenarios/compare")

    assert response.status_code == 200
    payload = response.json()
    assert payload["lead_scenario_id"].startswith("scenario:")
    assert payload["title"] == "Lisbon weekend runtime scenarios"
    assert payload["scenarios"][0]["scenario_id"].startswith("scenario:")
    assert payload["scenarios"][0]["option_count"] > 0
    assert payload["scenarios"][0]["route_sequence"]
    assert payload["source_refs"]
    assert "runtime scenario" in payload["summary"].lower()


def test_workspace_scenario_comparison_endpoint_returns_runtime_surface_for_persisted_business_trip(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Chicago kickoff",
            "summary": "Comparison endpoint should use persisted runtime inputs.",
            "mode": "business",
            "trip_frame": {
                "start_date": "2026-05-04",
                "end_date": "2026-05-06",
                "duration_days": 3,
                "primary_regions": ["Chicago"],
                "traveler_party": {
                    "kind": "team",
                    "traveler_count": 3,
                    "notes": "Customer kickoff",
                },
            },
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]

    response = client.get(f"/api/workspace/{trip_id}/scenarios/compare")

    assert response.status_code == 200
    payload = response.json()
    assert payload["lead_scenario_id"].startswith("scenario:")
    assert payload["title"] == "Chicago kickoff ranked scenarios"
    assert payload["scenarios"][0]["scenario_id"].startswith("scenario:")
    assert payload["scenarios"][0]["status"] in {"recommended", "fallback", "alternative"}
    assert payload["scenarios"][0]["route_sequence"]
    assert payload["source_refs"]
    assert "runtime scenario" in payload["summary"].lower()


def test_workspace_endpoint_returns_bounded_empty_runtime_state_when_trip_frame_is_sparse(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Flexible weekend",
            "summary": "Exercise sparse persisted leisure trip inputs.",
            "mode": "leisure",
            "trip_frame": {},
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]

    initial = client.get(f"/api/workspace/{trip_id}")
    reloaded = client.get(f"/api/workspace/{trip_id}")

    assert initial.status_code == 200
    assert reloaded.status_code == 200
    initial_payload = initial.json()
    reloaded_payload = reloaded.json()
    assert initial_payload["runtime_state"]["status"] == "empty"
    assert initial_payload["inventory_summary"]["runtime_state"]["status"] == "empty"
    assert len(initial_payload["scenario_search"]["scenarios"]) == 2
    assert len(initial_payload["runtime_scenario_comparison"]["scenarios"]) == 2
    assert (
        initial_payload["scenario_search"]["scenarios"][0]["scenario_id"]
        == reloaded_payload["scenario_search"]["scenarios"][0]["scenario_id"]
    )
    assert (
        initial_payload["planner_panel_state"]["option_set"]["purpose"]
        == reloaded_payload["planner_panel_state"]["option_set"]["purpose"]
    )
    assert (
        initial_payload["runtime_scenario_comparison"]["lead_scenario_id"]
        == reloaded_payload["runtime_scenario_comparison"]["lead_scenario_id"]
    )


def test_workspace_endpoint_surfaces_partial_runtime_state_for_under_scoped_trip(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Chicago kickoff draft",
            "summary": "Primary region exists but runtime inputs are incomplete.",
            "mode": "business",
            "trip_frame": {
                "primary_regions": ["Chicago"],
            },
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]

    response = client.get(f"/api/workspace/{trip_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["runtime_state"]["status"] == "partial"
    assert payload["inventory_summary"]["runtime_state"]["status"] == "partial"
    assert len(payload["scenario_search"]["scenarios"]) == 2
    assert len(payload["runtime_scenario_comparison"]["scenarios"]) == 2

    comparison_response = client.get(f"/api/workspace/{trip_id}/scenarios/compare")

    assert comparison_response.status_code == 200
    comparison_payload = comparison_response.json()
    assert len(comparison_payload["scenarios"]) == 2
    assert comparison_payload["lead_scenario_id"].startswith("saved-scenario:")
    assert "runtime scenario" in comparison_payload["summary"].lower()


def test_workspace_endpoint_returns_coherent_partial_response_when_trip_dates_are_missing(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Dates missing draft",
            "summary": "Verify degraded runtime behavior when persisted trip dates are absent.",
            "mode": "business",
            "trip_frame": {
                "primary_regions": ["Chicago"],
            },
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]

    response = client.get(f"/api/workspace/{trip_id}")
    assert response.status_code == 200
    payload = response.json()

    inventory_summary = payload["inventory_summary"]
    runtime_state = inventory_summary["runtime_state"]
    assert runtime_state["status"] == "partial"
    assert isinstance(runtime_state.get("issues"), list)
    assert runtime_state["issues"]
    assert any(issue["reason"] == "missing_dates" for issue in runtime_state["issues"])

    assert inventory_summary["bundle_count"] == 0
    assert inventory_summary["bundles"] == []
    assert payload["scenario_search"]["scenarios"]
    assert payload["runtime_scenario_comparison"]["scenarios"]
    assert payload["runtime_scenario_comparison"]["lead_scenario_id"].startswith("saved-scenario:")
    _assert_payload_avoids_fixture_or_default_inventory_data(payload)


def test_workspace_endpoint_returns_coherent_partial_response_when_destination_and_dates_are_missing(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Destination and dates missing draft",
            "summary": "Verify degraded runtime behavior when destination and trip dates are absent.",
            "mode": "leisure",
            "trip_frame": {},
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]

    response = client.get(f"/api/workspace/{trip_id}")
    assert response.status_code == 200
    payload = response.json()

    inventory_summary = payload["inventory_summary"]
    runtime_state = inventory_summary["runtime_state"]
    assert runtime_state["status"] == "empty"
    assert isinstance(runtime_state.get("issues"), list)
    assert runtime_state["issues"]
    reasons = {issue["reason"] for issue in runtime_state["issues"]}
    assert {"missing_destination", "missing_dates"}.issubset(reasons)

    assert inventory_summary["bundle_count"] == 0
    assert inventory_summary["bundles"] == []
    assert payload["scenario_search"]["scenarios"]
    assert payload["runtime_scenario_comparison"]["scenarios"]
    assert payload["runtime_scenario_comparison"]["lead_scenario_id"].startswith("saved-scenario:")
    _assert_payload_avoids_fixture_or_default_inventory_data(payload)


@pytest.mark.parametrize(
    ("title", "trip_frame", "expected_issue_codes", "expected_reasons"),
    [
        (
            "Missing destination draft",
            {
                "start_date": "2026-09-05",
                "end_date": "2026-09-08",
                "duration_days": 4,
            },
            {"missing_inventory_primary_regions"},
            {"missing_destination"},
        ),
        (
            "Missing dates draft",
            {
                "primary_regions": ["Lisbon"],
            },
            {"missing_inventory_trip_duration"},
            {"missing_dates"},
        ),
        (
            "Missing destination and dates draft",
            {},
            {"missing_inventory_primary_regions", "missing_inventory_trip_duration"},
            {"missing_destination", "missing_dates"},
        ),
    ],
)
def test_workspace_endpoint_returns_coherent_partial_response_for_missing_trip_inputs(
    client: TestClient,
    title: str,
    trip_frame: dict[str, Any],
    expected_issue_codes: set[str],
    expected_reasons: set[str],
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": title,
            "summary": "Verify degraded persisted-trip runtime behavior when required inputs are missing.",
            "mode": "leisure",
            "trip_frame": trip_frame,
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]

    response = client.get(f"/api/workspace/{trip_id}")
    assert response.status_code == 200
    payload = response.json()

    inventory_summary = payload["inventory_summary"]
    runtime_state = inventory_summary["runtime_state"]
    assert isinstance(runtime_state.get("issues"), list)
    assert runtime_state["issues"]

    issue_codes = {issue["code"] for issue in runtime_state["issues"]}
    issue_reasons = {issue["reason"] for issue in runtime_state["issues"]}
    assert expected_issue_codes.issubset(issue_codes)
    assert expected_reasons.issubset(issue_reasons)

    assert inventory_summary["bundle_count"] == 0
    assert inventory_summary["bundles"] == []
    assert payload["scenario_search"]["scenarios"]
    assert payload["runtime_scenario_comparison"]["scenarios"]
    assert payload["runtime_scenario_comparison"]["lead_scenario_id"].startswith("saved-scenario:")
    _assert_payload_avoids_fixture_or_default_inventory_data(payload)


def test_workspace_endpoint_treats_whitespace_only_primary_regions_as_missing(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Whitespace regions",
            "summary": "Whitespace-only regions should not unlock runtime inventory.",
            "mode": "business",
            "trip_frame": {
                "duration_days": 3,
                "primary_regions": [" ", ""],
            },
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]

    payload = client.get(f"/api/workspace/{trip_id}").json()

    assert payload["runtime_state"]["status"] == "empty"
    assert payload["inventory_summary"]["runtime_state"]["status"] == "empty"
    assert any(
        "add at least one destination" in note.lower()
        for note in payload["inventory_summary"]["notes"]
    )


def test_workspace_endpoint_surfaces_persisted_policy_readiness_for_business_trip(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Policy-backed workspace",
            "summary": "Business workspace should load stored policy posture.",
            "mode": "business",
            "trip_frame": {
                "start_date": "2026-05-04",
                "end_date": "2026-05-06",
                "duration_days": 3,
                "primary_regions": ["Chicago"],
            },
        },
    )
    trip_id = created.json()["trip"]["trip_id"]
    fixture = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "integrations"
            / "tpp"
            / "policy"
            / "standard_policy_sync.json"
        ).read_text(encoding="utf-8")
    )
    imported = client.put(
        f"/api/workspace/{trip_id}/policy",
        json={
            "request": fixture["request"],
            "response": fixture["response"],
            "notes": ["Policy-backed workspace test import."],
        },
    )
    assert imported.status_code == 200

    response = client.get(f"/api/workspace/{trip_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["policy_state"]["policy_id"] == "policy-standard-2026-02"
    assert payload["planner_panel_state"]["policy_evaluation"]["status"] == "compliant"
    assert (
        payload["planner_panel_state"]["proposal"]["constraint_set_id"] == "policy-standard-2026-02"
    )
    assert payload["planner_panel_state"]["outputs"][-1]["title"] == "Approval readiness loaded"
    assert payload["planner_panel_state"]["next_step_actions"][0]["target_section"] == "approval"
    assert "Navan" in payload["planner_panel_state"]["policy_evaluation"]["notes"][-2]


def test_workspace_endpoint_handles_null_constraint_set_for_business_policy_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'workspace.db'}")
    reset_database_state()
    ensure_database_ready()

    with get_session_factory()() as db_session:
        account = create_account(
            db_session,
            email="workspace-null-constraint@example.com",
            password="password123",
            display_name="Workspace Owner",
        )
        user = AuthenticatedUser(
            user_id=account.user_id,
            email=account.email,
            display_name=account.display_name,
        )
        trip = create_trip(
            db_session,
            user=user,
            title="Null constraint set workspace",
            summary="Business workspace should tolerate null policy constraint_set payloads.",
            mode="business",
            start_date="2026-05-12",
            end_date="2026-05-15",
            duration_days=4,
            primary_regions=["Chicago"],
            traveler_kind="team",
            traveler_count=3,
            traveler_notes="Business travel",
        )
        trip_id = trip["trip_id"]
        trip_record = db_session.scalar(
            select(PersistedTrip).where(PersistedTrip.trip_id == trip_id)
        )
        assert trip_record is not None
        db_session.add(
            PersistedPolicyState(
                policy_state_id=f"policy-state:{trip_id}:null-constraint-set",
                trip_id=trip_id,
                user_id=trip_record.user_id,
                owner_profile_id=trip_record.business_profile_id or f"profile:{trip_id}:business",
                source_kind="tpp_sync",
                source_request_id=f"request:{trip_id}",
                source_correlation_id=f"correlation:{trip_id}",
                policy_id="policy-standard-2026-02",
                organization_id="org-enterprise",
                policy_version="2026-02",
                sync_status="current",
                imported_at="2026-05-01T00:00:00Z",
                constraint_set=None,
                organization_context=None,
                freshness=None,
                raw_payload=None,
                tags=[],
                notes=["Inserted by regression test."],
            )
        )
        db_session.commit()
        payload = get_workspace_payload(db_session, user=user, trip_id=trip_id)

    assert payload is not None
    runtime_scenarios = payload["runtime_scenario_comparison"]["scenarios"]
    assert runtime_scenarios
    assert runtime_scenarios[0]["scenario_id"]
    assert runtime_scenarios[0]["metrics"]["score"] is not None
    assert payload["policy_state"]["constraint_set"]["policy_id"] == "policy-standard-2026-02"
    assert payload["policy_state"]["constraint_set"]["required_booking_channels"] == []

    reset_database_state()


def test_workspace_endpoint_surfaces_user_visible_planner_memory(client: TestClient) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Planner memory workspace",
            "summary": "Surface summarized memory in the workspace.",
            "mode": "leisure",
            "trip_frame": {
                "start_date": "2026-07-01",
                "end_date": "2026-07-04",
                "duration_days": 4,
                "primary_regions": ["Kyoto"],
            },
        },
    )
    trip_id = created.json()["trip"]["trip_id"]

    planner_turn = client.post(
        f"/api/planner/{trip_id}/turns",
        json={"message": "Keep the Kyoto baseline and remember that recovery time matters."},
    )
    assert planner_turn.status_code == 200

    response = client.get(f"/api/workspace/{trip_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["planner_memory"]["current_checkpoint_id"].startswith("planner-chk:")
    assert payload["planner_memory"]["artifacts"][0]["title"] == "Planner checkpoint 1"
    assert "Traveler focus:" in payload["planner_memory"]["artifacts"][0]["detail"]


def test_workspace_endpoint_prefers_persisted_proposal_lifecycle_for_business_trip(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Proposal lifecycle workspace",
            "summary": "Business workspace should load persisted proposal state.",
            "mode": "business",
            "trip_frame": {
                "start_date": "2026-05-04",
                "end_date": "2026-05-06",
                "duration_days": 3,
                "primary_regions": ["Chicago"],
            },
        },
    )
    trip_id = created.json()["trip"]["trip_id"]
    submission_fixture = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "integrations"
            / "tpp"
            / "proposal_submit_deferred.json"
        ).read_text(encoding="utf-8")
    )
    submission_fixture["request"]["trip_id"] = trip_id
    submission_fixture["request"]["proposal_id"] = f"proposal:{trip_id}"
    submission_fixture["request"]["payload"]["proposal_ref"] = f"proposal:{trip_id}"
    evaluation_fixture = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "integrations"
            / "tpp"
            / "results"
            / "approved_evaluation.json"
        ).read_text(encoding="utf-8")
    )
    evaluation_fixture["request"]["trip_id"] = trip_id
    evaluation_fixture["request"]["proposal_id"] = f"proposal:{trip_id}"
    evaluation_fixture["response"]["result_payload"]["trip_id"] = trip_id
    evaluation_fixture["response"]["result_payload"]["proposal_id"] = f"proposal:{trip_id}"
    evaluation_fixture["response"]["result_payload"]["evaluation_result"][
        "proposal_id"
    ] = f"proposal:{trip_id}"
    proposal_payload = {
        "proposal_id": f"proposal:{trip_id}",
        "trip_id": trip_id,
        "mode": "business",
        "traveler_context": {
            "employee_type": "employee",
            "traveler_experience": "frequent",
            "home_airport": "ORD",
            "loyalty_programs": ["United"],
            "mobility_or_access_needs": [],
        },
        "selected_options": [
            {
                "category": "airfare",
                "option_id": "flight-1",
                "label": "United 123",
                "vendor": "United",
                "booking_channel": "Navan",
                "estimated_cost": {
                    "currency": "USD",
                    "typical_amount": 620.0,
                    "min_amount": 620.0,
                    "max_amount": 620.0,
                },
                "justification_refs": ["fare-policy"],
            }
        ],
        "cost_summary": {
            "currency": "USD",
            "total_estimated_cost": 620.0,
            "category_estimates": {"airfare": 620.0},
            "notes": ["Costs include taxes."],
        },
        "comparables": [
            {
                "category": "airfare",
                "label": "Flexible fare",
                "vendor": "United",
                "booking_channel": "Concur",
                "estimated_cost": {
                    "currency": "USD",
                    "typical_amount": 710.0,
                    "min_amount": 710.0,
                    "max_amount": 710.0,
                },
                "notes": ["Refundable alternative."],
            }
        ],
        "approval_notes": ["Manager review required before booking."],
        "constraint_set_id": "policy-standard-2026-02",
    }

    submitted = client.put(
        f"/api/workspace/{trip_id}/proposal",
        json={
            "proposal": proposal_payload,
            "request": submission_fixture["request"],
            "response": submission_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )
    assert submitted.status_code == 200
    evaluated = client.put(
        f"/api/workspace/{trip_id}/proposal/evaluation",
        json={
            "request": evaluation_fixture["request"],
            "response": evaluation_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )
    assert evaluated.status_code == 200

    response = client.get(f"/api/workspace/{trip_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["proposal_state"]["summary"]["approval_ready"] is True
    assert payload["planner_panel_state"]["proposal"]["proposal_id"] == f"proposal:{trip_id}"
    assert (
        payload["planner_panel_state"]["policy_evaluation"]["evaluation_id"] == "eval-approved-001"
    )
    titles = [item["title"] for item in payload["planner_panel_state"]["outputs"]]
    assert "Approval packet loaded" in titles
    assert "Approval-ready proposal" in titles
    assert payload["proposal_state"]["follow_up"]["status"] == "resolved"


def test_workspace_endpoint_does_not_mix_policy_preview_with_pending_proposal_state(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Pending proposal workspace",
            "summary": "Workspace should not mix policy preview artifacts with persisted proposals.",
            "mode": "business",
            "trip_frame": {
                "start_date": "2026-05-04",
                "end_date": "2026-05-06",
                "duration_days": 3,
                "primary_regions": ["Chicago"],
            },
        },
    )
    trip_id = created.json()["trip"]["trip_id"]

    policy_fixture = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "integrations"
            / "tpp"
            / "policy"
            / "standard_policy_sync.json"
        ).read_text(encoding="utf-8")
    )
    imported = client.put(
        f"/api/workspace/{trip_id}/policy",
        json={
            "request": policy_fixture["request"],
            "response": policy_fixture["response"],
            "notes": ["Policy-backed workspace test import."],
        },
    )
    assert imported.status_code == 200

    submission_fixture = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "integrations"
            / "tpp"
            / "proposal_submit_deferred.json"
        ).read_text(encoding="utf-8")
    )
    submission_fixture["request"]["trip_id"] = trip_id
    submission_fixture["request"]["proposal_id"] = f"proposal:{trip_id}"
    submission_fixture["request"]["payload"]["proposal_ref"] = f"proposal:{trip_id}"
    proposal_payload = {
        "proposal_id": f"proposal:{trip_id}",
        "trip_id": trip_id,
        "mode": "business",
        "traveler_context": {
            "employee_type": "employee",
            "traveler_experience": "frequent",
            "home_airport": "ORD",
            "loyalty_programs": ["United"],
            "mobility_or_access_needs": [],
        },
        "selected_options": [
            {
                "category": "airfare",
                "option_id": "flight-1",
                "label": "United 123",
                "vendor": "United",
                "booking_channel": "Navan",
                "estimated_cost": {
                    "currency": "USD",
                    "typical_amount": 620.0,
                    "min_amount": 620.0,
                    "max_amount": 620.0,
                },
                "justification_refs": ["fare-policy"],
            }
        ],
        "cost_summary": {
            "currency": "USD",
            "total_estimated_cost": 620.0,
            "category_estimates": {"airfare": 620.0},
            "notes": ["Costs include taxes."],
        },
        "comparables": [],
        "approval_notes": ["Manager review required before booking."],
        "constraint_set_id": "policy-standard-2026-02",
    }

    submitted = client.put(
        f"/api/workspace/{trip_id}/proposal",
        json={
            "proposal": proposal_payload,
            "request": submission_fixture["request"],
            "response": submission_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )
    assert submitted.status_code == 200

    response = client.get(f"/api/workspace/{trip_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["planner_panel_state"]["proposal"]["proposal_id"] == f"proposal:{trip_id}"
    assert payload["planner_panel_state"]["policy_evaluation"] is None
    assert "Approval readiness loaded" not in [
        item["title"] for item in payload["planner_panel_state"]["outputs"]
    ]


def test_workspace_endpoint_surfaces_reoptimization_follow_up_for_non_compliant_results(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Non-compliant workspace",
            "summary": "Workspace should expose the next follow-up action.",
            "mode": "business",
            "trip_frame": {
                "start_date": "2026-05-04",
                "end_date": "2026-05-06",
                "duration_days": 3,
                "primary_regions": ["Chicago"],
            },
        },
    )
    trip_id = created.json()["trip"]["trip_id"]
    submission_fixture = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "integrations"
            / "tpp"
            / "proposal_submit_deferred.json"
        ).read_text(encoding="utf-8")
    )
    submission_fixture["request"]["trip_id"] = trip_id
    submission_fixture["request"]["proposal_id"] = f"proposal:{trip_id}"
    submission_fixture["request"]["payload"]["proposal_ref"] = f"proposal:{trip_id}"
    evaluation_fixture = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "integrations"
            / "tpp"
            / "results"
            / "non_compliant_evaluation.json"
        ).read_text(encoding="utf-8")
    )
    evaluation_fixture["request"]["trip_id"] = trip_id
    evaluation_fixture["request"]["proposal_id"] = f"proposal:{trip_id}"
    evaluation_fixture["response"]["result_payload"]["trip_id"] = trip_id
    evaluation_fixture["response"]["result_payload"]["proposal_id"] = f"proposal:{trip_id}"
    evaluation_fixture["response"]["result_payload"]["evaluation_result"][
        "proposal_id"
    ] = f"proposal:{trip_id}"
    proposal_payload = {
        "proposal_id": f"proposal:{trip_id}",
        "trip_id": trip_id,
        "mode": "business",
        "traveler_context": {
            "employee_type": "employee",
            "traveler_experience": "frequent",
            "home_airport": "ORD",
            "loyalty_programs": ["United"],
            "mobility_or_access_needs": [],
        },
        "selected_options": [
            {
                "category": "airfare",
                "option_id": "flight-1",
                "label": "United 123",
                "vendor": "United",
                "booking_channel": "Navan",
                "estimated_cost": {
                    "currency": "USD",
                    "typical_amount": 620.0,
                    "min_amount": 620.0,
                    "max_amount": 620.0,
                },
                "justification_refs": ["fare-policy"],
            }
        ],
        "cost_summary": {
            "currency": "USD",
            "total_estimated_cost": 620.0,
            "category_estimates": {"airfare": 620.0},
            "notes": ["Costs include taxes."],
        },
        "comparables": [
            {
                "category": "lodging",
                "label": "Downtown compliant hotel",
                "vendor": "Hilton",
                "booking_channel": "Navan",
                "estimated_cost": {
                    "currency": "USD",
                    "typical_amount": 245.0,
                    "min_amount": 245.0,
                    "max_amount": 245.0,
                },
                "notes": ["Compliant alternative for resubmission."],
            }
        ],
        "approval_notes": ["Manager review required before booking."],
        "constraint_set_id": "policy-standard-2026-02",
    }

    client.put(
        f"/api/workspace/{trip_id}/proposal",
        json={
            "proposal": proposal_payload,
            "request": submission_fixture["request"],
            "response": submission_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )
    client.put(
        f"/api/workspace/{trip_id}/proposal/evaluation",
        json={
            "request": evaluation_fixture["request"],
            "response": evaluation_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )

    response = client.get(f"/api/workspace/{trip_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["proposal_state"]["follow_up"]["status"] == "reoptimization_required"
    assert payload["planner_panel_state"]["next_step_actions"][0]["action_kind"] == "reoptimize"
    assert payload["planner_panel_state"]["outputs"][-1]["title"] == "Reoptimization path required"


def test_workspace_endpoint_surfaces_exception_follow_up_for_live_policy_results(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Exception workflow workspace",
            "summary": "Workspace should expose the exception-oriented follow-up lane.",
            "mode": "business",
            "trip_frame": {
                "start_date": "2026-05-04",
                "end_date": "2026-05-06",
                "duration_days": 3,
                "primary_regions": ["Chicago"],
            },
        },
    )
    trip_id = created.json()["trip"]["trip_id"]
    submission_fixture = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "integrations"
            / "tpp"
            / "proposal_submit_deferred.json"
        ).read_text(encoding="utf-8")
    )
    submission_fixture["request"]["trip_id"] = trip_id
    submission_fixture["request"]["proposal_id"] = f"proposal:{trip_id}"
    submission_fixture["request"]["payload"]["proposal_ref"] = f"proposal:{trip_id}"
    evaluation_fixture: dict[str, Any] = {
        "request": {
            "operation": "fetch_evaluation_result",
            "request_id": "req-result-exception-required",
            "correlation_id": {
                "value": "corr-result-exception-required",
                "issued_by": "trip-planner",
            },
            "payload": {
                "execution_id": "exec-exception-001",
            },
            "transport_pattern": "async",
            "organization_id": "org-acme",
            "trip_id": "trip-100",
            "proposal_id": "proposal-123",
            "submitted_at": "2026-04-03T02:18:00Z",
        },
        "response": {
            "operation": "fetch_evaluation_result",
            "request_id": "req-result-exception-required",
            "correlation_id": {
                "value": "corr-result-exception-required",
                "issued_by": "trip-planner",
            },
            "transport_pattern": "async",
            "execution_status": {
                "state": "succeeded",
                "terminal": True,
                "summary": "Policy evaluation completed with an exception requirement",
                "external_status": "200 OK",
                "updated_at": "2026-04-03T02:18:08Z",
            },
            "result_payload": {
                "execution_id": "exec-exception-001",
                "trip_id": "trip-100",
                "proposal_id": "proposal-123",
                "proposal_version": "proposal-v3",
                "scenario_id": "scenario-a",
                "evaluation_result": {
                    "evaluation_id": "eval-exception-001",
                    "proposal_id": "proposal-123",
                    "status": "exception_required",
                    "approval_requirements": [
                        {
                            "role": "manager",
                            "reason": "Schedule exception requires manager approval.",
                            "mandatory": True,
                        }
                    ],
                    "failure_reasons": [
                        {
                            "code": "arrival_window_conflict",
                            "message": "The compliant itinerary misses the client workshop start time.",
                            "severity": "blocking",
                            "related_category": "flight",
                        }
                    ],
                    "preferred_alternatives": [],
                    "exception_guidance": [
                        "Attach the compliant comparable to the exception packet.",
                        "Explain why the earlier arrival is required for the client meeting.",
                    ],
                    "notes": ["Exception review is required before approval can continue."],
                    "compliance_score": 0.61,
                },
            },
            "received_at": "2026-04-03T02:18:08Z",
            "status_endpoint": "https://tpp.example.test/executions/exec-exception-001",
        },
    }
    evaluation_fixture["request"]["trip_id"] = trip_id
    evaluation_fixture["request"]["proposal_id"] = f"proposal:{trip_id}"
    evaluation_fixture["response"]["result_payload"]["trip_id"] = trip_id
    evaluation_fixture["response"]["result_payload"]["proposal_id"] = f"proposal:{trip_id}"
    evaluation_fixture["response"]["result_payload"]["evaluation_result"][
        "proposal_id"
    ] = f"proposal:{trip_id}"
    proposal_payload = {
        "proposal_id": f"proposal:{trip_id}",
        "trip_id": trip_id,
        "mode": "business",
        "traveler_context": {
            "employee_type": "employee",
            "traveler_experience": "frequent",
            "home_airport": "ORD",
            "loyalty_programs": ["United"],
            "mobility_or_access_needs": [],
        },
        "selected_options": [
            {
                "category": "airfare",
                "option_id": "flight-1",
                "label": "United 123",
                "vendor": "United",
                "booking_channel": "Navan",
                "estimated_cost": {
                    "currency": "USD",
                    "typical_amount": 620.0,
                    "min_amount": 620.0,
                    "max_amount": 620.0,
                },
                "justification_refs": ["schedule-policy"],
            }
        ],
        "cost_summary": {
            "currency": "USD",
            "total_estimated_cost": 620.0,
            "category_estimates": {"airfare": 620.0},
            "notes": ["Costs include taxes."],
        },
        "comparables": [
            {
                "category": "airfare",
                "label": "Compliant later departure",
                "vendor": "United",
                "booking_channel": "Navan",
                "estimated_cost": {
                    "currency": "USD",
                    "typical_amount": 610.0,
                    "min_amount": 610.0,
                    "max_amount": 610.0,
                },
                "notes": ["Compliant arrival misses the workshop setup window."],
            }
        ],
        "approval_notes": ["Schedule exception needs a manager decision before booking."],
        "constraint_set_id": "policy-standard-2026-02",
    }

    client.put(
        f"/api/workspace/{trip_id}/proposal",
        json={
            "proposal": proposal_payload,
            "request": submission_fixture["request"],
            "response": submission_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )
    client.put(
        f"/api/workspace/{trip_id}/proposal/evaluation",
        json={
            "request": evaluation_fixture["request"],
            "response": evaluation_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )

    response = client.get(f"/api/workspace/{trip_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["proposal_state"]["follow_up"]["status"] == "exception_required"
    assert (
        payload["planner_panel_state"]["next_step_actions"][0]["action_kind"] == "request_exception"
    )
    assert (
        payload["planner_panel_state"]["next_step_actions"][0]["label"]
        == "Prepare exception request"
    )
    assert payload["planner_panel_state"]["outputs"][-1]["title"] == "Exception path required"
    assert payload["planner_panel_state"]["outputs"][-1]["status"] == "caution"


@pytest.mark.parametrize(
    ("error_code", "expected_title"),
    [
        ("timeout", "Approval service request timed out"),
        ("breaker_open", "Approval service is temporarily unavailable"),
    ],
)
def test_workspace_endpoint_persists_transport_fallback_notice_for_live_submission_errors(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    error_code: str,
    expected_title: str,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Live transport fallback workspace",
            "summary": "Proposal submission should preserve stored-policy posture on transport failures.",
            "mode": "business",
            "trip_frame": {
                "start_date": "2026-05-04",
                "end_date": "2026-05-06",
                "duration_days": 3,
                "primary_regions": ["Chicago"],
            },
        },
    )
    trip_id = created.json()["trip"]["trip_id"]
    submission_fixture = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "integrations"
            / "tpp"
            / "proposal_submit_deferred.json"
        ).read_text(encoding="utf-8")
    )
    submission_fixture["request"]["trip_id"] = trip_id
    submission_fixture["request"]["proposal_id"] = f"proposal:{trip_id}"
    submission_fixture["request"]["payload"]["proposal_ref"] = f"proposal:{trip_id}"
    proposal_payload = {
        "proposal_id": f"proposal:{trip_id}",
        "trip_id": trip_id,
        "mode": "business",
        "traveler_context": {
            "employee_type": "employee",
            "traveler_experience": "frequent",
            "home_airport": "ORD",
            "loyalty_programs": ["United"],
            "mobility_or_access_needs": [],
        },
        "selected_options": [
            {
                "category": "airfare",
                "option_id": "flight-1",
                "label": "United 123",
                "vendor": "United",
                "booking_channel": "Navan",
                "estimated_cost": {
                    "currency": "USD",
                    "typical_amount": 620.0,
                    "min_amount": 620.0,
                    "max_amount": 620.0,
                },
                "justification_refs": ["fare-policy"],
            }
        ],
        "cost_summary": {
            "currency": "USD",
            "total_estimated_cost": 620.0,
            "category_estimates": {"airfare": 620.0},
            "notes": ["Costs include taxes."],
        },
        "comparables": [],
        "approval_notes": ["Manager review required before booking."],
        "constraint_set_id": "policy-standard-2026-02",
    }

    def _raise_live_transport_error(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise TPPTransportError(
            f"Simulated live transport failure: {error_code}",
            error_code=error_code,  # type: ignore[arg-type]
            status_code=503,
            retryable=True,
        )

    monkeypatch.setattr(
        proposal_service,
        "_resolve_submission_response",
        _raise_live_transport_error,
    )

    submitted = client.put(
        f"/api/workspace/{trip_id}/proposal",
        json={
            "proposal": proposal_payload,
            "request": submission_fixture["request"],
            "response": None,
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )
    assert submitted.status_code == 200
    submission_body = submitted.json()
    assert submission_body["proposal_state"]["summary"]["submission_error"]["code"] == error_code

    panel_state = workspace_service._build_planner_panel_state(
        trip={
            "trip_id": trip_id,
            "title": "Live transport fallback workspace",
            "mode": "business",
            "trip_frame": {"primary_regions": ["Chicago"]},
        },
        scenario_search={"scenarios": [], "explanation": [], "source_refs": []},
        session={"pending_decisions": [], "interaction_state": {}},
        saved_scenarios=[],
        activity_log=[],
        feasibility_summary={"assessment_count": 0, "assessments": []},
        policy_context=None,
        proposal_context={"proposal_state": submission_body["proposal_state"]},
    )
    panel_outputs = panel_state["outputs"]
    fallback_output = next(
        (
            output
            for output in panel_outputs
            if output["output_id"].endswith(":proposal-transport-fallback")
        ),
        None,
    )
    assert fallback_output is not None
    assert fallback_output["title"] == expected_title
    assert "latest saved approval information" in fallback_output["body"]
    assert fallback_output["highlights"][0] == "Saved approval information is still available."


def test_workspace_planner_decision_answer_persists_across_reload(client: TestClient) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Austin workshop",
            "summary": "Bootstrap the workspace flow.",
            "mode": "business",
            "trip_frame": {"duration_days": 2, "primary_regions": ["Austin"]},
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]

    initial = client.get(f"/api/workspace/{trip_id}")
    decision = initial.json()["session"]["pending_decisions"][0]

    answered = client.post(
        f"/api/workspace/{trip_id}/planner/decisions/{decision['decision_id']}/answer",
        json={"choice": decision["choices"][0]},
    )

    assert answered.status_code == 200
    payload = answered.json()
    assert payload["session"]["pending_decisions"] == []
    assert payload["activity_log"][0]["event_kind"] == "decision_recorded"
    assert decision["title"] in payload["activity_log"][0]["summary"]

    reloaded = client.get(f"/api/workspace/{trip_id}")
    reloaded_payload = reloaded.json()
    assert reloaded_payload["session"]["pending_decisions"] == []
    assert reloaded_payload["activity_log"][0]["event_kind"] == "decision_recorded"

    with get_session_factory()() as db_session:
        actions = db_session.scalars(
            select(PersistedPlannerAction)
            .where(PersistedPlannerAction.trip_id == trip_id)
            .order_by(PersistedPlannerAction.occurred_at.desc())
        ).all()

    assert actions[0].action_type == "decision_answer"
    assert actions[0].decision_id == decision["decision_id"]
    assert actions[0].choice == decision["choices"][0]
    assert actions[0].activity_event_id == payload["activity_log"][0]["activity_event_id"]
    assert actions[0].occurred_at == payload["activity_log"][0]["occurred_at"]


def test_workspace_planner_decision_answer_returns_not_found_for_unknown_trip(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/workspace/trip-unknown/planner/decisions/decision:missing/answer",
        json={"choice": "Anything"},
    )

    assert response.status_code == 404


def test_workspace_option_feedback_persists_across_reload(client: TestClient) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Kyoto revisit",
            "summary": "Exercise option feedback persistence.",
            "mode": "leisure",
            "trip_frame": {"duration_days": 5, "primary_regions": ["Kyoto"]},
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]

    initial = client.get(f"/api/workspace/{trip_id}")
    option_id = initial.json()["planner_panel_state"]["option_set"]["options"][0]["option_id"]

    updated = client.post(
        f"/api/workspace/{trip_id}/planner/options/{option_id}/feedback",
        json={"action_type": "save_as_fallback", "decision_id": None},
    )

    assert updated.status_code == 200
    payload = updated.json()
    assert payload["activity_log"][0]["event_kind"] == "decision_recorded"
    assert payload["planner_panel_state"]["option_set"]["options"][0]["label"].endswith(
        "(fallback)"
    )

    reloaded = client.get(f"/api/workspace/{trip_id}")
    reloaded_payload = reloaded.json()
    assert reloaded_payload["activity_log"][0]["summary"] == payload["activity_log"][0]["summary"]
    assert reloaded_payload["planner_panel_state"]["option_set"]["options"][0]["label"].endswith(
        "(fallback)"
    )

    with get_session_factory()() as db_session:
        actions = db_session.scalars(
            select(PersistedPlannerAction)
            .where(PersistedPlannerAction.trip_id == trip_id)
            .order_by(PersistedPlannerAction.occurred_at.desc())
        ).all()

    assert actions[0].action_type == "save_as_fallback"
    assert actions[0].option_id == option_id
    assert actions[0].activity_event_id == payload["activity_log"][0]["activity_event_id"]
    assert actions[0].occurred_at == payload["activity_log"][0]["occurred_at"]


def test_workspace_option_feedback_reuses_recent_presentation_ids(client: TestClient) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Kyoto revisit",
            "summary": "Exercise option feedback persistence.",
            "mode": "leisure",
            "trip_frame": {"duration_days": 5, "primary_regions": ["Kyoto"]},
        },
    )
    trip_id = created.json()["trip"]["trip_id"]

    initial = client.get(f"/api/workspace/{trip_id}")
    options = initial.json()["planner_panel_state"]["option_set"]["options"]
    option_index = min(1, len(options) - 1)
    option_id = options[option_index]["option_id"]

    updated = client.post(
        f"/api/workspace/{trip_id}/planner/options/{option_id}/feedback",
        json={"action_type": "accept", "decision_id": None},
    )

    assert updated.status_code == 200
    payload = updated.json()
    assert payload["planner_panel_state"]["option_set"]["options"][option_index]["label"].endswith(
        "(saved direction)"
    )


def _route_option_scenario(
    scenario_id: str,
    *,
    feasible: bool,
    recommended: bool,
    rank: int,
) -> dict[str, Any]:
    return {
        "scenario_id": scenario_id,
        "source_result_id": f"source:{scenario_id}",
        "title": f"Route {rank}",
        "rank": rank,
        "score": 0.9 - (rank / 10),
        "supporting_option_ids": [f"option:{rank}"],
        "objective_refs": [],
        "unresolved_tradeoffs": [],
        "scenario_summary": {
            "headline": f"Route {rank} summary",
            "scenario_kind": "alternative",
            "recommended_for_selection": recommended,
            "feasible": feasible,
            "route_sequence": ["Stockholm", "Oslo"],
            "total_travel_minutes": 120 + rank,
            "total_transfer_count": rank,
            "estimated_total": {"amount": 1000 + rank, "currency": "USD"},
        },
    }


def test_runtime_route_options_hold_blocked_scenarios_for_research() -> None:
    comparison = workspace_service._build_runtime_scenario_comparison(
        trip_id="trip-route-blocked",
        trip_title="Blocked route comparison",
        scenario_search={
            "title": "Route comparison",
            "source_refs": ["test"],
            "scenarios": [
                _route_option_scenario(
                    "scenario:blocked", feasible=False, recommended=True, rank=1
                ),
                _route_option_scenario("scenario:open", feasible=True, recommended=False, rank=2),
            ],
        },
        session=None,
    )

    blocked = comparison["scenarios"][0]
    assert blocked["status"] == "blocked"
    assert blocked["state"] == "needs_research"
    assert "make_baseline" not in [action["action_type"] for action in blocked["available_actions"]]


def test_workspace_route_option_actions_update_comparison_and_ledger(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Scandinavia route workbench",
            "summary": "Keep multiple route options available for comparison.",
            "mode": "leisure",
            "trip_frame": {
                "start_date": "2026-07-04",
                "end_date": "2026-07-12",
                "duration_days": 9,
                "primary_regions": ["Stockholm", "Oslo", "Bergen"],
            },
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]

    initial = client.get(f"/api/workspace/{trip_id}")
    assert initial.status_code == 200
    initial_payload = initial.json()
    route_options = initial_payload["route_comparison"]["scenarios"]
    assert route_options
    assert len(route_options) >= 2
    assert len(route_options) <= 4
    assert route_options[0]["state"] == "baseline"
    assert route_options[0]["purpose"]
    assert isinstance(route_options[0]["confidence"], float)
    assert isinstance(route_options[0]["unresolved_questions"], list)
    assert "open_question" in route_options[0]
    assert route_options[0]["available_actions"]
    assert "available_action" in route_options[0]
    if route_options[0]["unresolved_questions"]:
        assert route_options[0]["open_question"] == route_options[0]["unresolved_questions"][0]
    else:
        assert route_options[0]["open_question"] is None
    assert route_options[0]["available_action"] == route_options[0]["available_actions"][0]

    candidate = route_options[min(1, len(route_options) - 1)]
    candidate_id = candidate["route_option_id"]
    baseline_response = client.post(
        f"/api/workspace/{trip_id}/route-options/{candidate_id}/action",
        json={"action_type": "make_baseline"},
    )

    assert baseline_response.status_code == 200, baseline_response.text
    baseline_payload = baseline_response.json()
    assert baseline_payload["route_comparison"]["lead_scenario_id"] == candidate_id
    baseline_row = next(
        item
        for item in baseline_payload["route_comparison"]["scenarios"]
        if item["route_option_id"] == candidate_id
    )
    assert baseline_row["state"] == "baseline"
    assert baseline_payload["activity_log"][0]["event_kind"] == "decision_recorded"
    assert "comparison baseline" in baseline_payload["activity_log"][0]["summary"]

    rejected_id = route_options[0]["route_option_id"]
    rejected_response = client.post(
        f"/api/workspace/{trip_id}/route-options/{rejected_id}/action",
        json={"action_type": "reject"},
    )

    assert rejected_response.status_code == 200, rejected_response.text
    rejected_payload = rejected_response.json()
    rejected_row = next(
        item
        for item in rejected_payload["route_comparison"]["scenarios"]
        if item["route_option_id"] == rejected_id
    )
    assert rejected_row["state"] == "rejected"
    assert [action["action_type"] for action in rejected_row["available_actions"]] == ["reopen"]
    assert rejected_payload["activity_log"][0]["event_kind"] == "option_rejected"

    reopened_response = client.post(
        f"/api/workspace/{trip_id}/route-options/{rejected_id}/action",
        json={"action_type": "reopen"},
    )

    assert reopened_response.status_code == 200, reopened_response.text
    reopened_payload = reopened_response.json()
    reopened_row = next(
        item
        for item in reopened_payload["route_comparison"]["scenarios"]
        if item["route_option_id"] == rejected_id
    )
    assert reopened_row["state"] in {"active", "fallback"}
    assert any(
        action["action_type"] == "make_baseline" for action in reopened_row["available_actions"]
    )
    assert f"reopened:{rejected_id}" not in json.dumps(reopened_payload)

    reloaded = client.get(f"/api/workspace/{trip_id}")
    assert reloaded.status_code == 200
    assert reloaded.json()["route_comparison"]["lead_scenario_id"] == candidate_id

    with get_session_factory()() as db_session:
        actions = db_session.scalars(
            select(PersistedPlannerAction)
            .where(PersistedPlannerAction.trip_id == trip_id)
            .order_by(PersistedPlannerAction.occurred_at.desc())
        ).all()

    assert actions[0].action_type == "route_option_reopen"
    assert actions[1].action_type == "route_option_reject"
    assert actions[2].action_type == "route_option_make_baseline"
    assert actions[2].option_id == candidate_id
    assert actions[2].payload["route_option_action"] == "make_baseline"


def test_workspace_option_feedback_rejects_unknown_option_id(client: TestClient) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Lisbon revisit",
            "summary": "Reject invalid option identifiers.",
            "mode": "leisure",
            "trip_frame": {"duration_days": 4, "primary_regions": ["Lisbon"]},
        },
    )
    trip_id = created.json()["trip"]["trip_id"]

    invalid = client.post(
        f"/api/workspace/{trip_id}/planner/options/option:missing/feedback",
        json={"action_type": "save_as_fallback", "decision_id": None},
    )

    assert invalid.status_code == 400
    assert "not available in the current workspace option set" in invalid.json()["detail"]


def test_workspace_activity_log_is_capped_for_persisted_trips(client: TestClient) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Tokyo sprint",
            "summary": "Exercise workspace activity log caps.",
            "mode": "business",
            "trip_frame": {"duration_days": 2, "primary_regions": ["Tokyo"]},
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]
    for index in range(55):
        option_id = client.get(f"/api/workspace/{trip_id}").json()["planner_panel_state"][
            "option_set"
        ]["options"][0]["option_id"]
        action_type = "save_as_fallback" if index % 2 == 0 else "reject"
        response = client.post(
            f"/api/workspace/{trip_id}/planner/options/{option_id}/feedback",
            json={"action_type": action_type, "decision_id": None},
        )
        assert response.status_code == 200

    reloaded = client.get(f"/api/workspace/{trip_id}")

    assert reloaded.status_code == 200
    assert len(reloaded.json()["activity_log"]) == 50


def test_workspace_endpoint_hides_other_users_persisted_trips(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/trips",
        json={
            "title": "Kyoto Spring",
            "summary": "Food and gardens",
            "mode": "leisure",
            "trip_frame": {"duration_days": 7},
        },
    )
    assert created.status_code == 201
    trip_id = created.json()["trip"]["trip_id"]

    client.post("/api/auth/logout")
    client.post(
        "/api/auth/signup",
        json={
            "email": "other@example.com",
            "password": "password123",
            "display_name": "Other User",
        },
    )

    response = client.get(f"/api/workspace/{trip_id}")

    assert response.status_code == 404


def test_planner_panel_state_surfaces_stored_policy_fallback_notice_for_breaker_open() -> None:
    panel_state = workspace_service._build_planner_panel_state(
        trip={
            "trip_id": "trip-fallback",
            "title": "Fallback trip",
            "mode": "business",
            "trip_frame": {"primary_regions": ["Chicago"]},
        },
        scenario_search={"scenarios": [], "explanation": [], "source_refs": []},
        session={"pending_decisions": [], "interaction_state": {}},
        saved_scenarios=[],
        activity_log=[],
        feasibility_summary={"assessment_count": 0, "assessments": []},
        policy_context=None,
        proposal_context={
            "proposal_state": {
                "proposal": {"proposal_id": "proposal:trip-fallback"},
                "summary": {
                    "submission_error": {
                        "code": "breaker_open",
                        "message": "TPP circuit breaker is open for host.",
                    }
                },
            }
        },
    )

    fallback_output = next(
        (
            item
            for item in panel_state["outputs"]
            if item["output_id"].endswith(":proposal-transport-fallback")
        ),
        None,
    )
    assert fallback_output is not None
    assert fallback_output["title"] == "Approval service is temporarily unavailable"
    assert "latest saved approval information" in fallback_output["body"]
    assert fallback_output["status"] == "caution"
    assert fallback_output["highlights"][0] == "Saved approval information is still available."


def test_planner_panel_state_surfaces_policy_sync_fallback_notice_for_breaker_open() -> None:
    panel_state = workspace_service._build_planner_panel_state(
        trip={
            "trip_id": "trip-policy-fallback",
            "title": "Policy fallback trip",
            "mode": "business",
            "trip_frame": {"primary_regions": ["Chicago"]},
        },
        scenario_search={"scenarios": [], "explanation": [], "source_refs": []},
        session={"pending_decisions": [], "interaction_state": {}},
        saved_scenarios=[],
        activity_log=[],
        feasibility_summary={"assessment_count": 0, "assessments": []},
        policy_context={
            "proposal": {"proposal_id": "proposal:trip-policy-fallback"},
            "policy_evaluation": {"status": "compliant", "notes": []},
            "summary": {
                "status": "stored_policy_fallback",
                "transport_error": {
                    "error_code": "breaker_open",
                    "message": "TPP circuit breaker is open for host.",
                },
            },
        },
        proposal_context=None,
    )

    fallback_output = next(
        (
            item
            for item in panel_state["outputs"]
            if item["output_id"].endswith(":policy-transport-fallback")
        ),
        None,
    )
    assert fallback_output is not None
    assert fallback_output["title"] == "Approval service is temporarily unavailable"
    assert "latest saved approval information" in fallback_output["body"]
    assert fallback_output["status"] == "caution"
    assert fallback_output["highlights"][0] == "Saved approval information is still available."


def test_planner_panel_state_surfaces_stored_policy_fallback_notice_for_timeout() -> None:
    panel_state = workspace_service._build_planner_panel_state(
        trip={
            "trip_id": "trip-timeout-fallback",
            "title": "Timeout fallback trip",
            "mode": "business",
            "trip_frame": {"primary_regions": ["Chicago"]},
        },
        scenario_search={"scenarios": [], "explanation": [], "source_refs": []},
        session={"pending_decisions": [], "interaction_state": {}},
        saved_scenarios=[],
        activity_log=[],
        feasibility_summary={"assessment_count": 0, "assessments": []},
        policy_context=None,
        proposal_context={
            "proposal_state": {
                "proposal": {"proposal_id": "proposal:trip-timeout-fallback"},
                "summary": {
                    "submission_error": {
                        "code": "timeout",
                        "message": "Live TPP request exceeded transport timeout.",
                    }
                },
            }
        },
    )

    fallback_output = next(
        (
            item
            for item in panel_state["outputs"]
            if item["output_id"].endswith(":proposal-transport-fallback")
        ),
        None,
    )
    assert fallback_output is not None
    assert fallback_output["title"] == "Approval service request timed out"
    assert "latest saved approval information" in fallback_output["body"]
    assert fallback_output["status"] == "caution"
    assert fallback_output["highlights"][0] == "Saved approval information is still available."


def test_planner_panel_state_uses_submission_error_details_code_for_timeout_fallback() -> None:
    panel_state = workspace_service._build_planner_panel_state(
        trip={
            "trip_id": "trip-timeout-details-fallback",
            "title": "Timeout details fallback trip",
            "mode": "business",
            "trip_frame": {"primary_regions": ["Chicago"]},
        },
        scenario_search={"scenarios": [], "explanation": [], "source_refs": []},
        session={"pending_decisions": [], "interaction_state": {}},
        saved_scenarios=[],
        activity_log=[],
        feasibility_summary={"assessment_count": 0, "assessments": []},
        policy_context=None,
        proposal_context={
            "proposal_state": {
                "proposal": {"proposal_id": "proposal:trip-timeout-details-fallback"},
                "summary": {
                    "submission_error": {
                        "message": "Live TPP request exceeded transport timeout.",
                        "details": {"error_code": "timeout"},
                    }
                },
            }
        },
    )

    fallback_output = next(
        (
            item
            for item in panel_state["outputs"]
            if item["output_id"].endswith(":proposal-transport-fallback")
        ),
        None,
    )
    assert fallback_output is not None
    assert fallback_output["title"] == "Approval service request timed out"
    assert "latest saved approval information" in fallback_output["body"]
    assert fallback_output["status"] == "caution"
    assert fallback_output["highlights"][0] == "Saved approval information is still available."


def test_planner_panel_state_surfaces_stored_policy_fallback_notice_for_evaluation_timeout() -> (
    None
):
    panel_state = workspace_service._build_planner_panel_state(
        trip={
            "trip_id": "trip-evaluation-timeout-fallback",
            "title": "Evaluation timeout fallback trip",
            "mode": "business",
            "trip_frame": {"primary_regions": ["Chicago"]},
        },
        scenario_search={"scenarios": [], "explanation": [], "source_refs": []},
        session={"pending_decisions": [], "interaction_state": {}},
        saved_scenarios=[],
        activity_log=[],
        feasibility_summary={"assessment_count": 0, "assessments": []},
        policy_context=None,
        proposal_context={
            "proposal_state": {
                "proposal": {"proposal_id": "proposal:trip-evaluation-timeout-fallback"},
                "summary": {
                    "evaluation_error": {
                        "code": "timeout",
                        "message": "Live TPP evaluation transport timed out.",
                    }
                },
            }
        },
    )

    fallback_output = next(
        (
            item
            for item in panel_state["outputs"]
            if item["output_id"].endswith(":proposal-transport-fallback")
        ),
        None,
    )
    assert fallback_output is not None
    assert fallback_output["title"] == "Approval service request timed out"
    assert "latest saved approval information" in fallback_output["body"]
    assert fallback_output["status"] == "caution"
    assert fallback_output["highlights"][0] == "Saved approval information is still available."


def test_planner_panel_state_surfaces_policy_sync_fallback_notice_for_timeout() -> None:
    panel_state = workspace_service._build_planner_panel_state(
        trip={
            "trip_id": "trip-policy-timeout",
            "title": "Policy timeout fallback trip",
            "mode": "business",
            "trip_frame": {"primary_regions": ["Chicago"]},
        },
        scenario_search={"scenarios": [], "explanation": [], "source_refs": []},
        session={"pending_decisions": [], "interaction_state": {}},
        saved_scenarios=[],
        activity_log=[],
        feasibility_summary={"assessment_count": 0, "assessments": []},
        policy_context={
            "proposal": {"proposal_id": "proposal:trip-policy-timeout"},
            "policy_evaluation": {"status": "compliant", "notes": []},
            "summary": {
                "status": "stored_policy_fallback",
                "transport_error": {
                    "error_code": "timeout",
                    "message": "Live TPP request exceeded transport timeout.",
                },
            },
        },
        proposal_context=None,
    )

    fallback_output = next(
        (
            item
            for item in panel_state["outputs"]
            if item["output_id"].endswith(":policy-transport-fallback")
        ),
        None,
    )
    assert fallback_output is not None
    assert fallback_output["title"] == "Approval service request timed out"
    assert "latest saved approval information" in fallback_output["body"]
    assert fallback_output["status"] == "caution"
    assert fallback_output["highlights"][0] == "Saved approval information is still available."


def _load_feasibility_fixture(name: str) -> InventoryBundle:
    fixture_path = (
        Path(__file__).resolve().parents[1] / "fixtures" / "itinerary" / "feasibility" / name
    )
    return InventoryBundle.from_dict(json.loads(fixture_path.read_text(encoding="utf-8")))


def test_feasibility_summary_payload_keeps_ready_and_blocked_bundles_distinct() -> None:
    payload = build_feasibility_summary_payload(
        [
            _load_feasibility_fixture("coherent_low_friction_route.json"),
            _load_feasibility_fixture("unrealistic_same_day_chaining.json"),
        ]
    )

    assert payload["assessment_count"] == 2
    assert payload["recommended_bundle_count"] == 1
    assert payload["blocking_bundle_count"] == 1
    statuses = {
        assessment["bundle_id"]: assessment["status"] for assessment in payload["assessments"]
    }
    assert statuses["bundle:kyoto-low-friction"] == "positive"
    assert statuses["bundle:unrealistic-same-day"] == "critical"


def test_feasibility_planner_outputs_surface_blocking_transition_details() -> None:
    summary = build_feasibility_summary_payload(
        [_load_feasibility_fixture("unrealistic_same_day_chaining.json")]
    )

    outputs = build_feasibility_planner_outputs(
        trip_id="trip-test-feasibility",
        feasibility_summary=summary,
    )

    assert outputs[0]["status"] == "critical"
    assert outputs[1]["status"] == "critical"
    assert any(
        "activity_start_window_missed" in highlight.lower().replace(" ", "_")
        or "cannot be reached inside its advertised start window" in highlight.lower()
        for highlight in outputs[1]["highlights"]
    )


_RAW_DEBUG_TOKENS_FORBIDDEN_IN_USER_COPY = (
    "runtime provider",
    "runtime_state_id",
    "fallback mode",
    "policy_state_id",
    "proposal_state_id",
    "session_state_id",
    "scenario_search_id",
)


def _assert_user_summary_avoids_raw_runtime_language(view_model: dict[str, Any]) -> None:
    user_summary = view_model["user_summary"]
    next_step = view_model["next_step"]
    user_facing_strings = [user_summary["headline"], next_step["title"], next_step["summary"]]
    user_facing_strings.extend(user_summary.get("decided", []))
    user_facing_strings.extend(user_summary.get("uncertain", []))
    business_summary = view_model.get("business_summary")
    if business_summary is not None:
        user_facing_strings.append(business_summary["headline"])
        user_facing_strings.extend(business_summary.get("blockers", []))
    for value in user_facing_strings:
        lowered = value.lower()
        for token in _RAW_DEBUG_TOKENS_FORBIDDEN_IN_USER_COPY:
            assert (
                token not in lowered
            ), f"User-facing view-model copy must not leak '{token}': {value!r}"


def test_workspace_endpoint_includes_typed_view_model_for_leisure_trip(
    client: TestClient,
) -> None:
    response = client.get("/api/workspace/trip-leisure-kyoto-draft")

    assert response.status_code == 200
    payload = response.json()
    view_model = payload["view_model"]
    assert view_model is not None
    user_summary = view_model["user_summary"]
    assert user_summary["trip_mode"] == "leisure"
    assert user_summary["mode_label"] == "Leisure trip"
    assert user_summary["status"] in {"ready", "partial", "empty"}
    assert user_summary["trip_title"]
    assert user_summary["headline"]

    next_step = view_model["next_step"]
    assert next_step["title"]
    assert next_step["summary"]

    assert view_model["business_summary"] is None
    assert view_model["panel_visibility"] == {
        "show_budget_panel": True,
        "show_policy_posture": False,
        "show_proposal_panel": False,
        "show_approval_readiness_panel": False,
    }
    assert view_model["policy_presentation"]["active_policy_state"] is False
    assert view_model["policy_presentation"]["posture_label"] == "Not applicable"

    debug_state = view_model["debug_state"]
    assert "runtime_state" in debug_state["sections"]
    assert "policy_state" not in debug_state["sections"]
    assert "proposal_state" not in debug_state["sections"]
    assert (
        debug_state["sections"]["runtime_state"]["payload"]["status"]
        == payload["runtime_state"]["status"]
    )

    _assert_user_summary_avoids_raw_runtime_language(view_model)


def test_workspace_endpoint_includes_typed_view_model_for_business_trip(
    client: TestClient,
) -> None:
    response = client.get("/api/workspace/trip-business-client-summit")

    assert response.status_code == 200
    payload = response.json()
    view_model = payload["view_model"]
    assert view_model is not None
    user_summary = view_model["user_summary"]
    assert user_summary["trip_mode"] == "business"
    assert user_summary["mode_label"] == "Business trip"

    business_summary = view_model["business_summary"]
    assert business_summary is not None
    assert business_summary["approval_status"] in {
        "not_applicable",
        "not_ready",
        "in_review",
        "approved",
        "needs_attention",
    }
    assert business_summary["headline"]
    assert view_model["panel_visibility"]["show_policy_posture"] is True
    assert view_model["panel_visibility"]["show_proposal_panel"] is True
    assert view_model["panel_visibility"]["show_approval_readiness_panel"] is True
    assert view_model["policy_presentation"]["posture_label"] in {
        "Approval not started",
        "Ready for approval",
        "Waiting for policy review",
        "Needs exception",
        "Needs follow-up",
        "Not ready for approval",
        "Policy state available",
    }

    debug_state = view_model["debug_state"]
    assert "runtime_state" in debug_state["sections"]

    _assert_user_summary_avoids_raw_runtime_language(view_model)


def test_workspace_view_model_builder_handles_empty_runtime_state() -> None:
    payload = {
        "trip_record": {
            "trip": {"title": "Bare workspace", "mode": "leisure"},
        },
        "runtime_state": {"status": "empty", "title": "", "summary": ""},
        "saved_scenarios": [],
        "inventory_summary": {"bundle_count": 0},
        "feasibility_summary": {"attention_bundle_count": 0},
    }

    view_model = workspace_service._build_workspace_view_model(payload)

    assert view_model["user_summary"]["status"] == "empty"
    assert view_model["next_step"]["blocked"] is True
    assert view_model["business_summary"] is None
    assert view_model["debug_state"]["sections"]["runtime_state"]["payload"]["status"] == "empty"


def test_workspace_view_model_keeps_active_leisure_policy_state_visible() -> None:
    payload = {
        "trip_record": {
            "trip": {"title": "Leisure exception workspace", "mode": "leisure"},
        },
        "runtime_state": {"status": "ready", "title": "Ready", "summary": "Ready"},
        "saved_scenarios": [{"saved_scenario_id": "scenario-1"}],
        "inventory_summary": {"bundle_count": 1},
        "feasibility_summary": {"attention_bundle_count": 0},
        "proposal_state": {
            "execution_id": "exec-active-leisure",
            "submission_status": "submitted",
            "evaluation_status": "completed",
            "summary": {
                "submission_status": "submitted",
                "evaluation_result_status": "failed",
                "follow_up_status": "exception_required",
                "approval_ready": False,
                "highlights": ["A lodging exception needs review."],
            },
        },
    }

    view_model = workspace_service._build_workspace_view_model(payload)

    assert view_model["business_summary"] is None
    assert view_model["panel_visibility"]["show_policy_posture"] is True
    assert view_model["panel_visibility"]["show_proposal_panel"] is True
    assert view_model["policy_presentation"]["posture_label"] == "Needs exception"
    assert "proposal_state" in view_model["debug_state"]["sections"]


def test_workspace_view_model_debug_sections_preserve_raw_payload_shapes() -> None:
    saved_scenarios = [{"saved_scenario_id": "scenario-1"}]
    activity_log = [{"activity_event_id": "activity-1"}]
    payload = {
        "trip_record": {
            "trip": {"title": "Raw debug workspace", "mode": "leisure"},
        },
        "runtime_state": {"status": "ready", "title": "Ready", "summary": "Ready"},
        "saved_scenarios": saved_scenarios,
        "inventory_summary": {"bundle_count": 1},
        "feasibility_summary": {"attention_bundle_count": 0},
        "activity_log": activity_log,
    }

    view_model = workspace_service._build_workspace_view_model(payload)
    debug_sections = view_model["debug_state"]["sections"]

    assert debug_sections["saved_scenarios"]["payload"] == saved_scenarios
    assert debug_sections["activity_log"]["payload"] == activity_log
