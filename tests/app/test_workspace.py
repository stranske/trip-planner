from collections.abc import Iterator
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.app.services.feasibility import (
    build_feasibility_planner_outputs,
    build_feasibility_summary_payload,
)
from trip_planner.options import InventoryBundle
from trip_planner.persistence.db import reset_database_state


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv(
        "TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'workspace.db'}"
    )
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
    assert (
        payload["session"]["current_saved_scenario_id"]
        == "saved-scenario:kyoto-baseline"
    )
    assert payload["scenario_search"]["title"] == "Kyoto ranked scenario workspace"
    assert payload["scenario_search"]["scenarios"][0]["title"] == "Kyoto cultural anchor"
    assert payload["scenario_search"]["scenarios"][0]["scenario_summary"][
        "route_sequence"
    ] == ["dest-city-osaka", "dest-city-kyoto"]
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
    assert payload["runtime_scenario_comparison"]["lead_scenario_id"] == payload["scenario_search"][
        "scenarios"
    ][0]["scenario_id"]
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
    assert payload["runtime_scenario_comparison"]["lead_scenario_id"] == payload["runtime_scenario_comparison"][
        "scenarios"
    ][0]["scenario_id"]
    assert payload["runtime_scenario_comparison"]["scenarios"][0]["status"] == "fallback"
    assert payload["planner_panel_state"]["outputs"][2]["title"] == "Scenario ranking summary"
    assert payload["planner_panel_state"]["outputs"][3]["title"] == "Rank #1 Airport arrival bundle"
    assert payload["planner_panel_state"]["option_set"]["options"][0]["label"] == "Airport arrival bundle"


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


def test_workspace_endpoint_returns_minimal_payload_for_persisted_trip(
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
    assert payload["session"]["pending_decisions"][0]["decision_id"].startswith("decision:")
    assert payload["saved_scenarios"] == []
    assert payload["scenario_search"]["scenarios"] == []
    assert payload["runtime_scenario_comparison"]["scenarios"] == []
    assert payload["inventory_summary"]["bundle_count"] == 0
    assert payload["feasibility_summary"]["assessment_count"] == 0
    assert payload["activity_log"] == []
    assert payload["budget_state"]["summary"]["planned_total"] == 0
    assert payload["budget_state"]["summary"]["actual_total"] == 0
    assert payload["budget_state"]["summary"]["has_budget_plan"] is False
    assert payload["planner_panel_state"]["trip"]["trip_id"] == trip_id
    assert payload["planner_panel_state"]["option_set"]["purpose"] == "workspace_bootstrap"
    assert payload["policy_state"] is None
    assert payload["proposal_state"] is None


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
    assert payload["planner_panel_state"]["proposal"]["constraint_set_id"] == "policy-standard-2026-02"
    assert payload["planner_panel_state"]["outputs"][-1]["title"] == "Policy posture loaded"
    assert payload["planner_panel_state"]["next_step_actions"][0]["target_section"] == "approval"
    assert "Navan" in payload["planner_panel_state"]["policy_evaluation"]["notes"][-2]


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
    evaluation_fixture["response"]["result_payload"]["evaluation_result"]["proposal_id"] = (
        f"proposal:{trip_id}"
    )
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
    assert payload["planner_panel_state"]["policy_evaluation"]["evaluation_id"] == "eval-approved-001"
    assert payload["planner_panel_state"]["outputs"][-1]["title"] == "Proposal lifecycle loaded"


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
    option_id = client.get(f"/api/workspace/{trip_id}").json()["planner_panel_state"]["option_set"][
        "options"
    ][0]["option_id"]

    for index in range(55):
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
    statuses = {assessment["bundle_id"]: assessment["status"] for assessment in payload["assessments"]}
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
