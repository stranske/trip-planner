"""Verify fixed receipt routing, owner authorization and failed-read semantics."""

import io
import json
from contextlib import contextmanager
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest

from trip_planner.integrations.tpp.client import TPPContractError
from trip_planner.integrations.tpp.portal_receipt import PortalReceiptBinding
from trip_planner.integrations.tpp.portal_receipt_client import (
    OwnerPortalReceiptClient,
    PortalOwnerIdentity,
    PortalPreparationError,
    PortalReceiptReadError,
)


@pytest.fixture
def client_setup(monkeypatch):
    monkeypatch.setenv("TPP_PORTAL_BASE_URL", "https://portal.example:8443")
    identity = PortalOwnerIdentity("tenant-a", "subject-a", "Bearer " + uuid4().hex)
    client = OwnerPortalReceiptClient(lambda account_id: identity)
    binding = PortalReceiptBinding(
        handoff_id="trip:handoff-1",
        snapshot_version="sha256:" + "b" * 64,
        snapshot_sha256="a" * 64,
        draft_id="draft-1",
    )
    return client, identity, binding


def test_receipt_uses_owner_authorization_and_fixed_route(client_setup, monkeypatch):
    client, identity, binding = client_setup

    @contextmanager
    def open_request(outgoing, *, timeout):
        parsed = urlsplit(outgoing.full_url)
        assert parsed.netloc == "portal.example:8443"
        assert parsed.path == "/api/planner/portal-handoffs/trip%3Ahandoff-1"
        assert parse_qs(parsed.query) == {"snapshot_version": [binding.snapshot_version]}
        assert identity.authorization not in outgoing.full_url
        assert outgoing.get_method() == "GET"
        assert outgoing.get_header("Authorization") == identity.authorization
        assert outgoing.data is None and timeout == 15
        response = io.BytesIO(json.dumps({"state": "prepared"}).encode())
        response.status = 200
        yield response

    monkeypatch.setattr(client._opener, "open", open_request)
    assert client.read_receipt(identity=identity, binding=binding) == {"state": "prepared"}
    assert identity.authorization not in repr(identity)
    assert "authorization" not in identity.owner_binding()


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (301, "unavailable"),
        (302, "unavailable"),
        (401, "unauthorized"),
        (403, "unauthorized"),
        (404, "not_found"),
        (409, "stale"),
        (422, "unavailable"),
        (503, "unavailable"),
    ],
)
def test_http_failure_never_becomes_prepared_or_approved(client_setup, monkeypatch, code, expected):
    client, identity, binding = client_setup
    private_body = io.BytesIO(b"private upstream error data")

    def fail(*args, **kwargs):
        raise HTTPError("https://portal.example", code, "private error", {}, private_body)

    monkeypatch.setattr(client._opener, "open", fail)
    with pytest.raises(PortalReceiptReadError) as rejected:
        client.read_receipt(identity=identity, binding=binding)
    assert rejected.value.observation_status == expected
    assert "private" not in str(rejected.value)
    assert private_body.closed
    assert rejected.value.__suppress_context__


def test_redirect_handler_never_forwards_owner_authorization(client_setup):
    client, _, _ = client_setup
    redirect_handler = next(
        handler for handler in client._opener.handlers if hasattr(handler, "redirect_request")
    )
    assert (
        redirect_handler.redirect_request(
            None, None, 302, "Found", {}, "https://another-origin.example/receipt"
        )
        is None
    )


@pytest.mark.parametrize("failure", [TimeoutError(), URLError("private upstream address")])
def test_network_failure_is_unavailable(client_setup, monkeypatch, failure):
    client, identity, binding = client_setup

    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(client._opener, "open", fail)
    with pytest.raises(PortalReceiptReadError, match="could not be observed") as rejected:
        client.read_receipt(identity=identity, binding=binding)
    assert rejected.value.observation_status == "unavailable"


@pytest.mark.parametrize("body", [b"not JSON", b"\xff", b"x" * 65_537])
def test_malformed_or_oversized_response_is_not_evidence(client_setup, monkeypatch, body):
    client, identity, binding = client_setup

    @contextmanager
    def open_request(*args, **kwargs):
        response = io.BytesIO(body)
        response.status = 200
        yield response

    monkeypatch.setattr(client._opener, "open", open_request)
    with pytest.raises(TPPContractError, match="Malformed TPP portal receipt"):
        client.read_receipt(identity=identity, binding=binding)


def _preparation_receipt(binding, *, decision_recorded=False):
    return {
        **binding.model_dump(),
        "contract_version": "portal-receipt/v1",
        "state": "decision_recorded" if decision_recorded else "prepared",
        "prepared_at": "2026-10-10T12:00:00Z",
        "observed_at": "2026-10-10T12:30:00Z",
        "request_id": "request-1" if decision_recorded else None,
        "execution_id": "execution-1" if decision_recorded else None,
        "review_id": "review-1" if decision_recorded else None,
        "submitted_at": "2026-10-10T12:10:00Z" if decision_recorded else None,
        "decision": "changes_requested" if decision_recorded else None,
        "decision_at": "2026-10-10T12:20:00Z" if decision_recorded else None,
    }


