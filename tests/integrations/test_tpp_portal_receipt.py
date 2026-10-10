"""Receipt observations must not turn stale or contradictory data into approval."""

from __future__ import annotations

from typing import Any

import pytest

from trip_planner.integrations.tpp.client import TPPContractError
from trip_planner.integrations.tpp.portal_receipt import (
    PortalReceiptBinding,
    validate_portal_receipt,
)


@pytest.fixture
def binding() -> PortalReceiptBinding:
    return PortalReceiptBinding(
        handoff_id="trip-1842-handoff-1",
        snapshot_version="sha256:" + "b" * 64,
        snapshot_sha256="a" * 64,
        draft_id="draft-1",
    )


def _receipt(binding: PortalReceiptBinding, state: str = "prepared") -> dict[str, Any]:
    payload: dict[str, Any] = {
        **binding.model_dump(),
        "contract_version": "portal-receipt/v1",
        "state": state,
        "prepared_at": "2026-10-10T12:00:00Z",
        "observed_at": "2026-10-10T12:30:00Z",
        "request_id": None,
        "execution_id": None,
        "review_id": None,
        "submitted_at": None,
        "decision": None,
        "decision_at": None,
    }
    if state != "prepared":
        payload.update(request_id="request-1", execution_id="execution-1")
    if state in {"pending_review", "decision_recorded"}:
        payload.update(review_id="review-1", submitted_at="2026-10-10T12:10:00Z")
    if state == "decision_recorded":
        payload.update(decision="approved", decision_at="2026-10-10T12:20:00Z")
    return payload


@pytest.mark.parametrize("state", ["prepared", "submitted", "pending_review", "decision_recorded"])
def test_accepts_correlated_persisted_observations(binding, state) -> None:
    payload = _receipt(binding, state)
    receipt = validate_portal_receipt(payload, binding=binding)
    assert receipt.model_dump(mode="json") == payload
    # A later malformed response must not be able to mutate the prior observation.
    payload["decision"] = "rejected"
    assert receipt.decision == ("approved" if state == "decision_recorded" else None)


@pytest.mark.parametrize("decision", ["approved", "rejected", "changes_requested"])
def test_preserves_actual_manager_decision(binding, decision) -> None:
    payload = _receipt(binding, "decision_recorded")
    payload["decision"] = decision
    assert validate_portal_receipt(payload, binding=binding).decision == decision


@pytest.mark.parametrize(
    ("key", "different"),
    [
        ("handoff_id", "another-trip"),
        ("snapshot_version", "sha256:" + "c" * 64),
        ("snapshot_sha256", "c" * 64),
        ("draft_id", "another-draft"),
    ],
)
def test_rejects_approval_for_another_snapshot(binding, key, different) -> None:
    payload = _receipt(binding, "decision_recorded")
    payload[key] = different
    with pytest.raises(TPPContractError, match="does not match the prepared snapshot"):
        validate_portal_receipt(payload, binding=binding)


@pytest.mark.parametrize(
    ("state", "updates"),
    [
        ("prepared", {"request_id": "request-1"}),
        ("prepared", {"execution_id": "execution-1"}),
        ("prepared", {"review_id": "review-1"}),
        ("prepared", {"submitted_at": "2026-10-10T12:10:00Z"}),
        ("prepared", {"decision": "approved"}),
        ("prepared", {"decision_at": "2026-10-10T12:20:00Z"}),
        ("submitted", {"request_id": None}),
        ("submitted", {"execution_id": None}),
        ("submitted", {"review_id": "review-1"}),
        ("submitted", {"decision": "approved"}),
        ("pending_review", {"review_id": None}),
        ("pending_review", {"submitted_at": None}),
        ("pending_review", {"decision": "approved"}),
        ("pending_review", {"decision_at": "2026-10-10T12:20:00Z"}),
        ("decision_recorded", {"decision": None}),
        ("decision_recorded", {"decision_at": None}),
        ("decision_recorded", {"decision": "sent"}),
    ],
)
def test_rejects_states_without_their_required_evidence(binding, state, updates) -> None:
    payload = {**_receipt(binding, state), **updates}
    with pytest.raises(TPPContractError, match="Malformed TPP portal receipt"):
        validate_portal_receipt(payload, binding=binding)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("prepared_at", "2026-10-10T12:31:00Z"),
        ("submitted_at", "2026-10-10T11:59:00Z"),
        ("submitted_at", "2026-10-10T12:31:00Z"),
        ("decision_at", "2026-10-10T12:09:00Z"),
        ("decision_at", "2026-10-10T12:31:00Z"),
        ("observed_at", "2026-10-10T12:30:00"),
        ("observed_at", "invalid-time"),
    ],
)
def test_rejects_ambiguous_or_impossible_evidence_times(binding, key, value) -> None:
    payload = {**_receipt(binding, "decision_recorded"), key: value}
    with pytest.raises(TPPContractError, match="Malformed TPP portal receipt"):
        validate_portal_receipt(payload, binding=binding)


@pytest.mark.parametrize("payload", [None, [], {"detail": "unavailable"}, {"state": "approved"}])
def test_failed_or_absent_lookup_is_never_a_successful_receipt(binding, payload) -> None:
    with pytest.raises(TPPContractError, match="Malformed TPP portal receipt"):
        validate_portal_receipt(payload, binding=binding)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("contract_version", "portal-receipt/v2"),
        ("snapshot_sha256", "sha256:" + "a" * 64),
        ("snapshot_sha256", "A" * 64),
        ("request_id", 42),
        ("draft_id", " "),
        ("state", "approved"),
        ("answers", {"traveler_name": "PRIVATE-RESPONSE-MARKER"}),
    ],
)
def test_rejects_unknown_or_malformed_metadata_without_exposing_input(binding, key, value) -> None:
    payload = {**_receipt(binding, "decision_recorded"), key: value}
    with pytest.raises(TPPContractError) as caught:
        validate_portal_receipt(payload, binding=binding)
    assert str(caught.value) == "Malformed TPP portal receipt contract."
    assert "PRIVATE-RESPONSE-MARKER" not in str(caught.value)
    assert caught.value.__suppress_context__ is True


@pytest.mark.parametrize("key", ["contract_version", "decision", "decision_at", "observed_at"])
def test_omitted_contract_fields_do_not_default_to_a_successful_observation(binding, key) -> None:
    payload = _receipt(binding)
    payload.pop(key)
    with pytest.raises(TPPContractError, match="Malformed TPP portal receipt"):
        validate_portal_receipt(payload, binding=binding)
