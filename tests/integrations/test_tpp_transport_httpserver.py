import time

import pytest

pytest.importorskip("pytest_httpserver")
from pytest_httpserver import HTTPServer

from trip_planner.integrations.tpp import (
    HTTPTPPIntegrationClient,
    TPPRuntimeSettings,
    TPPTransportError,
    TPPTransportPolicy,
)


def _client(base_url: str, *, policy: TPPTransportPolicy | None = None) -> HTTPTPPIntegrationClient:
    return HTTPTPPIntegrationClient(
        TPPRuntimeSettings(
            base_url=base_url.rstrip("/"),
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


def test_httpserver_surfaces_server_error_after_retry_budget(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/server", method="POST").respond_with_json(
        {"detail": "temporarily unavailable"}, status=503
    )
    client = _client(
        httpserver.url_for(""),
        policy=TPPTransportPolicy(
            max_attempts=3,
            backoff_initial_seconds=0.0,
            backoff_max_seconds=0.0,
            breaker_failure_threshold=5,
        ),
    )

    with pytest.raises(TPPTransportError) as exc_info:
        client._request_json(method="POST", path="/server", json_payload={})

    assert exc_info.value.error_code == "server_error"
    assert len(httpserver.log) == 3


def test_httpserver_surfaces_unauthorized(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/unauthorized", method="POST").respond_with_json(
        {"detail": "bad token"}, status=401
    )
    client = _client(httpserver.url_for(""))

    with pytest.raises(TPPTransportError) as exc_info:
        client._request_json(method="POST", path="/unauthorized", json_payload={})

    assert exc_info.value.error_code == "unauthorized"


def test_httpserver_surfaces_invalid_response(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/invalid", method="POST").respond_with_data(
        "not-json", status=200, content_type="text/plain"
    )
    client = _client(httpserver.url_for(""))

    with pytest.raises(TPPTransportError) as exc_info:
        client._request_json(method="POST", path="/invalid", json_payload={})

    assert exc_info.value.error_code == "invalid_response"


def test_httpserver_surfaces_timeout(httpserver: HTTPServer) -> None:
    def _slow_response(_request):
        time.sleep(0.15)
        return "slow"

    httpserver.expect_request("/timeout", method="POST").respond_with_handler(_slow_response)
    client = _client(
        httpserver.url_for(""),
        policy=TPPTransportPolicy(
            connect_timeout_seconds=1.0,
            read_timeout_seconds=0.05,
            max_attempts=1,
            backoff_initial_seconds=0.0,
            backoff_max_seconds=0.0,
            breaker_failure_threshold=5,
        ),
    )

    with pytest.raises(TPPTransportError) as exc_info:
        client._request_json(method="POST", path="/timeout", json_payload={})

    assert exc_info.value.error_code == "timeout"


def test_httpserver_breaker_opens_after_consecutive_failures(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/down", method="POST").respond_with_json(
        {"detail": "service down"}, status=503
    )
    client = _client(
        httpserver.url_for(""),
        policy=TPPTransportPolicy(
            max_attempts=1,
            backoff_initial_seconds=0.0,
            backoff_max_seconds=0.0,
            breaker_failure_threshold=2,
            breaker_reset_seconds=60.0,
        ),
    )

    with pytest.raises(TPPTransportError) as first:
        client._request_json(method="POST", path="/down", json_payload={})
    assert first.value.error_code == "server_error"

    with pytest.raises(TPPTransportError) as second:
        client._request_json(method="POST", path="/down", json_payload={})
    assert second.value.error_code == "server_error"

    with pytest.raises(TPPTransportError) as third:
        client._request_json(method="POST", path="/down", json_payload={})
    assert third.value.error_code == "breaker_open"
