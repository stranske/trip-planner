"""The planner chat hears places, and knows the verdict the trip already has (issue 1845).

Observed 2026-09-22, asking the message below two minutes after TPP had blocked the trip:
"What I heard - Destinations: My, What, Seattle", then "No policy preview is available in
the current workspace data yet", and only at the very end that the planner was offline.
Every assertion reads the served planner turn.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.app.tpp_intercept import seed_policy
from trip_planner.integrations.tpp import client as tpp_client_module
from trip_planner.integrations.tpp.contracts import TPPResponseEnvelope

MESSAGE = (
    "My approval was blocked for fare comparison. What is the lowest economy fare Seattle "
    "to Chicago on Oct 5, and what do I need to attach?"
)


def _refused(self: Any, request: Any) -> TPPResponseEnvelope:
    return TPPResponseEnvelope.from_dict(
        {
            "operation": request.operation,
            "request_id": request.request_id,
            "correlation_id": request.correlation_id.to_dict(),
            "transport_pattern": "sync",
            "execution_status": {"state": "failed", "terminal": True, "summary": "blocked"},
            "result_payload": {
                "execution_id": "exec-blocked",
                "queue_state": "blocked_by_policy",
                "blocking_codes": ["fare_evidence", "fare_comparison"],
            },
            "error": {
                "code": "proposal_blocked_by_policy",
                "message": "The proposal has blocking policy violations and cannot be submitted.",
                "category": "policy",
                "retryable": False,
            },
        }
    )


@pytest.fixture
def blocked_trip(tpp_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, str]:
    monkeypatch.setattr(tpp_client_module.HTTPTPPIntegrationClient, "submit_proposal", _refused)
    created = tpp_client.post(
        "/api/trips",
        json={
            "title": "Chicago client review",
            "summary": "Quarterly review.",
            "mode": "business",
            "trip_frame": {
                "origin": "Seattle",
                "start_date": "2026-10-05",
                "end_date": "2026-10-07",
                "duration_days": 3,
                "primary_regions": ["Chicago, IL"],
            },
        },
    )
    trip_id = str(created.json()["trip"]["trip_id"])
    seed_policy(tpp_client, trip_id)
    tpp_client.put(
        f"/api/workspace/{trip_id}/prices", json={"component": "transport", "amount": 486.0}
    )
    submitted = tpp_client.post(f"/api/workspace/{trip_id}/proposal/submit", json={})
    assert submitted.status_code == 200, submitted.text
    summary = tpp_client.get(f"/api/workspace/{trip_id}").json()["proposal_state"]["summary"]
    assert summary["submission_outcome"] == "blocked_by_policy", summary
    return tpp_client, trip_id


def _reply(client: TestClient, trip_id: str) -> dict[str, Any]:
    response = client.post(f"/api/planner/{trip_id}/turns", json={"message": MESSAGE})
    assert response.status_code == 200, response.text
    return dict(response.json()["messages"][-1])


def test_capitalised_words_are_not_heard_as_destinations(
    blocked_trip: tuple[TestClient, str],
) -> None:
    client, trip_id = blocked_trip
    turns = client.post(f"/api/planner/{trip_id}/turns", json={"message": MESSAGE}).json()
    user_turn = next(m for m in reversed(turns["messages"]) if m["role"] == "user")
    heard = next(
        block
        for block in user_turn["structured_blocks"]
        if block["kind"] == "traveler_input_summary"
    )

    assert heard["metadata"]["destinations"] == ["Seattle", "Chicago"]


def test_the_reply_states_the_saved_verdict_with_its_rules(
    blocked_trip: tuple[TestClient, str],
) -> None:
    client, trip_id = blocked_trip
    content = _reply(client, trip_id)["content"]

    assert "No policy preview is available" not in content
    assert "The travel policy blocked Chicago client review." in content
    assert "(rule fare_evidence)" in content and "(rule fare_comparison)" in content
    assert "lowest fare you found" in content
    # The limit is stated first, not after the answer.
    assert content.startswith("The planner is offline:")
