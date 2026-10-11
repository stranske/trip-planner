"""Verify the planner half of the portal contract without the optional sibling."""

from copy import deepcopy

import pytest
from fastapi import HTTPException, Response

from trip_planner.app.routes.proposal import prepare_workspace_proposal_portal_handoff
from trip_planner.app.schemas.proposal import WorkspaceProposalHandoffRequest
from trip_planner.app.services.proposal import get_workspace_proposal_payload
from trip_planner.persistence.models.proposal import PersistedProposalState
from trip_planner.persistence.models.trip import PersistedTrip


def test_saved_verdict_produces_portal_form_and_private_snapshot(saved_portal_handoff) -> None:
    session, user, trip_id, handoff = saved_portal_handoff
    assert handoff["action_url"] == "https://tpp.example/portal/handoff"
    assert handoff["method"] == "POST"
    fields = handoff["fields"]
    assert fields["traveler_name"] == "Morgan Planner"
    assert fields["business_purpose"] == "Meet the client team"
    assert fields["city_state"] == "Washington, DC"
    trip = session.get(PersistedTrip, trip_id)
    assert trip is not None
    assert fields["depart_date"] == trip.start_date
    assert fields["return_date"] == trip.end_date
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


@pytest.mark.parametrize("already_prepared", [False, True])
def test_empty_form_preserves_saved_handoff_and_allows_retry(
    saved_portal_handoff, monkeypatch: pytest.MonkeyPatch, already_prepared: bool
) -> None:
    session, user, trip_id, handoff = saved_portal_handoff
    stored = session.get(PersistedProposalState, f"proposal-state:{trip_id}")
    assert stored is not None
    if not already_prepared:
        stored.portal_handoff = {
            **stored.portal_handoff,
            "status": "eligible",
            "prepared_at": None,
        }
        session.commit()
    before = deepcopy(stored.portal_handoff)
    verdict = deepcopy(stored.evaluation_record)
    trip = session.get(PersistedTrip, trip_id)
    assert trip is not None
    updated_at = trip.updated_at

    with monkeypatch.context() as failed_mapping:
        failed_mapping.setattr(
            "trip_planner.app.services.proposal.build_portal_fields", lambda snapshot: {}
        )
        with pytest.raises(HTTPException) as rejected:
            prepare_workspace_proposal_portal_handoff(
                trip_id=trip_id,
                _payload=WorkspaceProposalHandoffRequest(),
                response=Response(),
                user=user,
                db_session=session,
            )

    assert rejected.value.status_code == 422
    session.expire_all()
    assert stored.portal_handoff == before
    assert stored.evaluation_record == verdict
    assert trip.updated_at == updated_at

    response = Response()
    retried = prepare_workspace_proposal_portal_handoff(
        trip_id=trip_id,
        _payload=WorkspaceProposalHandoffRequest(),
        response=response,
        user=user,
        db_session=session,
    ).model_dump()
    assert retried["fields"] == handoff["fields"]
    assert response.headers["cache-control"] == "no-store"
    assert retried["handoff"]["source_snapshot_hash"] == before["source_snapshot_hash"]
    assert retried["handoff"]["status"] == "prepared"
    assert retried["handoff"]["manager_submission_status"] == "unknown"
    assert retried["handoff"]["manager_decision"] is None
    session.expire_all()
    assert (
        get_workspace_proposal_payload(session, user=user, trip_id=trip_id)["proposal_state"][
            "portal_handoff"
        ]
        == retried["handoff"]
    )
