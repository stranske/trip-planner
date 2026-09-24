"""TPP interception shared by the app tests (see `tpp_client` in conftest.py).

State lives here, not in conftest.py: pytest imports conftest under its own module name,
so a list defined there and imported by a test module would be a second, empty copy.
"""

from typing import Any

from fastapi.testclient import TestClient

from trip_planner.integrations.tpp.contracts import TPPResponseEnvelope

TPP_SENT: list[dict[str, Any]] = []


def _blocked_response(request: Any) -> TPPResponseEnvelope:
    return TPPResponseEnvelope.from_dict(
        {
            "operation": request.operation,
            "request_id": request.request_id,
            "correlation_id": request.correlation_id.to_dict(),
            "transport_pattern": "sync",
            "execution_status": {"state": "accepted", "terminal": False, "summary": "queued"},
            "result_payload": {"execution_id": "exec-test", "queue_state": "queued"},
        }
    )


def seed_policy(client: TestClient, trip_id: str) -> None:
    response = client.post(f"/api/workspace/{trip_id}/policy/sync", json={})
    assert response.status_code == 200, response.text
