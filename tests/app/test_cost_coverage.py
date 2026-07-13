from __future__ import annotations

import json
from collections.abc import Iterator
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.persistence.db import reset_database_state


@pytest.fixture
def client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'coverage.db'}")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    reset_database_state()
    with TestClient(create_app()) as test_client:
        response = test_client.post(
            "/api/auth/signup",
            json={
                "email": "coverage@example.com",
                "password": "password123",
                "display_name": "Coverage Tester",
            },
        )
        assert response.status_code == 201
        yield test_client
    reset_database_state()


def _catalog() -> dict[str, object]:
    return {
        "contract_version": "tpp-intake-requirements/v1",
        "organization_id": "tpp",
        "requirements": [
            {
                "code": "airport_parking",
                "category": "ground_transport",
                "title": "Airport parking",
                "summary": "Research official parking rates.",
                "collection_mode": "researchable",
                "evidence_kind": "provider_rate",
                "required_inputs": ["departure_airport", "parking_days"],
                "output_fields": ["parking_estimate"],
                "research_prompt": "Find current official airport parking options.",
            },
            {
                "code": "organization_attestations",
                "category": "administrative",
                "title": "Organization details",
                "summary": "Traveler-supplied fields.",
                "collection_mode": "traveler",
                "evidence_kind": "traveler_confirmation",
                "required_inputs": [],
                "output_fields": ["cost_center"],
            },
        ],
    }


def _create_trip(client: TestClient) -> str:
    response = client.post(
        "/api/trips",
        json={
            "title": "NYC meetings",
            "summary": "Business meetings",
            "mode": "business",
            "trip_frame": {
                "start_date": "2026-11-11",
                "end_date": "2026-11-14",
                "duration_days": 4,
                "primary_regions": ["New York, NY 10282"],
            },
        },
    )
    assert response.status_code == 201
    return response.json()["trip"]["trip_id"]


def test_cost_coverage_derives_parking_days_and_requests_only_missing_airport(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "trip_planner.app.services.cost_coverage._load_tpp_catalog",
        _catalog,
    )
    trip_id = _create_trip(client)

    response = client.get(f"/api/workspace/{trip_id}/cost-coverage")

    assert response.status_code == 200
    parking = next(
        item for item in response.json()["requirements"] if item["code"] == "airport_parking"
    )
    assert parking["inputs"]["parking_days"] == "4"
    assert parking["missing_inputs"] == ["departure_airport"]
    assert parking["status"] == "needs_input"
    assert response.json()["summary"]["research_offer_count"] == 1


def test_research_returns_missing_input_prompt_without_calling_provider(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "trip_planner.app.services.cost_coverage._load_tpp_catalog",
        _catalog,
    )
    trip_id = _create_trip(client)

    response = client.post(
        f"/api/workspace/{trip_id}/cost-coverage/airport_parking/research",
        json={"inputs": {}},
    )

    assert response.status_code == 200
    assert response.json()["research_notice"]["status"] == "needs_input"
    assert response.json()["research_notice"]["missing_inputs"] == ["departure_airport"]


def test_live_research_persists_options_sources_and_timestamp(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "trip_planner.app.services.cost_coverage._load_tpp_catalog",
        _catalog,
    )
    monkeypatch.setenv("TRIP_PLANNER_PLANNER_MODEL_PROVIDER", "openai")
    monkeypatch.setenv("TRIP_PLANNER_PLANNER_MODEL", "gpt-test")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    option = {
        "name": "Official economy lot",
        "unit_rate": 12,
        "unit": "day",
        "estimated_total": 48,
        "notes": "Airport shuttle included.",
        "source_url": "https://airport.example/parking",
    }
    response_payload = SimpleNamespace(
        output_text=json.dumps({"summary": "Official parking researched.", "options": [option]}),
        output=[
            SimpleNamespace(
                type="web_search_call",
                action=SimpleNamespace(
                    sources=[
                        SimpleNamespace(
                            title="Airport parking",
                            url="https://airport.example/parking",
                        )
                    ]
                ),
            )
        ],
    )

    class FakeResponses:
        def create(self, **kwargs):
            assert kwargs["tools"] == [{"type": "web_search"}]
            return response_payload

    class FakeOpenAI:
        def __init__(self, **_kwargs) -> None:
            self.responses = FakeResponses()

    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)
    trip_id = _create_trip(client)

    response = client.post(
        f"/api/workspace/{trip_id}/cost-coverage/airport_parking/research",
        json={"inputs": {"departure_airport": "STL"}},
    )

    assert response.status_code == 200
    parking = next(
        item for item in response.json()["requirements"] if item["code"] == "airport_parking"
    )
    assert parking["status"] == "researched"
    assert parking["research"]["options"] == [option]
    assert parking["research"]["sources"][0]["url"] == option["source_url"]
    assert parking["research"]["researched_at"].endswith("Z")


