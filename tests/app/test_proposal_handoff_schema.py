"""Enforce the public browser handoff's preparation-only response contract."""

import pytest
from pydantic import ValidationError

from trip_planner.app.schemas.proposal import WorkspaceProposalHandoffResponse


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
