import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

pytest.importorskip("pytest_httpserver")

_SOCKET_BIND_AVAILABLE = True
try:
    _socket_probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _socket_probe.bind(("127.0.0.1", 0))
except PermissionError:
    _SOCKET_BIND_AVAILABLE = False
finally:
    try:
        _socket_probe.close()
    except Exception:
        pass

pytestmark = pytest.mark.skipif(
    not _SOCKET_BIND_AVAILABLE,
    reason="socket bind is not permitted in this environment",
)

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
