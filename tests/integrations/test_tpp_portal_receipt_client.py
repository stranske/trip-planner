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
