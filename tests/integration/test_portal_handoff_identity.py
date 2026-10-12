"""The authenticated browser handoff must use the live workspace session owner."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_workspace_portal_preparation import PreparationClient
from trip_planner.app.main import create_app
from trip_planner.app.services.auth import SESSION_COOKIE_NAME, create_session_for_user
from trip_planner.persistence.models.account import UserAccount
from trip_planner.persistence.models.proposal import PersistedProposalState
from trip_planner.persistence.models.trip import PersistedTrip


@pytest.mark.parametrize("already_bound", [False, True], ids=["first-preparation", "retry"])
def test_live_session_owns_authenticated_handoff_despite_forwarded_identity_headers(
    saved_portal_handoff, monkeypatch, already_bound
):
    session, user, trip_id, original = saved_portal_handoff
    record = session.get(PersistedProposalState, f"proposal-state:{trip_id}")
    saved_snapshot = deepcopy(record.portal_handoff["source_snapshot"])
    account = session.get(UserAccount, user.user_id)
    browser_session, _ = create_session_for_user(session, user=account)
    client = PreparationClient()
    # Resolve both destinations on the server; proxy/browser identity hints must
    # never select the producer account or replace the saved traveler facts.
    monkeypatch.setenv("TRIP_PLANNER_ENV", "production")
    monkeypatch.setenv("TPP_BASE_URL", "https://policy-api.example")
    monkeypatch.setenv("TPP_PORTAL_BASE_URL", "https://traveler-portal.example:8443")
    app = create_app(portal_receipt_client=client)
    assert not app.dependency_overrides
    path = f"/api/workspace/{trip_id}/proposal/handoff"
    with TestClient(app) as browser:
        browser.cookies.set(SESSION_COOKIE_NAME, browser_session)
        if already_bound:
            assert browser.post(path, json={}).status_code == 200
        result = browser.post(
            path,
            json={},
            headers={
                "Origin": "https://caller.example",
                "Forwarded": 'host="caller.example";proto=http',
                "X-Forwarded-Host": "caller.example",
                "X-Forwarded-User": "another-traveler",
                "X-User-Id": "another-traveler",
                "X-TPP-Subject": "another-producer-owner",
            },
        )
        assert result.status_code == 200
        assert result.headers["cache-control"] == "no-store"
        form = result.json()
        assert form["action_url"] == "https://traveler-portal.example:8443/portal/handoff/receipt"
        assert form["method"] == "POST"
        assert form["fields"] == {"handoff_token": client.capability}
        assert client.users == [user.user_id] * (2 if already_bound else 1)
        assert len(client.preparations) == 1
        assert client.preparations[0][2] == original["fields"]
        assert client.reads == (1 if already_bound else 0)
        assert (
            form["handoff"]["source_snapshot_hash"] == original["handoff"]["source_snapshot_hash"]
        )
        assert form["handoff"]["manager_submission_status"] == "unknown"
        assert form["handoff"]["manager_decision"] is None
        public = browser.get(f"/api/workspace/{trip_id}/proposal").json()
        assert public["proposal_state"]["portal_handoff"] == form["handoff"]
        assert client.capability not in str(public)
        assert client.identity.authorization not in str(public)

    session.expire_all()
    record = session.get(PersistedProposalState, f"proposal-state:{trip_id}")
    assert record.portal_handoff["producer_owner"] == client.identity.owner_binding()
    assert record.portal_handoff["producer_origin"] == "https://traveler-portal.example:8443"
    assert record.portal_handoff["source_snapshot"] == saved_snapshot


@pytest.mark.parametrize("already_bound", [False, True], ids=["first-preparation", "retry"])
@pytest.mark.parametrize("session_state", ["missing", "expired", "revoked", "another-owner"])
def test_session_rejection_precedes_authenticated_producer_calls_and_preserves_saved_state(
    saved_portal_handoff, already_bound, session_state
):
    session, user, trip_id, _ = saved_portal_handoff
    owner = session.get(UserAccount, user.user_id)
    owner_session, _ = create_session_for_user(session, user=owner)
    client = PreparationClient()
    app = create_app(portal_receipt_client=client)
    assert not app.dependency_overrides
    path = f"/api/workspace/{trip_id}/proposal/handoff"
    with TestClient(app) as browser:
        browser.cookies.set(SESSION_COOKIE_NAME, owner_session)
        if already_bound:
            assert browser.post(path, json={}).status_code == 200

        account = owner
        if session_state == "another-owner":
            account = UserAccount(
                user_id="another-handoff-owner",
                email="another-handoff-owner@example.test",
                display_name="Another Traveler",
                password_hash="unused",
            )
            session.add(account)
            session.commit()
        rejected_session, auth_record = create_session_for_user(session, user=account)
        if session_state == "expired":
            auth_record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        elif session_state == "revoked":
            auth_record.revoked_at = datetime.now(UTC)
        session.commit()
        browser.cookies.clear()
        if session_state != "missing":
            browser.cookies.set(SESSION_COOKIE_NAME, rejected_session)

        session.expire_all()
        record = session.get(PersistedProposalState, f"proposal-state:{trip_id}")
        trip = session.get(PersistedTrip, trip_id)
        before = deepcopy(record.portal_handoff)
        evaluation = deepcopy(record.evaluation_record)
        revisions = record.updated_at, trip.updated_at
        calls = (list(client.users), deepcopy(client.preparations), list(client.browser_bindings))
        for endpoint in (path, f"{path}/status"):
            denied = browser.post(endpoint, json={}, headers={"X-User-Id": user.user_id})
            assert denied.status_code == (404 if session_state == "another-owner" else 401)
            assert user.display_name not in denied.text
            assert client.capability not in denied.text
            assert (client.users, client.preparations, client.browser_bindings) == calls
            assert client.reads == 0
            session.expire_all()
            assert record.portal_handoff == before
            assert record.evaluation_record == evaluation
            assert (record.updated_at, trip.updated_at) == revisions

        # A valid owner session can still prepare/replay the same saved verdict.
        browser.cookies.clear()
        browser.cookies.set(SESSION_COOKIE_NAME, owner_session)
        retried = browser.post(path, json={})
        assert retried.status_code == 200
        assert retried.json()["handoff"]["source_snapshot_hash"] == before["source_snapshot_hash"]
        assert len(client.preparations) == 1
