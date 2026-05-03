from __future__ import annotations

import io
import socket
from email.message import Message
from urllib import error as urllib_error

import pytest

from trip_planner.integrations.tpp import (
    HTTPTPPIntegrationClient,
    TPPRuntimeSettings,
    TPPTransportError,
    TPPTransportPolicy,
)
from trip_planner.integrations.tpp import client as tpp_client_module


class _FakeHTTPResponse:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb

    def read(self) -> bytes:
        return self._body


def _client(*, policy: TPPTransportPolicy | None = None) -> HTTPTPPIntegrationClient:
    return HTTPTPPIntegrationClient(
        TPPRuntimeSettings(
            base_url="http://tpp.example.test",
            access_token="token-123",
            oidc_provider="okta",
        ),
        policy=policy
        or TPPTransportPolicy(
            max_attempts=1,
            backoff_initial_seconds=0.0,
            backoff_max_seconds=0.0,
            breaker_failure_threshold=5,
        ),
        breaker_registry={},
    )


@pytest.mark.parametrize(
    ("raised", "expected_code"),
    [
        (
            urllib_error.HTTPError(
                url="http://tpp.example.test/transport",
                code=401,
                msg="Unauthorized",
                hdrs=Message(),
                fp=io.BytesIO(b'{"detail": "bad token"}'),
            ),
            "unauthorized",
        ),
        (
            urllib_error.HTTPError(
                url="http://tpp.example.test/transport",
                code=503,
                msg="Service Unavailable",
                hdrs=Message(),
                fp=io.BytesIO(b'{"detail": "down"}'),
            ),
            "server_error",
        ),
        (
            urllib_error.HTTPError(
                url="http://tpp.example.test/transport",
                code=418,
                msg="Teapot",
                hdrs=Message(),
                fp=io.BytesIO(b'{"detail": "teapot"}'),
            ),
            "unknown",
        ),
        (urllib_error.URLError(ConnectionRefusedError("connection refused")), "connection_error"),
        (urllib_error.URLError(socket.timeout("timed out")), "timeout"),
    ],
)
def test_transport_error_code_mapping_without_socket_bind(
    monkeypatch: pytest.MonkeyPatch,
    raised: Exception,
    expected_code: str,
) -> None:
    client = _client()

    def _raise(*args, **kwargs):
        del args, kwargs
        raise raised

    monkeypatch.setattr(tpp_client_module.urllib_request, "urlopen", _raise)

    with pytest.raises(TPPTransportError) as exc_info:
        client._request_json(method="POST", path="/transport", json_payload={})

    assert exc_info.value.error_code == expected_code


def test_transport_invalid_response_mapping_without_socket_bind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client()

    def _respond(*args, **kwargs):
        del args, kwargs
        return _FakeHTTPResponse(status=200, body=b"not-json")

    monkeypatch.setattr(tpp_client_module.urllib_request, "urlopen", _respond)

    with pytest.raises(TPPTransportError) as exc_info:
        client._request_json(method="POST", path="/invalid", json_payload={})

    assert exc_info.value.error_code == "invalid_response"


def test_transport_breaker_open_mapping_without_socket_bind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"count": 0}
    client = _client(
        policy=TPPTransportPolicy(
            max_attempts=1,
            backoff_initial_seconds=0.0,
            backoff_max_seconds=0.0,
            breaker_failure_threshold=1,
            breaker_reset_seconds=60.0,
        )
    )

    def _raise(*args, **kwargs):
        del args, kwargs
        calls["count"] += 1
        raise urllib_error.URLError(ConnectionRefusedError("connection refused"))

    monkeypatch.setattr(tpp_client_module.urllib_request, "urlopen", _raise)

    with pytest.raises(TPPTransportError) as first:
        client._request_json(method="POST", path="/down", json_payload={})
    assert first.value.error_code == "connection_error"

    with pytest.raises(TPPTransportError) as second:
        client._request_json(method="POST", path="/down", json_payload={})
    assert second.value.error_code == "breaker_open"
    assert calls["count"] == 1


def test_transport_503_retries_to_max_attempts_without_socket_bind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"count": 0}
    client = _client(
        policy=TPPTransportPolicy(
            max_attempts=3,
            backoff_initial_seconds=0.0,
            backoff_max_seconds=0.0,
            breaker_failure_threshold=5,
        )
    )

    def _raise(*args, **kwargs):
        del args, kwargs
        calls["count"] += 1
        raise urllib_error.HTTPError(
            url="http://tpp.example.test/retry",
            code=503,
            msg="Service Unavailable",
            hdrs=None,
            fp=io.BytesIO(b'{"detail": "temporarily unavailable"}'),
        )

    monkeypatch.setattr(tpp_client_module.urllib_request, "urlopen", _raise)

    with pytest.raises(TPPTransportError) as exc_info:
        client._request_json(method="POST", path="/retry", json_payload={})

    assert exc_info.value.error_code == "server_error"
    assert calls["count"] == 3