@pytest.mark.parametrize("decision_recorded", [False, True])
def test_owner_preparation_posts_private_answers_and_preserves_retry_evidence(
    client_setup, monkeypatch, decision_recorded
):
    client, identity, binding = client_setup
    answers = {"traveler_name": "Morgan José", "notes": "Quote + tax & fees = $430.00"}
    payload = _preparation_receipt(binding, decision_recorded=decision_recorded)
    requests = []

    @contextmanager
    def open_request(outgoing, *, timeout):
        assert outgoing.full_url == "https://portal.example:8443/api/planner/portal-handoffs"
        assert outgoing.get_method() == "POST"
        assert outgoing.get_header("Authorization") == identity.authorization
        assert outgoing.get_header("Content-type") == "application/json; charset=utf-8"
        assert timeout == 15
        requests.append(json.loads(outgoing.data))
        response = io.BytesIO(json.dumps(payload).encode())
        response.status = 200
        yield response

    monkeypatch.setattr(client._opener, "open", open_request)
    for _ in range(2):
        receipt = client.prepare_handoff(
            identity=identity,
            handoff_id=binding.handoff_id,
            snapshot_version=binding.snapshot_version,
            answers=answers,
        )
        assert receipt.model_dump(mode="json") == payload
        assert "answers" not in receipt.model_dump()
    assert (
        requests
        == [
            {
                "handoff_id": binding.handoff_id,
                "snapshot_version": binding.snapshot_version,
                "answers": answers,
            }
        ]
        * 2
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"handoff_id": "another-handoff"},
        {"snapshot_version": "another-snapshot"},
        {"snapshot_sha256": "invalid"},
        {"decision": "approved"},
        {"answers": {"traveler_name": "Private traveler"}},
    ],
)
def test_preparation_rejects_uncorrelated_or_malformed_success(client_setup, monkeypatch, changes):
    client, identity, binding = client_setup

    @contextmanager
    def open_request(*args, **kwargs):
        response = io.BytesIO(json.dumps({**_preparation_receipt(binding), **changes}).encode())
        response.status = 200
        yield response

    monkeypatch.setattr(client._opener, "open", open_request)
    with pytest.raises(TPPContractError) as rejected:
        client.prepare_handoff(
            identity=identity,
            handoff_id=binding.handoff_id,
            snapshot_version=binding.snapshot_version,
            answers={},
        )
    assert "Private traveler" not in str(rejected.value)


@pytest.mark.parametrize("code", [302, 401, 403, 409, 422, 500, 503])
def test_preparation_failure_is_sanitized_without_retrying(client_setup, monkeypatch, code):
    client, identity, binding = client_setup
    calls = []
    private_body = io.BytesIO(b"private upstream answers")

    def fail(outgoing, **kwargs):
        calls.append(outgoing)
        raise HTTPError(outgoing.full_url, code, "private error", {}, private_body)

    monkeypatch.setattr(client._opener, "open", fail)
    with pytest.raises(PortalPreparationError) as rejected:
        client.prepare_handoff(
            identity=identity,
            handoff_id=binding.handoff_id,
            snapshot_version=binding.snapshot_version,
            answers={"traveler_name": "Private traveler"},
        )
    assert rejected.value.status_code == (code if code in {401, 403, 409, 422, 503} else 502)
    assert str(rejected.value) == "The portal handoff could not be prepared."
    assert rejected.value.__suppress_context__
    assert private_body.closed
    assert len(calls) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"handoff_id": "caller/path"},
        {"snapshot_version": "x" * 81},
        {"answers": {"traveler_name": 42}},
        {"answers": {"x" * 101: "value"}},
        {"answers": {"notes": "x" * 4097}},
        {"answers": {str(i): "value" for i in range(81)}},
        # Each field is within its own limit; the encoded JSON body is too large.
        {"answers": {str(i): "é" * 4096 for i in range(9)}},
    ],
)
def test_preparation_rejects_invalid_or_oversized_requests_before_transport(
    client_setup, monkeypatch, changes
):
    client, identity, binding = client_setup

    def unexpected_request(*args, **kwargs):
        pytest.fail("Invalid preparation reached the producer")

    monkeypatch.setattr(client._opener, "open", unexpected_request)
    with pytest.raises(
        TPPContractError, match="Invalid TPP portal preparation request"
    ) as rejected:
        client.prepare_handoff(
            identity=identity,
            **{
                "handoff_id": binding.handoff_id,
                "snapshot_version": binding.snapshot_version,
                "answers": {},
                **changes,
            },
        )
    assert str(rejected.value) == "Invalid TPP portal preparation request."


@pytest.mark.parametrize("failure", [TimeoutError(), URLError("private upstream address")])
def test_preparation_network_failure_never_establishes_a_binding(
    client_setup, monkeypatch, failure
):
    client, identity, binding = client_setup

    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(client._opener, "open", fail)
    with pytest.raises(PortalPreparationError) as rejected:
        client.prepare_handoff(
            identity=identity,
            handoff_id=binding.handoff_id,
            snapshot_version=binding.snapshot_version,
            answers={},
        )
    assert rejected.value.status_code == 502
    assert str(rejected.value) == "The portal handoff could not be prepared."


@pytest.mark.parametrize("body", [b"not JSON", b"\xff", b"x" * 65_537])
def test_preparation_rejects_invalid_or_oversized_response(client_setup, monkeypatch, body):
    client, identity, binding = client_setup

    @contextmanager
    def open_request(*args, **kwargs):
        response = io.BytesIO(body)
        response.status = 200
        yield response

    monkeypatch.setattr(client._opener, "open", open_request)
    with pytest.raises(TPPContractError, match="Malformed TPP portal receipt"):
        client.prepare_handoff(
            identity=identity,
            handoff_id=binding.handoff_id,
            snapshot_version=binding.snapshot_version,
            answers={},
        )
