"""Verify the planner half of the portal contract without the optional sibling."""

from copy import deepcopy
from dataclasses import replace

import pytest
from fastapi import HTTPException, Response

from trip_planner.app.routes.proposal import prepare_workspace_proposal_portal_handoff
from trip_planner.app.schemas.proposal import WorkspaceProposalHandoffRequest
from trip_planner.app.services.proposal import (
    get_workspace_proposal_payload,
    save_workspace_proposal_evaluation,
)
from trip_planner.app.services.trip_prices import save_trip_price
from trip_planner.app.services.trips import update_trip
from trip_planner.persistence.db import get_session_factory
from trip_planner.persistence.models.proposal import PersistedProposalState
from trip_planner.persistence.models.trip import PersistedTrip
from trip_planner.persistence.models.trip_price import PersistedTripPrice


@pytest.mark.parametrize("already_prepared", [False, True], ids=["first-handoff", "retry"])
@pytest.mark.parametrize("concurrent_change", ["trip", "price", "removed-price", "cleared-verdict"])
def test_form_preparation_rechecks_facts_changed_while_building_the_form(
    saved_portal_handoff, monkeypatch, already_prepared: bool, concurrent_change: str
) -> None:
    session, user, trip_id, original_form = saved_portal_handoff
    stored = session.get(PersistedProposalState, f"proposal-state:{trip_id}")
    trip = session.get(PersistedTrip, trip_id)
    price_id = f"trip-price:{trip_id}:transport"
    price = session.get(PersistedTripPrice, price_id)
    assert stored is not None and trip is not None and price is not None
    if not already_prepared:
        stored.portal_handoff = {
            **stored.portal_handoff,
            "status": "eligible",
            "prepared_at": None,
        }
        session.commit()
    session.expire_all()
    before = deepcopy(stored.portal_handoff)
    verdict = deepcopy(stored.evaluation_record)
    revision = stored.updated_at
    trip_updated_at = trip.updated_at
    original_amount = price.amount

    def edit_facts_while_building_form(snapshot):
        # Use a separate committed transaction, as a second workspace request
        # would. These edits leave the proposal revision unchanged.
        with get_session_factory()() as another_session:
            if concurrent_change == "trip":
                edited_trip = another_session.get(PersistedTrip, trip_id)
                assert edited_trip is not None
                edited_trip.title = "Changed during form preparation"
            elif concurrent_change == "cleared-verdict":
                # The production edit service deletes the saved verdict when
                # a policy determinant such as the trip purpose changes.
                assert (
                    update_trip(
                        another_session,
                        user=user,
                        trip_id=trip_id,
                        changes={"summary": "Changed during form preparation"},
                    )
                    is not None
                )
            else:
                edited_price = another_session.get(PersistedTripPrice, price_id)
                assert edited_price is not None
                if concurrent_change == "price":
                    edited_price.amount += 100
                else:
                    another_session.delete(edited_price)
            another_session.commit()
        return original_form["fields"]

    with monkeypatch.context() as delayed_form:
        delayed_form.setattr(
            "trip_planner.app.services.proposal.build_portal_fields",
            edit_facts_while_building_form,
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
    if concurrent_change == "cleared-verdict":
        assert session.query(PersistedProposalState).filter_by(trip_id=trip_id).count() == 0
        assert trip.summary == "Changed during form preparation"
        assert trip.updated_at != trip_updated_at
        return
    assert stored.portal_handoff == before
    assert stored.evaluation_record == verdict
    assert stored.updated_at == revision
    if concurrent_change == "trip":
        assert trip.title == "Changed during form preparation"
        assert trip.updated_at != trip_updated_at
    else:
        assert trip.updated_at == trip_updated_at
        edited_price = session.get(PersistedTripPrice, price_id)
        if concurrent_change == "price":
            assert edited_price is not None and edited_price.amount == original_amount + 100
        else:
            assert edited_price is None
    # The next request still refuses the obsolete verdict; no stale form was
    # committed that could make a retry look prepared for the changed facts.
    with pytest.raises(HTTPException) as retry:
        prepare_workspace_proposal_portal_handoff(
            trip_id=trip_id,
            _payload=WorkspaceProposalHandoffRequest(),
            response=Response(),
            user=user,
            db_session=session,
        )
    assert retry.value.status_code == (422 if concurrent_change == "removed-price" else 409)


@pytest.mark.parametrize("already_prepared", [False, True], ids=["first-handoff", "retry"])
@pytest.mark.parametrize("concurrent_change", ["policy-check", "authenticated-preparation"])
def test_form_preparation_cannot_overwrite_a_newer_saved_proposal(
    saved_portal_handoff, monkeypatch, already_prepared, concurrent_change
) -> None:
    session, user, trip_id, original_form = saved_portal_handoff
    stored = session.get(PersistedProposalState, f"proposal-state:{trip_id}")
    trip = session.get(PersistedTrip, trip_id)
    assert stored is not None and trip is not None
    if not already_prepared:
        stored.portal_handoff = {
            **stored.portal_handoff,
            "status": "eligible",
            "prepared_at": None,
        }
        session.commit()
    trip_updated_at = trip.updated_at
    newer_state: dict[str, object] = {}

    def save_newer_proposal_while_building_form(snapshot):
        with get_session_factory()() as another_session:
            newer = another_session.get(PersistedProposalState, stored.proposal_state_id)
            assert newer is not None
            if concurrent_change == "policy-check":
                result = deepcopy(newer.evaluation_record)
                result["evaluation_result"]["evaluation_id"] = "newer-policy-check"
                newer.evaluation_record = result
                newer.portal_handoff = {
                    **newer.portal_handoff,
                    "status": "eligible",
                    "prepared_at": None,
                    "source_snapshot_hash": "sha256:" + "a" * 64,
                }
            else:
                newer.portal_handoff = {
                    **newer.portal_handoff,
                    "producer_binding": {
                        "handoff_id": "newer-handoff",
                        "snapshot_version": "v1",
                        "snapshot_sha256": "b" * 64,
                        "draft_id": "newer-draft",
                    },
                    "producer_owner": {"namespace": "test-owner", "subject": "traveler"},
                }
            another_session.commit()
            another_session.refresh(newer)
            newer_state.update(
                handoff=deepcopy(newer.portal_handoff),
                evaluation=deepcopy(newer.evaluation_record),
                updated_at=newer.updated_at,
            )
        return original_form["fields"]

    monkeypatch.setattr(
        "trip_planner.app.services.proposal.build_portal_fields",
        save_newer_proposal_while_building_form,
    )
    response = Response()
    with pytest.raises(HTTPException) as rejected:
        prepare_workspace_proposal_portal_handoff(
            trip_id=trip_id,
            _payload=WorkspaceProposalHandoffRequest(),
            response=response,
            user=user,
            db_session=session,
        )
    assert rejected.value.status_code == 409
    assert "newer-draft" not in rejected.value.detail
    session.expire_all()
    assert stored.portal_handoff == newer_state["handoff"]
    assert stored.evaluation_record == newer_state["evaluation"]
    assert stored.updated_at == newer_state["updated_at"]
    assert trip.updated_at == trip_updated_at


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
@pytest.mark.parametrize(
    ("result_field", "new_value"),
    [
        ("evaluation_id", "eval-rechecked-same-status"),
        (
            "approval_requirements",
            [{"role": "manager", "reason": "Revised approval reason", "mandatory": True}],
        ),
        (
            "approval_requirements",
            [{"role": "manager", "reason": "International travel", "mandatory": False}],
        ),
        ("exception_guidance", ["Use the revised exception process"]),
        ("notes", ["Revised policy detail with the same compliant verdict"]),
        ("compliance_score", 0.95),
    ],
    ids=["evaluation-id", "approval-reason", "mandatory-approval", "guidance", "notes", "score"],
)
def test_handoff_binds_policy_details_even_when_the_form_and_verdict_status_are_unchanged(
    saved_portal_handoff,
    already_prepared: bool,
    result_field: str,
    new_value: object,
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
    original_handoff = deepcopy(stored.portal_handoff)
    original_evaluation = deepcopy(stored.evaluation_record)
    changed_result = deepcopy(original_evaluation["evaluation_result"])
    changed_result[result_field] = new_value
    assert changed_result["status"] == original_evaluation["evaluation_result"]["status"]

    # A changed saved result cannot reuse the original binding merely because
    # its headline verdict and browser prefill still look the same.
    stored.evaluation_record = {**original_evaluation, "evaluation_result": changed_result}
    session.commit()
    trip = session.get(PersistedTrip, trip_id)
    assert trip is not None
    updated_at = trip.updated_at
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
    assert stored.portal_handoff == original_handoff
    assert stored.evaluation_record["evaluation_result"] == changed_result
    assert trip.updated_at == updated_at

    # Ingest the fresh result through the real policy service, then prepare a
    # new form. Its hash must bind the complete result, not just displayed fields.
    request_payload = {
        "operation": "fetch_evaluation_result",
        "request_id": original_evaluation["request_id"],
        "correlation_id": original_evaluation["correlation_id"],
        "transport_pattern": original_evaluation["transport_pattern"],
        "organization_id": stored.organization_id,
        "trip_id": trip_id,
        "proposal_id": stored.proposal_id,
        "payload": original_evaluation["request_payload"],
    }
    response_payload = {
        **request_payload,
        "execution_status": original_evaluation["execution_status"],
        "result_payload": {
            **original_evaluation["response_payload"],
            "evaluation_result": changed_result,
        },
    }
    refreshed = save_workspace_proposal_evaluation(
        session,
        user=user,
        trip_id=trip_id,
        request_payload=request_payload,
        response_payload=response_payload,
        proposal_version=stored.proposal_version,
        scenario_id=stored.scenario_id,
    )
    metadata = refreshed["proposal_state"]["portal_handoff"]
    assert metadata["status"] == "eligible"
    assert metadata["prepared_at"] is None
    assert metadata["source_snapshot_hash"] != original_handoff["source_snapshot_hash"]
    assert "source_snapshot" not in metadata

    response = Response()
    fresh_form = prepare_workspace_proposal_portal_handoff(
        trip_id=trip_id,
        _payload=WorkspaceProposalHandoffRequest(),
        response=response,
        user=user,
        db_session=session,
    ).model_dump()
    assert fresh_form["action_url"] == original_form["action_url"]
    assert fresh_form["method"] == "POST"
    assert fresh_form["fields"] == original_form["fields"]
    assert response.headers["cache-control"] == "no-store"
    assert fresh_form["handoff"]["source_snapshot_hash"] == metadata["source_snapshot_hash"]
    assert fresh_form["handoff"]["status"] == "prepared"
    assert fresh_form["handoff"]["manager_submission_status"] == "unknown"
    assert fresh_form["handoff"]["manager_decision"] is None
    session.expire_all()
    reloaded = get_workspace_proposal_payload(session, user=user, trip_id=trip_id)
    assert reloaded["proposal_state"]["portal_handoff"] == fresh_form["handoff"]


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
@pytest.mark.parametrize(
    "invalid_fields",
    [
        {},
        {"source_snapshot": "Private saved quote"},
        {"return_url": "https://another.example/receive"},
        {"destination_zip": "Private saved quote"},
        {"manager_decision": "approved"},
        {"submit": "Private saved quote"},
        {"notes": {"quote": "Private saved quote"}},
        {"traveler_name": None},
        {"selected_fare": 430.0},
        {"fare_evidence_attached": True},
    ],
    ids=[
        "empty-form",
        "private-snapshot",
        "caller-redirect",
        "traveler-completed-field",
        "invented-decision",
        "native-submit-shadow",
        "nested-notes",
        "missing-traveler",
        "numeric-fare",
        "boolean-evidence",
    ],
)
def test_invalid_form_preserves_saved_handoff_and_allows_retry(
    saved_portal_handoff,
    monkeypatch: pytest.MonkeyPatch,
    already_prepared: bool,
    invalid_fields: dict,
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

    # An empty form and a valid prefill with an unexpected field must both fail
    # before preparation is committed. This exercises the saved-verdict route,
    # rather than only validating a response model without persistence.
    generated_fields = {**handoff["fields"], **invalid_fields} if invalid_fields else {}
    with monkeypatch.context() as failed_mapping:
        failed_mapping.setattr(
            "trip_planner.app.services.proposal.build_portal_fields",
            lambda snapshot: generated_fields,
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
    assert "Private saved quote" not in str(rejected.value.detail)
    assert "Morgan Planner" not in str(rejected.value.detail)
    assert "another.example" not in str(rejected.value.detail)
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


@pytest.mark.parametrize("already_prepared", [False, True], ids=["first-handoff", "retry"])
@pytest.mark.parametrize(
    "portal_origin",
    ["http://portal.example", "https://portal.example/api", "https://portal.example:25"],
    ids=["insecure", "non-origin", "browser-blocked-port"],
)
def test_invalid_explicit_portal_never_falls_back_to_a_valid_policy_api(
    saved_portal_handoff,
    monkeypatch: pytest.MonkeyPatch,
    already_prepared: bool,
    portal_origin: str,
) -> None:
    session, user, trip_id, original_form = saved_portal_handoff
    stored = session.get(PersistedProposalState, f"proposal-state:{trip_id}")
    trip = session.get(PersistedTrip, trip_id)
    assert stored is not None and trip is not None
    if not already_prepared:
        stored.portal_handoff = {
            **stored.portal_handoff,
            "status": "eligible",
            "prepared_at": None,
        }
        session.commit()
    saved_handoff = deepcopy(stored.portal_handoff)
    saved_verdict = deepcopy(stored.evaluation_record)
    updated_at = trip.updated_at
    monkeypatch.setenv("TRIP_PLANNER_ENV", "production")
    monkeypatch.setenv("TPP_BASE_URL", "https://policy-api.example")
    monkeypatch.setenv("TPP_PORTAL_BASE_URL", portal_origin)

    def unexpected_mapping(*args, **kwargs):
        pytest.fail("An invalid portal destination must not generate traveler form fields")

    def unexpected_policy_call(*args, **kwargs):
        pytest.fail("Configuration recovery must use the saved policy verdict")

    monkeypatch.setattr(
        "trip_planner.app.services.proposal.HTTPTPPIntegrationClient", unexpected_policy_call
    )
    with monkeypatch.context() as invalid_configuration:
        invalid_configuration.setattr(
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
    assert rejected.value.status_code == 503
    session.expire_all()
    assert stored.portal_handoff == saved_handoff
    assert stored.evaluation_record == saved_verdict
    assert trip.updated_at == updated_at

    monkeypatch.setenv("TPP_PORTAL_BASE_URL", "https://tpp.example")
    response = Response()
    retried = prepare_workspace_proposal_portal_handoff(
        trip_id=trip_id,
        _payload=WorkspaceProposalHandoffRequest(),
        response=response,
        user=user,
        db_session=session,
    ).model_dump()
    assert retried["action_url"] == "https://tpp.example/portal/handoff"
    assert retried["method"] == "POST"
    assert retried["fields"] == original_form["fields"]
    assert response.headers["cache-control"] == "no-store"
    assert retried["handoff"]["source_snapshot_hash"] == saved_handoff["source_snapshot_hash"]
    assert retried["handoff"]["manager_submission_status"] == "unknown"
    assert retried["handoff"]["manager_decision"] is None
    if already_prepared:
        assert retried == original_form
    session.expire_all()
    assert stored.evaluation_record == saved_verdict
    assert (
        get_workspace_proposal_payload(session, user=user, trip_id=trip_id)["proposal_state"][
            "portal_handoff"
        ]
        == retried["handoff"]
    )


@pytest.mark.parametrize("already_prepared", [False, True])
@pytest.mark.parametrize("setting", ["TPP_PORTAL_BASE_URL", "TPP_BASE_URL"])
@pytest.mark.parametrize(
    "hostname",
    [
        "tpp。123",
        "１２７．１",
        "tpp.example\u200b",
        "[v1.tpp.example]",
        "tpp.example:0",
        "tpp.example:25",
        "[::1]:6000",
    ],
)
def test_browser_invalid_origin_preserves_saved_verdict_until_valid_configuration_retry(
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
