import json
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Literal
from urllib import error as urllib_error

import pytest

from trip_planner.integrations.tpp import client as tpp_client_module
from trip_planner.integrations.tpp import (
    BaseTPPIntegrationClient,
    HTTPTPPIntegrationClient,
    TPPContractError,
    TPPRequestEnvelope,
    TPPResponseEnvelope,
    TPPRuntimeSettings,
    TPPTransportError,
    TPPTransportPolicy,
)


def _fixture_path(name: str) -> Path:
    return Path("tests/fixtures/integrations/tpp") / name


def _load_fixture(name: str) -> dict:
    return json.loads(_fixture_path(name).read_text(encoding="utf-8"))


def test_policy_fetch_success_fixture_round_trip() -> None:
    fixture = _load_fixture("policy_fetch_success.json")

    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])

    assert request.operation == "fetch_policy_constraints"
    assert request.transport_pattern == "sync"
    assert response.execution_status.state == "succeeded"
    assert response.result_payload["policy_id"] == "policy-2026-01"
    assert response.to_dict()["correlation_id"]["value"] == "corr-policy-001"


def test_proposal_submit_deferred_fixture_round_trip() -> None:
    fixture = _load_fixture("proposal_submit_deferred.json")

    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])

    assert request.operation == "submit_proposal"
    assert response.execution_status.state == "deferred"
    assert response.execution_status.terminal is False
    assert response.retry is not None
    assert response.retry.next_retry_at == "2026-04-03T00:41:31Z"
    assert response.status_endpoint is not None
    assert response.status_endpoint.endswith("/exec-001")


def test_evaluation_failure_fixture_round_trip() -> None:
    fixture = _load_fixture("evaluation_failure.json")

    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])

    assert request.operation == "fetch_evaluation_result"
    assert response.execution_status.state == "failed"
    assert response.error is not None
    assert response.error.retryable is True
    assert response.retry is not None
    assert response.retry.attempt == 1


def test_request_rejects_non_mapping_payload() -> None:
    fixture = _load_fixture("policy_fetch_success.json")
    fixture["request"]["payload"] = ["not", "a", "mapping"]

    with pytest.raises(ValueError, match="payload"):
        TPPRequestEnvelope.from_dict(fixture["request"])


def test_response_rejects_failed_status_without_error() -> None:
    fixture = _load_fixture("evaluation_failure.json")
    del fixture["response"]["error"]

    with pytest.raises(ValueError, match="must include an error"):
        TPPResponseEnvelope.from_dict(fixture["response"])


