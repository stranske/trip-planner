from fastapi.testclient import TestClient

from trip_planner.app.main import app


def test_workspace_endpoint_returns_trip_scenario_payload() -> None:
    client = TestClient(app)

    response = client.get("/api/workspace/trip-leisure-kyoto-draft")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trip_record"]["trip"]["trip_id"] == "trip-leisure-kyoto-draft"
    assert payload["session"]["current_saved_scenario_id"] == "saved-scenario:kyoto-baseline"
    assert payload["scenario_search"]["scenarios"][0]["scenario_summary"]["route_sequence"] == [
        "kyoto",
        "uji",
        "kyoto",
    ]


def test_workspace_endpoint_returns_not_found_for_unknown_trip() -> None:
    client = TestClient(app)

    response = client.get("/api/workspace/trip-unknown")

    assert response.status_code == 404
