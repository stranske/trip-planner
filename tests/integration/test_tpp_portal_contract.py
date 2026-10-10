from __future__ import annotations

import os
import re
import sys
from datetime import date, timedelta
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.integration.portal_contract_checkout import resolve_portal_contract_checkout
from trip_planner.app.services.proposal import get_workspace_proposal_payload

TPP_REPO_PATH = resolve_portal_contract_checkout(os.environ)
if TPP_REPO_PATH is None:
    pytest.skip(
        "TPP_REPO_PATH is required for the cross-repo portal contract", allow_module_level=True
    )

TPP_SOURCE_PATH = TPP_REPO_PATH / "src"
sys.path.insert(0, str(TPP_SOURCE_PATH))

# TPP is an optional sibling checkout, not a trip-planner dependency. Resolve it
# dynamically only after the explicit cross-repo path gate above.
http_service: Any = import_module("travel_plan_permission.http_service")


def test_trip_planner_handoff_reaches_tpp_manager_queue(
    monkeypatch: pytest.MonkeyPatch,
    saved_portal_handoff,
) -> None:
    # An already-installed TPP package must not silently replace the pinned checkout.
    assert Path(http_service.__file__).resolve().is_relative_to(TPP_SOURCE_PATH)
    monkeypatch.setenv("TPP_BASE_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("TPP_OIDC_PROVIDER", "google")
    monkeypatch.setenv("TPP_AUTH_MODE", "static-token")
    monkeypatch.setenv("TPP_ACCESS_TOKEN", "dev-token")
    monkeypatch.setenv("TPP_HANDOFF_SIGNING_SECRET", "test-handoff-signing-secret")

    store = http_service.PlannerProposalStore()
    client = TestClient(http_service.create_app(store))
    session, user, trip_id, handoff = saved_portal_handoff
    fields = handoff["fields"]

    prefill = client.post("/portal/handoff", data=fields)
    assert prefill.status_code == 200
    assert "tpp_portal_handoff=" in prefill.headers["set-cookie"]
    assert prefill.request.headers["content-type"] == "application/x-www-form-urlencoded"
    assert not prefill.request.url.query
    assert not store.portal_drafts_by_id
    assert not store.list_manager_reviews()

    # TPP deliberately requires the traveler to complete facts trip-planner does not own.
    incomplete = client.post("/portal/handoff/draft", data=fields, follow_redirects=False)
    assert incomplete.status_code == 400
    assert "Destination ZIP" in incomplete.text
    assert not store.portal_drafts_by_id
    assert not store.list_manager_reviews()

    # Supply the traveler-owned facts required by the real producer policy.
    # A saved planner evaluation cannot waive TPP's fresh submission checks.
    completed_fields = {
        **fields,
        "destination_zip": "20001",
        "booking_date": (
            date.fromisoformat(fields["depart_date"]) - timedelta(days=30)
        ).isoformat(),
        "selected_fare": "430.00",
        "lowest_fare": "430.00",
        "fare_evidence_attached": "true",
        "cabin_class": "economy",
        "flight_duration_hours": "2.5",
    }
    completed = client.post(
        "/portal/handoff/draft",
        data=completed_fields,
        follow_redirects=False,
    )
    assert completed.status_code == 303
    match = re.search(r"/portal/review/([^/]+)$", completed.headers["location"])
    assert match is not None
    draft_id = match.group(1)
    assert store.lookup_portal_draft(draft_id) is not None
    assert store.lookup_manager_review_for_draft(draft_id) is None
    assert not store.list_manager_reviews()

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
    assert f"/portal/manager/reviews/{review.review_id}" in queue.text

    # TPP's local manager queue is not a receipt returned to trip-planner.
    # Even after real submission, its persisted handoff must remain preparation-only.
    session.expire_all()
    planner_state = get_workspace_proposal_payload(session, user=user, trip_id=trip_id)
    assert planner_state["proposal_state"]["portal_handoff"] == handoff["handoff"]
    assert handoff["handoff"]["manager_submission_status"] == "unknown"
    assert handoff["handoff"]["manager_decision"] is None
