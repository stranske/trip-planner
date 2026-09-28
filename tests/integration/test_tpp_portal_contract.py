from __future__ import annotations

import os
import re
import sys
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from trip_planner.integrations.tpp.portal_handoff import build_portal_fields

TPP_REPO_PATH = os.getenv("TPP_REPO_PATH")
if not TPP_REPO_PATH:
    pytest.skip("TPP_REPO_PATH is required for the cross-repo portal contract", allow_module_level=True)

sys.path.insert(0, str(Path(TPP_REPO_PATH).resolve() / "src"))

# TPP is an optional sibling checkout, not a trip-planner dependency. Resolve it
# dynamically only after the explicit cross-repo path gate above.
http_service: Any = import_module("travel_plan_permission.http_service")


def test_trip_planner_handoff_reaches_tpp_manager_queue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TPP_BASE_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("TPP_OIDC_PROVIDER", "google")
    monkeypatch.setenv("TPP_AUTH_MODE", "static-token")
    monkeypatch.setenv("TPP_ACCESS_TOKEN", "dev-token")
    monkeypatch.setenv("TPP_HANDOFF_SIGNING_SECRET", "test-handoff-signing-secret")

    store = http_service.PlannerProposalStore()
    client = TestClient(http_service.create_app(store))
    fields = build_portal_fields(
        {
            "trip_id": "trip-1842",
            "proposal_id": "proposal:trip-1842",
            "proposal_version": "v1",
            "scenario_id": "scenario-1",
            "execution_id": "execution-1",
            "traveler_name": "Morgan Planner",
            "trip": {
                "title": "Washington client visit",
                "summary": "Meet the client team",
                "origin": "ORD",
                "primary_regions": ["Washington, DC"],
                "start_date": "2026-10-12",
                "end_date": "2026-10-14",
            },
            "prices": [
                {
                    "component": "transport",
                    "label": "Transportation",
                    "amount": 430.0,
                    "currency": "USD",
                    "note": "United.com quote",
                    "source": {
                        "attributed_to": "Morgan Planner",
                        "captured_at": "2026-09-28",
                    },
                    "lowest_amount": 400.0,
                    "evidence_attested": True,
                    "cabin_class": "economy",
                    "flight_hours": 2.5,
                }
            ],
            "verdict": {
                "status": "compliant",
                "outcome": "accepted",
                "blocking_codes": [],
            },
        }
    )

    prefill = client.post("/portal/handoff", data=fields)
    assert prefill.status_code == 200
    assert "tpp_portal_handoff=" in prefill.headers["set-cookie"]

    # TPP deliberately requires the traveler to complete facts trip-planner does not own.
    incomplete = client.post("/portal/handoff/draft", data=fields, follow_redirects=False)
    assert incomplete.status_code == 400
    assert "Destination ZIP" in incomplete.text

    completed_fields = {**fields, "destination_zip": "20001"}
    completed = client.post(
        "/portal/handoff/draft",
        data=completed_fields,
        follow_redirects=False,
    )
    assert completed.status_code == 303
    match = re.search(r"/portal/review/([^/]+)$", completed.headers["location"])
    assert match is not None
    draft_id = match.group(1)

    auth_header = {"Authorization": "Bearer dev-token"}
    submitted = client.post(
        f"/portal/review/{draft_id}/submit",
        headers=auth_header,
        follow_redirects=True,
    )
    assert submitted.status_code == 200, submitted.text
    review = store.lookup_manager_review_for_draft(draft_id)
    assert review is not None

    queue = client.get("/portal/manager/reviews", headers=auth_header)
    assert queue.status_code == 200
    assert review.trip_plan.traveler_name in queue.text
    assert "pending_manager_review" in queue.text
