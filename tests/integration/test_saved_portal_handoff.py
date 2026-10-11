"""Verify the planner half of the portal contract without the optional sibling."""

from copy import deepcopy
from dataclasses import replace

import pytest
from fastapi import HTTPException, Response

from trip_planner.app.routes.proposal import prepare_workspace_proposal_portal_handoff
from trip_planner.app.schemas.proposal import WorkspaceProposalHandoffRequest
from trip_planner.app.services.proposal import get_workspace_proposal_payload
from trip_planner.app.services.trip_prices import save_trip_price
from trip_planner.persistence.models.proposal import PersistedProposalState
from trip_planner.persistence.models.trip import PersistedTrip
from trip_planner.persistence.models.trip_price import PersistedTripPrice


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


@pytest.mark.parametrize(
    "saved_portal_handoff",
    [
        {
            "lowest_amount": 350.0,
            "cabin_class": "business",
            "flight_hours": 8.5,
            "evidence_attested": True,
        },
        {
            "lowest_amount": 0.0,
            "cabin_class": "economy",
            "flight_hours": 1.0,
            "evidence_attested": False,
        },
    ],
    indirect=True,
    ids=["attested-business-quote", "unattested-zero-lowest-fare"],
)
def test_saved_flight_facts_prefill_the_form_without_inventing_airfare(
    saved_portal_handoff, monkeypatch: pytest.MonkeyPatch
) -> None:
    session, user, trip_id, first_form = saved_portal_handoff
    price = session.get(PersistedTripPrice, f"trip-price:{trip_id}:transport")
    assert price is not None
    expected_flight_fields = {
        "lowest_cost_roundtrip": f"{price.lowest_amount:.2f}",
        "lowest_fare": f"{price.lowest_amount:.2f}",
        "cabin_class": price.cabin_class,
        "flight_duration_hours": str(price.flight_hours),
        "fare_evidence_attached": "true" if price.evidence_attested else "false",
    }
    saved_metadata = deepcopy(first_form["handoff"])
    session.expire_all()

    # Once checked and saved, preparing the browser body needs no new policy call.
    def unexpected_policy_call(*args, **kwargs):
        pytest.fail("Preparing the form must use the saved verdict and price facts")

    monkeypatch.setattr(
        "trip_planner.app.services.proposal.HTTPTPPIntegrationClient",
        unexpected_policy_call,
    )
    response = Response()
    form = prepare_workspace_proposal_portal_handoff(
        trip_id=trip_id,
        _payload=WorkspaceProposalHandoffRequest(),
        response=response,
        user=user,
        db_session=session,
    ).model_dump()

    assert form["action_url"] == "https://tpp.example/portal/handoff"
    assert form["method"] == "POST"
    assert response.headers["cache-control"] == "no-store"
    assert form["fields"].items() >= expected_flight_fields.items()
    # The persisted transport amount can include ground travel, so it is not airfare.
    assert {"selected_fare", "flight_cost", "flight_pref_outbound.roundtrip_cost"}.isdisjoint(
        form["fields"]
    )
    assert "USD 430.00" in form["fields"]["notes"]
    assert form["handoff"] == saved_metadata
    assert form == first_form
    assert "source_snapshot" not in form["handoff"]

    # Withdrawing those facts invalidates the saved form rather than reusing its prefill.
    save_trip_price(
        session,
        user=user,
        trip_id=trip_id,
        component="transport",
        amount=430.0,
        note="United.com quote",
    )
    with pytest.raises(HTTPException) as rejected:
        prepare_workspace_proposal_portal_handoff(
            trip_id=trip_id,
            _payload=WorkspaceProposalHandoffRequest(),
            response=Response(),
            user=user,
            db_session=session,
        )
    assert rejected.value.status_code == 409
    session.expire_all()
    assert (
        get_workspace_proposal_payload(session, user=user, trip_id=trip_id)["proposal_state"][
            "portal_handoff"
        ]
        == saved_metadata
    )


@pytest.mark.parametrize("already_prepared", [False, True])
def test_another_traveler_cannot_prepare_the_owners_saved_handoff(
    saved_portal_handoff, monkeypatch: pytest.MonkeyPatch, already_prepared: bool
) -> None:
    session, user, trip_id, original_form = saved_portal_handoff
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
    other_traveler = replace(user, user_id="another-portal-owner")

    def unexpected_mapping(snapshot):
        pytest.fail("Another traveler must be rejected before form fields are generated")

    with monkeypatch.context() as guarded:
        guarded.setattr(
            "trip_planner.app.services.proposal.build_portal_fields", unexpected_mapping
        )
        failures = []
        # A real trip owned by someone else must be indistinguishable from a
        # missing trip to the caller, and must not change its saved preparation.
        for requested_trip in (trip_id, "missing-portal-trip"):
            with pytest.raises(HTTPException) as denied:
                prepare_workspace_proposal_portal_handoff(
                    trip_id=requested_trip,
                    _payload=WorkspaceProposalHandoffRequest(),
                    response=Response(),
                    user=other_traveler,
                    db_session=session,
                )
            assert denied.value.status_code == 404
            assert requested_trip not in denied.value.detail
            failures.append(denied.value.detail.split(" Reference ID:", maxsplit=1)[0])
        assert failures[0] == failures[1]

    session.expire_all()
    assert stored.portal_handoff == before
    assert stored.evaluation_record == verdict
    assert trip.updated_at == updated_at
    owner_form = prepare_workspace_proposal_portal_handoff(
        trip_id=trip_id,
        _payload=WorkspaceProposalHandoffRequest(),
        response=Response(),
        user=user,
        db_session=session,
    ).model_dump()
    assert owner_form["fields"] == original_form["fields"]
    assert owner_form["handoff"]["source_snapshot_hash"] == before["source_snapshot_hash"]
    assert owner_form["handoff"]["manager_submission_status"] == "unknown"
    assert owner_form["handoff"]["manager_decision"] is None
    if already_prepared:
        assert owner_form == original_form


