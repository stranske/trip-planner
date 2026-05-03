import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from pytest_httpserver import HTTPServer

from trip_planner.integrations.tpp import (
    HTTPTPPIntegrationClient,
    TPPRuntimeSettings,
    TPPTransportError,
    TPPTransportPolicy,
)

_SOCKET_BIND_AVAILABLE = True
_socket_probe: socket.socket | None = None
try:
    _socket_probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _socket_probe.bind(("127.0.0.1", 0))
except OSError:
    # Some CI runners disallow loopback binds entirely; skip these tests there.
    _SOCKET_BIND_AVAILABLE = False
finally:
    if _socket_probe is not None:
        _socket_probe.close()

pytestmark = pytest.mark.skipif(
    not _SOCKET_BIND_AVAILABLE,
    reason="socket bind is not permitted in this environment",
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


def test_httpserver_surfaces_forbidden_as_unauthorized(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/forbidden", method="POST").respond_with_json(
        {"detail": "forbidden"}, status=403
    )
    client = _client(httpserver.url_for(""))

    with pytest.raises(TPPTransportError) as exc_info:
        client._request_json(method="POST", path="/forbidden", json_payload={})

    assert exc_info.value.error_code == "unauthorized"
    assert exc_info.value.status_code == 403


def test_httpserver_surfaces_invalid_response(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/invalid", method="POST").respond_with_data(
        "not-json", status=200, content_type="text/plain"
    )
    client = _client(httpserver.url_for(""))

    with pytest.raises(TPPTransportError) as exc_info:
        client._request_json(method="POST", path="/invalid", json_payload={})

    assert exc_info.value.error_code == "invalid_response"


def test_httpserver_surfaces_invalid_utf8_as_invalid_response(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/invalid-utf8", method="POST").respond_with_data(
        b"\xff\xfe\xfa", status=200, content_type="application/json"
    )
    client = _client(httpserver.url_for(""))

    with pytest.raises(TPPTransportError) as exc_info:
        client._request_json(method="POST", path="/invalid-utf8", json_payload={})

    assert exc_info.value.error_code == "invalid_response"


def test_httpserver_surfaces_unknown_for_non_retryable_http_status(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/unknown", method="POST").respond_with_json(
        {"detail": "teapot"}, status=418
    )
    client = _client(httpserver.url_for(""))

    with pytest.raises(TPPTransportError) as exc_info:
        client._request_json(method="POST", path="/unknown", json_payload={})

    assert exc_info.value.error_code == "unknown"


def test_httpserver_surfaces_timeout() -> None:
    class SlowBodyHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", "12")
            self.end_headers()
            time.sleep(0.25)
            try:
                self.wfile.write(b'{"ok": true}')
            except BrokenPipeError:
                pass

        def log_message(self, _format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), SlowBodyHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = _client(
        f"http://127.0.0.1:{server.server_port}",
        policy=TPPTransportPolicy(
            connect_timeout_seconds=1.0,
            read_timeout_seconds=0.05,
            max_attempts=1,
            backoff_initial_seconds=0.0,
            backoff_max_seconds=0.0,
            breaker_failure_threshold=5,
        ),
    )

    try:
        with pytest.raises(TPPTransportError) as exc_info:
            client._request_json(method="POST", path="/timeout", json_payload={})
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1.0)

    assert exc_info.value.error_code == "timeout"


def test_httpserver_surfaces_connection_error() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        unreachable_port = probe.getsockname()[1]
    client = _client(
        f"http://127.0.0.1:{unreachable_port}",
        policy=TPPTransportPolicy(
            connect_timeout_seconds=0.2,
            read_timeout_seconds=0.2,
            max_attempts=1,
            backoff_initial_seconds=0.0,
            backoff_max_seconds=0.0,
            breaker_failure_threshold=5,
        ),
    )

    with pytest.raises(TPPTransportError) as exc_info:
        client._request_json(method="POST", path="/connection", json_payload={})

    assert exc_info.value.error_code == "connection_error"


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


def test_httpserver_breaker_half_open_trial_success_closes_breaker(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/down", method="POST").respond_with_json(
        {"detail": "service down"}, status=503
    )
    httpserver.expect_request("/recovered", method="POST").respond_with_json(
        {"ok": True}, status=200
    )
    httpserver.expect_request("/recovered", method="POST").respond_with_json(
        {"ok": True}, status=200
    )
    now = [0.0]
    client = _client(
        httpserver.url_for(""),
        policy=TPPTransportPolicy(
            max_attempts=1,
            backoff_initial_seconds=0.0,
            backoff_max_seconds=0.0,
            breaker_failure_threshold=1,
            breaker_reset_seconds=10.0,
        ),
    )
    client._clock = lambda: now[0]

    with pytest.raises(TPPTransportError) as first:
        client._request_json(method="POST", path="/down", json_payload={})
    assert first.value.error_code == "server_error"
    assert len(httpserver.log) == 1

    with pytest.raises(TPPTransportError) as second:
        client._request_json(method="POST", path="/recovered", json_payload={})
    assert second.value.error_code == "breaker_open"
    assert len(httpserver.log) == 1

    now[0] = 11.0
    payload = client._request_json(method="POST", path="/recovered", json_payload={})
    assert payload == {"ok": True}
    assert len(httpserver.log) == 2

    payload = client._request_json(method="POST", path="/recovered", json_payload={})
    assert payload == {"ok": True}
    assert len(httpserver.log) == 3


def test_httpserver_breaker_half_open_trial_failure_reopens_breaker(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/down", method="POST").respond_with_json(
        {"detail": "service down"}, status=503
    )
    httpserver.expect_request("/recovered", method="POST").respond_with_json(
        {"detail": "still down"}, status=503
    )
    httpserver.expect_request("/recovered-again", method="POST").respond_with_json(
        {"ok": True}, status=200
    )
    now = [0.0]
    client = _client(
        httpserver.url_for(""),
        policy=TPPTransportPolicy(
            max_attempts=1,
            backoff_initial_seconds=0.0,
            backoff_max_seconds=0.0,
            breaker_failure_threshold=1,
            breaker_reset_seconds=10.0,
        ),
    )
    client._clock = lambda: now[0]

    with pytest.raises(TPPTransportError) as first:
        client._request_json(method="POST", path="/down", json_payload={})
    assert first.value.error_code == "server_error"
    assert len(httpserver.log) == 1

    now[0] = 11.0
    with pytest.raises(TPPTransportError) as half_open_trial:
        client._request_json(method="POST", path="/recovered", json_payload={})
    assert half_open_trial.value.error_code == "server_error"
    assert len(httpserver.log) == 2

    now[0] = 12.0
    with pytest.raises(TPPTransportError) as reopened:
        client._request_json(method="POST", path="/recovered", json_payload={})
    assert reopened.value.error_code == "breaker_open"
    assert len(httpserver.log) == 2

    now[0] = 23.0
    payload = client._request_json(method="POST", path="/recovered-again", json_payload={})
    assert payload == {"ok": True}
    assert len(httpserver.log) == 3
