"""Receipt observations must not turn stale or contradictory data into approval."""

from __future__ import annotations

from typing import Any

import pytest

from trip_planner.integrations.tpp.client import TPPContractError
from trip_planner.integrations.tpp.portal_receipt import (
    PortalReceiptBinding,
    TPPPortalReceipt,
    validate_portal_preparation,
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
def test_preparation_establishes_producer_binding_and_preserves_retry_evidence(binding, state):
    payload = _receipt(binding, state)
    prepared = validate_portal_preparation(
        payload, handoff_id=binding.handoff_id, snapshot_version=binding.snapshot_version
    )
    assert prepared.model_dump(mode="json") == payload
    retained_binding = PortalReceiptBinding.model_validate(
        {key: getattr(prepared, key) for key in PortalReceiptBinding.model_fields}
    )

    # The producer owns the draft and normalized digest; later reads must agree
    # with the metadata learned from this authenticated preparation response.
    assert validate_portal_receipt(payload, binding=retained_binding, previous=prepared) == prepared
    changed = {**payload, "draft_id": "another-draft"}
    with pytest.raises(TPPContractError, match="does not match the prepared snapshot"):
        validate_portal_receipt(changed, binding=retained_binding, previous=prepared)


@pytest.mark.parametrize("key", ["handoff_id", "snapshot_version"])
def test_preparation_rejects_correlation_not_selected_by_the_server(binding, key):
    payload = _receipt(binding)
    payload[key] = "unrequested-snapshot"
    with pytest.raises(TPPContractError, match="does not match the requested snapshot") as rejected:
        validate_portal_preparation(
            payload, handoff_id=binding.handoff_id, snapshot_version=binding.snapshot_version
        )
    assert "unrequested-snapshot" not in str(rejected.value)


@pytest.mark.parametrize(
    "change",
    [
        {"snapshot_sha256": "invalid"},
        {"draft_id": ""},
        {"state": "approved"},
        {"request_id": "invented-request"},
        {"decision": "approved"},
        {"observed_at": "2026-10-10T11:00:00Z"},
        {"answers": {"traveler_name": "Private traveler fact"}},
    ],
)
def test_preparation_rejects_malformed_or_invented_evidence_without_exposing_payload(
    binding, change
):
    payload = {**_receipt(binding), **change}
    with pytest.raises(TPPContractError, match="Malformed TPP portal receipt contract") as rejected:
        validate_portal_preparation(
            payload, handoff_id=binding.handoff_id, snapshot_version=binding.snapshot_version
        )
    assert str(rejected.value) == "Malformed TPP portal receipt contract."
    assert rejected.value.__suppress_context__


@pytest.mark.parametrize("operation", ["preparation", "receipt"])
@pytest.mark.parametrize(
    ("state", "updates"),
    [
        ("prepared", {"observed_at": "invalid-time"}),
        ("prepared", {"snapshot_sha256": "invalid-digest"}),
        ("submitted", {"request_id": 42}),
        ("decision_recorded", {"decision": "sent"}),
        ("decision_recorded", {"state": "approved"}),
    ],
)
def test_model_instance_cannot_bypass_receipt_evidence_validation(
    binding, operation, state, updates
):
    original = _receipt(binding, state)
    parsed = TPPPortalReceipt.model_validate(original)
    # model_copy deliberately bypasses field and model validation. The trusted
    # transport may return a parsed model, so the boundary must recheck it just
    # as strictly as a decoded JSON response before establishing evidence.
    unvalidated = parsed.model_copy(update=updates)

    with pytest.raises(TPPContractError, match="Malformed TPP portal receipt contract") as rejected:
        if operation == "preparation":
            validate_portal_preparation(
                unvalidated,
                handoff_id=binding.handoff_id,
                snapshot_version=binding.snapshot_version,
            )
        else:
            validate_portal_receipt(unvalidated, binding=binding)

    assert str(rejected.value) == "Malformed TPP portal receipt contract."
    assert rejected.value.__suppress_context__
    assert parsed.model_dump(mode="json") == original


@pytest.mark.parametrize("state", ["prepared", "submitted", "pending_review", "decision_recorded"])
def test_valid_model_instance_retains_evidence_after_revalidation(binding, state):
    payload = _receipt(binding, state)
    parsed = TPPPortalReceipt.model_validate(payload)
    preparation = validate_portal_preparation(
        parsed, handoff_id=binding.handoff_id, snapshot_version=binding.snapshot_version
    )
    receipt = validate_portal_receipt(parsed, binding=binding, previous=preparation)
    assert receipt.model_dump(mode="json") == payload
    assert parsed.model_dump(mode="json") == payload


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


@pytest.mark.parametrize("state", ["prepared", "submitted", "pending_review", "decision_recorded"])
def test_newer_observation_preserves_preparation_and_persisted_evidence(binding, state) -> None:
    previous = validate_portal_receipt(_receipt(binding), binding=binding)
    payload = _receipt(binding, state)
    payload["observed_at"] = "2026-10-10T12:31:00Z"

    current = validate_portal_receipt(payload, binding=binding, previous=previous)

    assert current.model_dump(mode="json") == payload
    assert previous.state == "prepared"
    assert previous.request_id is None


def test_successive_observations_follow_actual_submission_and_review_evidence(binding) -> None:
    previous = None
    for minute, state in enumerate(
        ("prepared", "submitted", "pending_review", "decision_recorded"), start=30
    ):
        payload = _receipt(binding, state)
        payload["observed_at"] = f"2026-10-10T12:{minute}:00Z"
        current = validate_portal_receipt(payload, binding=binding, previous=previous)
        assert current.model_dump(mode="json") == payload
        previous = current


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("observed_at", "2026-10-10T12:29:00Z"),
        ("prepared_at", "2026-10-10T12:01:00Z"),
        ("request_id", "replacement-request"),
        ("execution_id", "replacement-execution"),
        ("review_id", "replacement-review"),
        ("submitted_at", "2026-10-10T12:11:00Z"),
        ("decision_at", "2026-10-10T12:19:00Z"),
        ("decision", "rejected"),
    ],
)
def test_observation_cannot_rewrite_or_predate_recorded_evidence(binding, key, value) -> None:
    original = _receipt(binding, "decision_recorded")
    previous = validate_portal_receipt(original, binding=binding)
    payload = {**original, "observed_at": "2026-10-10T12:31:00Z", key: value}

    with pytest.raises(TPPContractError, match="conflicts with the previous observation"):
        validate_portal_receipt(payload, binding=binding, previous=previous)

    assert previous.model_dump(mode="json") == original