class FakeTPPClient(BaseTPPIntegrationClient):
    def __init__(self, response: TPPResponseEnvelope) -> None:
        self.response = response
        self.calls: list[str] = []

    def execute(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        self.calls.append(request.operation)
        return self.response


def test_base_client_routes_supported_operations() -> None:
    fixture = _load_fixture("policy_fetch_success.json")
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    client = FakeTPPClient(response)

    result = client.fetch_policy_constraints(request)

    assert result.execution_status.state == "succeeded"
    assert client.calls == ["fetch_policy_constraints"]


def test_base_client_rejects_mismatched_operation() -> None:
    fixture = _load_fixture("policy_fetch_success.json")
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    client = FakeTPPClient(response)

    with pytest.raises(ValueError, match="submit_proposal"):
        client.submit_proposal(request)


def test_http_policy_payload_accepts_trip_plan_trip_id() -> None:
    fixture = _load_fixture("policy_fetch_success.json")
    fixture["request"].pop("trip_id", None)
    fixture["request"]["payload"] = {
        "trip_plan": {"trip_id": "trip-plan-id", "destination": "Chicago"}
    }
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    client = HTTPTPPIntegrationClient(
        TPPRuntimeSettings(
            base_url="https://tpp.example.test",
            access_token="token-123",
            oidc_provider="okta",
        )
    )

    payload = client._policy_request_payload(request)

    assert payload["request"]["trip_id"] == "trip-plan-id"


def test_http_policy_payload_names_all_trip_id_sources() -> None:
    fixture = _load_fixture("policy_fetch_success.json")
    fixture["request"].pop("trip_id", None)
    fixture["request"]["payload"] = {"trip_plan": {"destination": "Chicago"}}
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    client = HTTPTPPIntegrationClient(
        TPPRuntimeSettings(
            base_url="https://tpp.example.test",
            access_token="token-123",
            oidc_provider="okta",
        )
    )

    with pytest.raises(TPPContractError, match="payload.trip_plan.trip_id"):
        client._policy_request_payload(request)


class _FakeHTTPResponse:
    def __init__(self, status_code: int, body: dict | list | str) -> None:
        self.status = status_code
        self._body = body

    def read(self) -> bytes:
        if isinstance(self._body, str):
            return self._body.encode("utf-8")
        return json.dumps(self._body).encode("utf-8")

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> Literal[False]:
        del exc_type, exc, tb
        return False


def _http_client(
    *,
    policy: TPPTransportPolicy | None = None,
    clock=lambda: 0.0,
    breaker_registry=None,
) -> HTTPTPPIntegrationClient:
    return HTTPTPPIntegrationClient(
        TPPRuntimeSettings(
            base_url="https://tpp.example.test",
            access_token="token-123",
            oidc_provider="okta",
        ),
        policy=policy or TPPTransportPolicy(backoff_initial_seconds=0.0, backoff_max_seconds=0.0),
        sleep=lambda _delay: None,
        clock=clock,
        jitter=lambda _start, _end: 0.0,
        breaker_registry=breaker_registry if breaker_registry is not None else {},
    )


def _install_urlopen(
    monkeypatch: pytest.MonkeyPatch,
    responses: list[_FakeHTTPResponse | Exception],
    *,
    captured_timeouts: list[float] | None = None,
    call_counter: list[int] | None = None,
) -> None:
    queue = list(responses)

    def _fake_urlopen(request, timeout=0):
        del request
        if call_counter is not None:
            call_counter[0] += 1
        if captured_timeouts is not None:
            captured_timeouts.append(timeout)
        response = queue.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(tpp_client_module.urllib_request, "urlopen", _fake_urlopen)


def test_transport_policy_defaults_and_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "TPP_TIMEOUT_SECONDS",
        "TPP_TRANSPORT_CONNECT_TIMEOUT_SECONDS",
        "TPP_TRANSPORT_READ_TIMEOUT_SECONDS",
        "TPP_TRANSPORT_MAX_ATTEMPTS",
        "TPP_TRANSPORT_BACKOFF_INITIAL_SECONDS",
        "TPP_TRANSPORT_BACKOFF_MAX_SECONDS",
        "TPP_TRANSPORT_BREAKER_FAILURE_THRESHOLD",
        "TPP_TRANSPORT_BREAKER_RESET_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)

    default_policy = TPPTransportPolicy.from_env()

    assert default_policy.connect_timeout_seconds == 5.0
    assert default_policy.read_timeout_seconds == 15.0
    assert default_policy.max_attempts == 3
    assert default_policy.backoff_initial_seconds == 0.5
    assert default_policy.backoff_max_seconds == 4.0
    assert default_policy.breaker_failure_threshold == 5
    assert default_policy.breaker_reset_seconds == 30.0

    monkeypatch.setenv("TPP_TRANSPORT_CONNECT_TIMEOUT_SECONDS", "2")
    monkeypatch.setenv("TPP_TRANSPORT_READ_TIMEOUT_SECONDS", "9")
    monkeypatch.setenv("TPP_TRANSPORT_MAX_ATTEMPTS", "4")
    monkeypatch.setenv("TPP_TRANSPORT_BACKOFF_INITIAL_SECONDS", "0.1")
    monkeypatch.setenv("TPP_TRANSPORT_BACKOFF_MAX_SECONDS", "1.5")
    monkeypatch.setenv("TPP_TRANSPORT_BREAKER_FAILURE_THRESHOLD", "7")
    monkeypatch.setenv("TPP_TRANSPORT_BREAKER_RESET_SECONDS", "11")

    policy = TPPTransportPolicy.from_env()

    assert policy.connect_timeout_seconds == 2.0
    assert policy.read_timeout_seconds == 9.0
    assert policy.max_attempts == 4
    assert policy.backoff_initial_seconds == 0.1
    assert policy.backoff_max_seconds == 1.5
    assert policy.breaker_failure_threshold == 7
    assert policy.breaker_reset_seconds == 11.0


def test_http_transport_retries_server_errors_then_surfaces_typed_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_counter = [0]
    _install_urlopen(
        monkeypatch,
        [
            _FakeHTTPResponse(503, {"detail": "try later"}),
            _FakeHTTPResponse(503, {"detail": "still later"}),
            _FakeHTTPResponse(503, {"detail": "failed"}),
        ],
        call_counter=call_counter,
    )
    client = _http_client(
        policy=TPPTransportPolicy(
            max_attempts=3,
            backoff_initial_seconds=0.0,
            backoff_max_seconds=0.0,
            breaker_failure_threshold=5,
        )
    )

    with pytest.raises(TPPTransportError) as exc_info:
        client._request_json(method="POST", path="/api/fail", json_payload={})

    assert exc_info.value.error_code == "server_error"
    assert exc_info.value.retryable is True
    assert call_counter[0] == 3


def test_http_transport_uses_connect_timeout_policy_for_urlopen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_timeouts: list[float] = []
    _install_urlopen(
        monkeypatch,
        [_FakeHTTPResponse(200, {"ok": True})],
        captured_timeouts=captured_timeouts,
    )
    client = _http_client(
        policy=TPPTransportPolicy(
            connect_timeout_seconds=2.5,
            read_timeout_seconds=9.0,
            max_attempts=1,
        )
    )

    payload = client._request_json(method="POST", path="/api/ok", json_payload={})

    assert payload == {"ok": True}
    assert captured_timeouts == [2.5]


def test_http_transport_classifies_connection_timeout_unauthorized_and_invalid_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases: list[tuple[_FakeHTTPResponse | Exception, str]] = [
        (urllib_error.URLError(ConnectionRefusedError("refused")), "connection_error"),
        (socket.timeout("slow response"), "timeout"),
        (_FakeHTTPResponse(401, {"detail": "bad token"}), "unauthorized"),
        (_FakeHTTPResponse(200, "not-json"), "invalid_response"),
    ]
    for response, error_code in cases:
        _install_urlopen(monkeypatch, [response])
        client = _http_client(policy=TPPTransportPolicy(max_attempts=1))

        with pytest.raises(TPPTransportError) as exc_info:
            client._request_json(method="POST", path=f"/api/{error_code}", json_payload={})

        assert exc_info.value.error_code == error_code


def test_transport_error_rejects_unknown_error_code() -> None:
    with pytest.raises(ValueError, match="error_code must be one of"):
        TPPTransportError("bad code", error_code="not_a_real_code")  # type: ignore[arg-type]


def test_http_transport_opens_breaker_after_consecutive_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_urlopen(
        monkeypatch,
        [urllib_error.URLError(ConnectionRefusedError("refused")) for _ in range(5)],
    )
    registry: dict[str, object] = {}
    client = _http_client(
        policy=TPPTransportPolicy(max_attempts=1, breaker_failure_threshold=5),
        breaker_registry=registry,
    )
    for _ in range(5):
        with pytest.raises(TPPTransportError) as exc_info:
            client._request_json(method="POST", path="/api/down", json_payload={})
        assert exc_info.value.error_code == "connection_error"

    with pytest.raises(TPPTransportError) as exc_info:
        client._request_json(method="POST", path="/api/down", json_payload={})

    assert exc_info.value.error_code == "breaker_open"


def test_http_transport_half_open_success_closes_breaker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_time = 0.0

    def _clock() -> float:
        return current_time

    _install_urlopen(
        monkeypatch,
        [
            urllib_error.URLError(ConnectionRefusedError("refused")),
            _FakeHTTPResponse(200, {"ok": True}),
            urllib_error.URLError(ConnectionRefusedError("refused-again")),
        ],
    )
    client = _http_client(
        policy=TPPTransportPolicy(
            max_attempts=1,
            breaker_failure_threshold=1,
            breaker_reset_seconds=10.0,
        ),
        clock=_clock,
        breaker_registry={},
    )

    with pytest.raises(TPPTransportError) as first_failure:
        client._request_json(method="POST", path="/api/down", json_payload={})
    assert first_failure.value.error_code == "connection_error"

    current_time = 5.0
    with pytest.raises(TPPTransportError) as open_breaker:
        client._request_json(method="POST", path="/api/down", json_payload={})
    assert open_breaker.value.error_code == "breaker_open"

    breaker = next(iter(client._breaker_registry.values()))
    assert breaker.state == "open"
    current_time = 11.0
    assert client._request_json(method="POST", path="/api/down", json_payload={}) == {"ok": True}
    assert breaker.state == "closed"

    current_time = 12.0
    with pytest.raises(TPPTransportError) as after_close:
        client._request_json(method="POST", path="/api/down", json_payload={})
    assert after_close.value.error_code == "connection_error"


def test_http_transport_half_open_allows_single_trial_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_time = 0.0

    def _clock() -> float:
        return current_time

    _install_urlopen(
        monkeypatch,
        [
            urllib_error.URLError(ConnectionRefusedError("refused")),
            _FakeHTTPResponse(200, {"ok": True}),
        ],
    )
    client = _http_client(
        policy=TPPTransportPolicy(
            max_attempts=1,
            breaker_failure_threshold=1,
            breaker_reset_seconds=10.0,
        ),
        clock=_clock,
        breaker_registry={},
    )

    with pytest.raises(TPPTransportError):
        client._request_json(method="POST", path="/api/down", json_payload={})

    current_time = 11.0
    assert client._request_json(method="POST", path="/api/down", json_payload={}) == {"ok": True}

    breaker = next(iter(client._breaker_registry.values()))
    breaker.opened_at = 11.0
    breaker.half_open = True
    breaker._half_open_trial_in_flight = True
    current_time = 22.0

    with pytest.raises(TPPTransportError) as exc_info:
        client._request_json(method="POST", path="/api/down", json_payload={})
    assert exc_info.value.error_code == "breaker_open"


def test_http_transport_integration_against_stub_http_server_reports_server_error() -> None:
    class _Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"detail": "temporarily unavailable"}')

        def log_message(self, *_args) -> None:
            return

    try:
        server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    except PermissionError:
        pytest.skip("Local socket bind is not permitted in this execution environment.")
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = HTTPTPPIntegrationClient(
            TPPRuntimeSettings(
                base_url=f"http://127.0.0.1:{server.server_port}",
                access_token="token-123",
                oidc_provider="okta",
            ),
            policy=TPPTransportPolicy(max_attempts=1, breaker_failure_threshold=5),
            breaker_registry={},
        )

        with pytest.raises(TPPTransportError) as exc_info:
            client._request_json(method="POST", path="/stub", json_payload={})
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)

    assert exc_info.value.error_code == "server_error"
