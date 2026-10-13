"""Production consumer and pinned producer routes, real HTTP/auth/SQLite, no response mocks."""

import json
import socket
import threading
import time
from datetime import date, timedelta
from importlib import import_module

import pytest
import uvicorn
from fastapi.testclient import TestClient

from tests.integration.test_tpp_portal_contract import http_service
from trip_planner.app.main import create_app
from trip_planner.app.services.auth import SESSION_COOKIE_NAME, create_session_for_user
from trip_planner.persistence.models.account import UserAccount


@pytest.mark.parametrize("action,decision", [("approve", "approved"), ("reject", "rejected")])
def test_authenticated_real_two_app_approval_status_roundtrip(
    saved_portal_handoff, monkeypatch, tmp_path, action, decision
):
    session, user, trip_id, original = saved_portal_handoff
    auth = import_module("travel_plan_permission.planner_auth")
    permission = import_module("travel_plan_permission.security").Permission
    monkeypatch.setenv("TPP_OIDC_PROVIDER", "google")
    monkeypatch.setenv("TPP_AUTH_MODE", "bootstrap-token")
    monkeypatch.setenv("TPP_BOOTSTRAP_SIGNING_SECRET", "bootstrap-secret-123")
    monkeypatch.setenv("TPP_HANDOFF_SIGNING_SECRET", "test-handoff-signing-secret")
    token = auth.mint_bootstrap_token(
        subject="issued-traveler-a",
        permissions=(permission.VIEW, permission.CREATE),
        provider="google",
        secret="bootstrap-secret-123",
        expires_in_seconds=600,
    )
    manager_token = auth.mint_bootstrap_token(
        subject="issued-manager",
        permissions=(permission.VIEW, permission.APPROVE),
        provider="google",
        secret="bootstrap-secret-123",
        expires_in_seconds=600,
    )
    identities = tmp_path / "identities.json"
    identities.write_text(
        json.dumps(
            {
                "schema_version": "tpp-owner-identities/v1",
                "users": {
                    user.user_id: {
                        "namespace": "google",
                        "subject": "issued-traveler-a",
                        "authorization": f"Bearer {token}",
                    }
                },
            }
        )
    )
    identities.chmod(0o600)
    monkeypatch.setenv("TRIP_PLANNER_TPP_IDENTITIES_FILE", str(identities))
    store = http_service.PlannerProposalStore(state_path=tmp_path / "producer.sqlite3")
    producer_app = http_service.create_app(store)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    origin = f"http://127.0.0.1:{sock.getsockname()[1]}"
    monkeypatch.setenv("TPP_BASE_URL", origin)
    monkeypatch.setenv("TPP_PORTAL_BASE_URL", origin)
    server = uvicorn.Server(uvicorn.Config(producer_app, log_level="error", lifespan="off"))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.started
    answers = {
        "destination_zip": "20001",
        "booking_date": (
            date.fromisoformat(original["fields"]["depart_date"]) - timedelta(days=30)
        ).isoformat(),
        "selected_fare": "430.00",
        "lowest_fare": "430.00",
        "fare_evidence_attached": "true",
        "cabin_class": "economy",
        "flight_duration_hours": "2.5",
    }
    cookie, _ = create_session_for_user(session, user=session.get(UserAccount, user.user_id))
    path = f"/api/workspace/{trip_id}/proposal/handoff"
    try:
        with TestClient(create_app()) as consumer, TestClient(producer_app) as traveler:
            assert not consumer.app.dependency_overrides
            consumer.cookies.set(SESSION_COOKIE_NAME, cookie)
            prepared = consumer.post(path, json={"traveler_answers": answers})
            assert prepared.status_code == 200, prepared.text
            payload = prepared.json()
            assert set(payload["fields"]) == {"handoff_token"}
            assert token not in prepared.text
            review = traveler.post("/portal/handoff/receipt", data=payload["fields"])
            assert review.status_code == 200, review.text
            draft = next(iter(store.portal_drafts_by_id.values()))
            assert draft.receipt_binding.owner_subject == "issued-traveler-a"
            assert not store.list_manager_reviews()
            # The view capability is not submission authority.
            assert traveler.post(f"/portal/review/{draft.draft_id}/submit").status_code == 401
            submitted = consumer.post(path + "/submit", json={})
            assert submitted.status_code == 200, submitted.text
            pending = consumer.post(path + "/status", json={})
            assert pending.status_code == 200, pending.text
            handoff = pending.json()["proposal_state"]["portal_handoff"]
            assert handoff["manager_submission_status"] == "pending_review"
            manager_review = store.lookup_manager_review_for_draft(draft.draft_id)
            result = traveler.post(
                f"/portal/manager/reviews/{manager_review.review_id}/decision",
                headers={"Authorization": f"Bearer {manager_token}"},
                data={"action": action, "rationale": "Actual authenticated manager decision"},
                follow_redirects=False,
            )
            assert result.status_code == 303, result.text
        # A new production consumer instance resolves credentials and persisted correlation again.
        with TestClient(create_app()) as restarted:
            restarted.cookies.set(SESSION_COOKIE_NAME, cookie)
            final = restarted.post(path + "/status", json={})
            assert final.status_code == 200, final.text
            observed = final.json()["proposal_state"]["portal_handoff"]
            assert observed["manager_submission_status"] == "decision_recorded"
            assert observed["manager_decision"] == decision
            assert observed["manager_decision_at"]
            assert token not in final.text and payload["fields"]["handoff_token"] not in final.text
            replay = restarted.post(path, json={})
            assert replay.status_code == 200, replay.text
            assert len(store.portal_drafts_by_id) == len(store.list_manager_reviews()) == 1
            changed = restarted.post(
                path, json={"traveler_answers": {**answers, "destination_zip": "20002"}}
            )
            assert changed.status_code == 409
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
        store.close()