@pytest.mark.parametrize("state", ["prepared", "submitted", "pending_review"])
def test_observation_cannot_discard_recorded_submission_or_decision(binding, state) -> None:
    previous = validate_portal_receipt(_receipt(binding, "decision_recorded"), binding=binding)
    payload = _receipt(binding, state)
    payload["observed_at"] = "2026-10-10T12:31:00Z"

    with pytest.raises(TPPContractError, match="conflicts with the previous observation"):
        validate_portal_receipt(payload, binding=binding, previous=previous)


def test_actual_later_manager_decision_is_not_frozen_by_an_earlier_observation(binding) -> None:
    payload = _receipt(binding, "decision_recorded")
    payload["decision"] = "changes_requested"
    previous = validate_portal_receipt(payload, binding=binding)
    payload.update(
        decision="approved",
        decision_at="2026-10-10T12:25:00Z",
        observed_at="2026-10-10T12:31:00Z",
    )

    current = validate_portal_receipt(payload, binding=binding, previous=previous)

    assert current.decision == "approved"
    assert previous.decision == "changes_requested"


def test_previous_observation_must_belong_to_the_current_binding(binding) -> None:
    other = binding.model_copy(update={"handoff_id": "another-handoff"})
    previous = validate_portal_receipt(_receipt(other), binding=other)

    with pytest.raises(TPPContractError, match="does not match the prepared snapshot"):
        validate_portal_receipt(_receipt(binding), binding=binding, previous=previous)


def test_invalid_previous_evidence_cannot_bypass_validation_via_model_copy(binding) -> None:
    previous = validate_portal_receipt(_receipt(binding), binding=binding)
    previous = previous.model_copy(update={"decision": "approved"})

    with pytest.raises(TPPContractError, match="Malformed TPP portal receipt"):
        validate_portal_receipt(_receipt(binding), binding=binding, previous=previous)


def test_identical_observation_can_be_replayed_without_mutating_the_previous_receipt(
    binding,
) -> None:
    payload = _receipt(binding, "decision_recorded")
    previous = validate_portal_receipt(payload, binding=binding)

    current = validate_portal_receipt(payload, binding=binding, previous=previous)

    assert current == previous
    assert current is not previous