def test_selecting_researched_option_marks_requirement_evidenced(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "trip_planner.app.services.cost_coverage._load_tpp_catalog",
        _catalog,
    )
    trip_id = _create_trip(client)

    response = client.patch(
        f"/api/workspace/{trip_id}/cost-coverage/airport_parking",
        json={
            "estimate_amount": 48,
            "source_url": "https://airport.example/parking",
            "selected_option": {"name": "Official economy lot", "estimated_total": 48},
        },
    )

    assert response.status_code == 200
    parking = next(
        item for item in response.json()["requirements"] if item["code"] == "airport_parking"
    )
    assert parking["status"] == "evidenced"
    assert parking["estimate_amount"] == 48


def test_shared_inputs_are_reused_across_related_requirements(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = _catalog()
    requirements = catalog["requirements"]
    assert isinstance(requirements, list)
    requirements.append(
        {
            "code": "intercity_transport",
            "category": "airfare",
            "title": "Intercity transportation",
            "summary": "Research roundtrip options.",
            "collection_mode": "researchable",
            "evidence_kind": "fare_quote",
            "required_inputs": [
                "departure_airport",
                "destination_airport",
                "travel_dates",
            ],
            "output_fields": ["selected_fare"],
            "research_prompt": "Find practical transportation options.",
        }
    )
    monkeypatch.setattr(
        "trip_planner.app.services.cost_coverage._load_tpp_catalog",
        lambda: catalog,
    )
    trip_id = _create_trip(client)

    response = client.patch(
        f"/api/workspace/{trip_id}/cost-coverage/airport_parking",
        json={"inputs": {"departure_airport": "STL"}},
    )

    assert response.status_code == 200
    intercity = next(
        item for item in response.json()["requirements"] if item["code"] == "intercity_transport"
    )
    assert intercity["inputs"]["departure_airport"] == "STL"
    assert intercity["missing_inputs"] == ["destination_airport"]


def test_residence_and_official_domicile_are_reused_for_future_trips(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = _catalog()
    requirements = catalog["requirements"]
    assert isinstance(requirements, list)
    requirements.append(
        {
            "code": "airport_access",
            "category": "ground_transport",
            "title": "Airport access",
            "summary": "Apply mileage and commuting rules.",
            "collection_mode": "researchable",
            "evidence_kind": "route_comparison",
            "required_inputs": [
                "traveler_residence_address",
                "official_domicile_address",
                "departure_airport",
            ],
            "output_fields": ["ground_transport.mileage_miles"],
            "research_prompt": "Compare the residence and official domicile routes.",
        }
    )
    monkeypatch.setattr(
        "trip_planner.app.services.cost_coverage._load_tpp_catalog",
        lambda: catalog,
    )
    first_trip_id = _create_trip(client)
    addresses = {
        "traveler_residence_address": "803 B Broadway, Jefferson City, MO",
        "official_domicile_address": "3236 W Edgewood Dr, Jefferson City, MO 65109",
        "departure_airport": "STL",
    }

    response = client.patch(
        f"/api/workspace/{first_trip_id}/cost-coverage/airport_access",
        json={"inputs": addresses},
    )
    assert response.status_code == 200

    second_trip_id = _create_trip(client)
    second_response = client.get(f"/api/workspace/{second_trip_id}/cost-coverage")
    airport_access = next(
        item for item in second_response.json()["requirements"] if item["code"] == "airport_access"
    )
    assert (
        airport_access["inputs"]["traveler_residence_address"]
        == addresses["traveler_residence_address"]
    )
    assert (
        airport_access["inputs"]["official_domicile_address"]
        == addresses["official_domicile_address"]
    )
    assert airport_access["missing_inputs"] == ["departure_airport"]


def test_destination_zip_is_derived_from_saved_trip_region(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = _catalog()
    requirements = catalog["requirements"]
    assert isinstance(requirements, list)
    requirements.append(
        {
            "code": "meals_incidentals",
            "category": "meals",
            "title": "Meals and incidental allowance",
            "summary": "Calculate eligible meals.",
            "collection_mode": "automatic",
            "evidence_kind": "policy_rate",
            "required_inputs": ["destination_zip"],
            "output_fields": ["meal_counts"],
            "research_prompt": "Apply the organization meal policy.",
        }
    )
    monkeypatch.setattr(
        "trip_planner.app.services.cost_coverage._load_tpp_catalog",
        lambda: catalog,
    )
    trip_id = _create_trip(client)

    response = client.get(f"/api/workspace/{trip_id}/cost-coverage")

    assert response.status_code == 200
    meals = next(
        item for item in response.json()["requirements"] if item["code"] == "meals_incidentals"
    )
    assert meals["inputs"]["destination_zip"] == "10282"
    assert meals["missing_inputs"] == []
