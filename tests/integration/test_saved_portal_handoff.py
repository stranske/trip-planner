"""Verify the planner half of the portal contract without the optional sibling."""

from trip_planner.app.services.proposal import get_workspace_proposal_payload
from trip_planner.persistence.models.proposal import PersistedProposalState


def test_saved_verdict_produces_portal_form_and_private_snapshot(saved_portal_handoff) -> None:
    session, user, trip_id, handoff = saved_portal_handoff
    assert handoff["action_url"] == "https://tpp.example/portal/handoff"
    assert handoff["method"] == "POST"
    fields = handoff["fields"]
    assert fields["traveler_name"] == "Morgan Planner"
    assert fields["business_purpose"] == "Meet the client team"
    assert fields["city_state"] == "Washington, DC"
    assert fields["depart_date"] == "2026-10-12"
    assert fields["return_date"] == "2026-10-14"
    assert "destination_zip" not in fields
    assert "selected_fare" not in fields
    assert "USD 430.00" in fields["notes"]
    assert "United.com quote" in fields["notes"]
    assert "status=compliant" in fields["notes"]
    assert f"proposal=proposal:{trip_id}" in fields["notes"]

    stored = session.get(PersistedProposalState, f"proposal-state:{trip_id}")
    assert stored is not None
    assert stored.portal_handoff["source_snapshot"]["prices"][0]["amount"] == 430.0
    metadata = handoff["handoff"]
    assert "source_snapshot" not in metadata
    assert metadata["source_snapshot_hash"].startswith("sha256:")
    assert metadata["status"] == "prepared"
    assert metadata["manager_submission_status"] == "unknown"
    assert metadata["manager_decision"] is None

    session.expire_all()
    reloaded = get_workspace_proposal_payload(session, user=user, trip_id=trip_id)
    assert reloaded["proposal_state"]["portal_handoff"] == metadata
