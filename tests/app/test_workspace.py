from collections.abc import Iterator
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from trip_planner.app.main import create_app
from trip_planner.app.services.feasibility import (
    build_feasibility_planner_outputs,
    build_feasibility_summary_payload,
)
from trip_planner.app.services.scenarios import _runtime_business_profile
from trip_planner.options import InventoryBundle
from trip_planner.persistence.db import get_session_factory, reset_database_state
from trip_planner.persistence.models.activity import PersistedPlannerAction

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


def test_workspace_endpoint_surfaces_business_ranked_scenarios(client: TestClient) -> None:
    response = client.get("/api/workspace/trip-business-client-summit")

    assert response.status_code == 200
    payload = response.json()
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
    assert "runtime scenario" in payload["summary"].lower()


def test_workspace_endpoint_returns_not_found_for_unknown_trip(
    client: TestClient,
) -> None:
    response = client.get("/api/workspace/trip-unknown")

    assert response.status_code == 404

    comparison_response = client.get("/api/workspace/trip-unknown/scenarios/compare")

    assert comparison_response.status_code == 404


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
    assert isinstance(workspace_payload["inventory_summary"]["bundle_count"], int)
    assert workspace_payload["inventory_summary"]["bundle_count"] > 0
    assert workspace_payload["scenario_comparison"] is not None
    assert workspace_payload["scenario_comparison"]["baseline_scenario_id"]
    runtime_comparison = workspace_payload["runtime_scenario_comparison"]
    assert runtime_comparison["scenarios"]
    first_scenario = runtime_comparison["scenarios"][0]
    assert first_scenario["scenario_id"]
    assert first_scenario["metrics"]["estimated_total"] is not None
    assert any(
        first_scenario["metrics"][key] is not None
        for key in ("score", "travel_minutes", "transfers")
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
    assert payload["planner_panel_state"]["outputs"][-1]["title"] == "Policy posture loaded"
    assert payload["planner_panel_state"]["next_step_actions"][0]["target_section"] == "approval"
    assert "Navan" in payload["planner_panel_state"]["policy_evaluation"]["notes"][-2]


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
    assert "Proposal lifecycle loaded" in titles
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
    assert "Policy posture loaded" not in [
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