@pytest.mark.parametrize("already_prepared", [False, True])
@pytest.mark.parametrize("price_change", ["added", "removed"])
def test_changed_price_set_cannot_prepare_a_form_from_the_original_verdict(
    saved_portal_handoff,
    monkeypatch: pytest.MonkeyPatch,
    already_prepared: bool,
    price_change: str,
) -> None:
    session, user, trip_id, _ = saved_portal_handoff
    stored = session.get(PersistedProposalState, f"proposal-state:{trip_id}")
    assert stored is not None
    if not already_prepared:
        stored.portal_handoff = {
            **stored.portal_handoff,
            "status": "eligible",
            "prepared_at": None,
        }
    price = session.get(PersistedTripPrice, f"trip-price:{trip_id}:transport")
    assert price is not None
    if price_change == "added":
        session.add(
            PersistedTripPrice(
                trip_price_id=f"trip-price:{trip_id}:lodging",
                trip_id=trip_id,
                user_id=user.user_id,
                component="lodging",
                amount=250.0,
                currency=price.currency,
                entered_by=price.entered_by,
                captured_at=price.captured_at,
                note="New hotel quote after the policy check",
            )
        )
    else:
        session.delete(price)
    session.commit()
    before = deepcopy(stored.portal_handoff)
    verdict = deepcopy(stored.evaluation_record)
    trip = session.get(PersistedTrip, trip_id)
    assert trip is not None
    updated_at = trip.updated_at

    def unexpected_mapping(snapshot):
        pytest.fail("Changed price sets must be rejected before preparing traveler form fields")

    monkeypatch.setattr(
        "trip_planner.app.services.proposal.build_portal_fields", unexpected_mapping
    )
    with pytest.raises(HTTPException) as rejected:
        prepare_workspace_proposal_portal_handoff(
            trip_id=trip_id,
            _payload=WorkspaceProposalHandoffRequest(),
            response=Response(),
            user=user,
            db_session=session,
        )

    # Removing the final sourced price is unpriced; adding one makes the verdict stale.
    assert rejected.value.status_code == (409 if price_change == "added" else 422)
    session.expire_all()
    assert stored.portal_handoff == before
    assert stored.evaluation_record == verdict
    assert trip.updated_at == updated_at
    reloaded = get_workspace_proposal_payload(session, user=user, trip_id=trip_id)
    assert (
        reloaded["proposal_state"]["portal_handoff"]["source_snapshot_hash"]
        == before["source_snapshot_hash"]
    )
    assert "source_snapshot" not in reloaded["proposal_state"]["portal_handoff"]


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


@pytest.mark.parametrize("already_prepared", [False, True])
@pytest.mark.parametrize("setting", ["TPP_PORTAL_BASE_URL", "TPP_BASE_URL"])
@pytest.mark.parametrize("hostname", ["tpp。123", "１２７．１", "tpp.example\u200b"])
def test_unicode_origin_preserves_saved_verdict_until_ascii_configuration_retry(
    saved_portal_handoff,
    monkeypatch: pytest.MonkeyPatch,
    already_prepared: bool,
    setting: str,
    hostname: str,
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
    before = deepcopy(get_workspace_proposal_payload(session, user=user, trip_id=trip_id))
    trip = session.get(PersistedTrip, trip_id)
    assert trip is not None
    updated_at = trip.updated_at
    monkeypatch.setenv("TRIP_PLANNER_ENV", "production")
    monkeypatch.delenv("TPP_PORTAL_BASE_URL", raising=False)
    monkeypatch.delenv("TPP_BASE_URL", raising=False)
    monkeypatch.setenv(setting, f"https://{hostname}")

    with pytest.raises(HTTPException) as rejected:
        prepare_workspace_proposal_portal_handoff(
            trip_id=trip_id,
            _payload=WorkspaceProposalHandoffRequest(),
            response=Response(),
            user=user,
            db_session=session,
        )

    assert rejected.value.status_code == 503
    session.expire_all()
    assert get_workspace_proposal_payload(session, user=user, trip_id=trip_id) == before
    assert trip.updated_at == updated_at

    monkeypatch.setenv(setting, "https://xn--bcher-kva.example:8443")
    response = Response()
    retried = prepare_workspace_proposal_portal_handoff(
        trip_id=trip_id,
        _payload=WorkspaceProposalHandoffRequest(),
        response=response,
        user=user,
        db_session=session,
    ).model_dump()
    assert retried["action_url"] == "https://xn--bcher-kva.example:8443/portal/handoff"
    assert retried["fields"] == handoff["fields"]
    assert retried["method"] == "POST"
    assert response.headers["cache-control"] == "no-store"
    assert retried["handoff"]["status"] == "prepared"
    assert retried["handoff"]["source_snapshot_hash"] == handoff["handoff"]["source_snapshot_hash"]
    assert retried["handoff"]["manager_submission_status"] == "unknown"
    assert retried["handoff"]["manager_decision"] is None
    assert "source_snapshot" not in retried["handoff"]
    session.expire_all()
    assert (
        get_workspace_proposal_payload(session, user=user, trip_id=trip_id)["proposal_state"][
            "portal_handoff"
        ]
        == retried["handoff"]
    )
