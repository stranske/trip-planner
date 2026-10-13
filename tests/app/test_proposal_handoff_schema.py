"""Enforce the public browser handoff's preparation-only response contract."""

import pytest
from pydantic import ValidationError

from trip_planner.app.schemas.proposal import WorkspaceProposalHandoffResponse
from trip_planner.integrations.tpp.portal_handoff import build_portal_fields


def test_handoff_response_preserves_complete_server_mapped_prefill() -> None:
    fields = build_portal_fields(
        {
            "trip_id": "trip-1",
            "proposal_id": "proposal-1",
            "proposal_version": "v1",
            "traveler_name": "Morgan José Planner",
            "trip": {
                "title": "Client visit",
                "origin": "ORD",
                "primary_regions": ["Washington, DC"],
                "start_date": "2027-04-12",
                "end_date": "2027-04-14",
            },
            "prices": [
                {
                    "component": "transport",
                    "amount": 450.0,
                    "currency": "USD",
                    "flight_amount": 430.0,
                    "lowest_amount": 400.0,
                    "evidence_attested": True,
                    "cabin_class": "economy",
                    "flight_hours": 2.5,
                }
            ],
        }
    )
    response = WorkspaceProposalHandoffResponse.model_validate(
        {
            "action_url": "https://tpp.example/portal/handoff",
            "fields": fields,
            "handoff": {
                "schema_version": "tpp-portal-handoff/v1",
                "source_snapshot_hash": f"sha256:{'a' * 64}",
                "prepared_at": "2026-10-10T12:00:00Z",
                "status": "prepared",
                "manager_submission_status": "unknown",
                "manager_decision": None,
            },
        }
    )

    assert response.model_dump()["fields"] == fields


@pytest.mark.parametrize("field", ["source_snapshot", "proposal", "return_url", "destination_zip"])
def test_handoff_response_rejects_fields_outside_the_server_prefill_contract(field: str) -> None:
    with pytest.raises(ValidationError) as rejected:
        WorkspaceProposalHandoffResponse.model_validate(
            {
                "action_url": "https://tpp.example/portal/handoff",
                "method": "POST",
                "fields": {"traveler_name": "Morgan Planner", field: "Private traveler fact"},
                "handoff": {
                    "schema_version": "tpp-portal-handoff/v1",
                    "source_snapshot_hash": f"sha256:{'a' * 64}",
                    "prepared_at": "2026-10-10T12:00:00Z",
                    "status": "prepared",
                    "manager_submission_status": "unknown",
                    "manager_decision": None,
                },
            }
        )

    assert rejected.value.errors()[0]["loc"][:2] == ("fields", field)


def test_handoff_response_rejects_empty_native_form() -> None:
    with pytest.raises(ValidationError) as rejected:
        WorkspaceProposalHandoffResponse.model_validate(
            {
                "action_url": "https://tpp.example/portal/handoff",
                "method": "POST",
                "fields": {},
                "handoff": {
                    "schema_version": "tpp-portal-handoff/v1",
                    "source_snapshot_hash": f"sha256:{'a' * 64}",
                    "prepared_at": "2026-10-10T12:00:00Z",
                    "status": "prepared",
                    "manager_submission_status": "unknown",
                    "manager_decision": None,
                },
            }
        )

    assert rejected.value.errors()[0]["loc"] == ("fields",)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", "sent"),
        ("manager_submission_status", "submitted"),
        ("manager_decision", "approved"),
        ("source_snapshot_hash", "unbound"),
        ("schema_version", "unsupported"),
    ],
)
def test_handoff_response_rejects_unverified_state_or_unbound_metadata(field, value) -> None:
    metadata = {
        "schema_version": "tpp-portal-handoff/v1",
        "source_snapshot_hash": f"sha256:{'a' * 64}",
        "prepared_at": "2026-10-10T12:00:00Z",
        "status": "prepared",
        "manager_submission_status": "unknown",
        "manager_decision": None,
        field: value,
    }

    with pytest.raises(ValidationError) as rejected:
        WorkspaceProposalHandoffResponse.model_validate(
            {
                "action_url": "https://tpp.example/portal/handoff",
                "method": "POST",
                "fields": {"traveler_name": "Morgan Planner"},
                "handoff": metadata,
            }
        )

    assert rejected.value.errors()[0]["loc"] == ("handoff", field)
