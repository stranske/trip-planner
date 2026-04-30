from __future__ import annotations

import pytest

from trip_planner.integrations.tpp.contracts import (
    TPPCorrelationId,
    TPPErrorRecord,
    TPPExecutionStatus,
    TPPRequestEnvelope,
    TPPResponseEnvelope,
)
from trip_planner.integrations.tpp.services.tpp_polling_service import (
    TPPPollingService,
    _next_wait,
)


class FakeClock:
    def __init__(self) -> None:
        self.current = 0.0

    def now(self) -> float:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.current += seconds


def _request() -> TPPRequestEnvelope:
    return TPPRequestEnvelope(
        operation="poll_execution_status",
        request_id="request-1",
        correlation_id=TPPCorrelationId(value="corr-1"),
        payload={"proposal_id": "proposal-123"},
        proposal_id="proposal-123",
        transport_pattern="async",
    )


def _response(
    state: str, *, terminal: bool, result_payload: dict[str, object] | None = None
) -> TPPResponseEnvelope:
    error = TPPErrorRecord(code="failed", message="failed") if state == "failed" else None
    return TPPResponseEnvelope(
        operation="poll_execution_status",
        request_id="request-1",
        correlation_id=TPPCorrelationId(value="corr-1"),
        transport_pattern="async",
        execution_status=TPPExecutionStatus(state=state, terminal=terminal),
        result_payload=result_payload or {},
        error=error,
    )


@pytest.mark.parametrize(
    ("attempt", "expected"),
    [(1, 1.0), (2, 2.0), (3, 4.0), (4, 8.0), (5, 16.0), (6, 30.0), (7, 30.0)],
)
def test_next_wait_matches_doubling_with_cap(attempt: int, expected: float) -> None:
    assert _next_wait(attempt) == expected


def test_poll_pending_then_success_records_expected_sleeps() -> None:
    clock = FakeClock()
    sleeps: list[float] = []
    responses = iter(
        [
            _response("running", terminal=False),
            _response("running", terminal=False),
            _response(
                "succeeded", terminal=True, result_payload={"trip_id": "t-1", "proposal_id": "p-1"}
            ),
        ]
    )

    def provider(_request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        return next(responses)

    def sleeper(seconds: float) -> None:
        sleeps.append(seconds)
        clock.sleep(seconds)

    service = TPPPollingService(provider, timeout_seconds=20.0, sleeper=sleeper, now=clock.now)

    response = service.poll(_request())

    assert response.execution_status.state == "succeeded"
    assert sleeps == [1.0, 2.0]


def test_poll_pending_then_failure_records_expected_sleeps() -> None:
    clock = FakeClock()
    sleeps: list[float] = []
    responses = iter(
        [
            _response("running", terminal=False),
            _response("failed", terminal=True),
        ]
    )

    def provider(_request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        return next(responses)

    def sleeper(seconds: float) -> None:
        sleeps.append(seconds)
        clock.sleep(seconds)

    service = TPPPollingService(provider, timeout_seconds=20.0, sleeper=sleeper, now=clock.now)

    response = service.poll(_request())

    assert response.execution_status.state == "failed"
    assert sleeps == [1.0]


def test_poll_pending_until_timeout_returns_timeout_envelope() -> None:
    clock = FakeClock()
    sleeps: list[float] = []
    call_count = 0

    def provider(_request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        nonlocal call_count
        call_count += 1
        return _response("running", terminal=False)

    def sleeper(seconds: float) -> None:
        sleeps.append(seconds)
        clock.sleep(seconds)

    service = TPPPollingService(provider, timeout_seconds=5.0, sleeper=sleeper, now=clock.now)

    response = service.poll(_request())
    payload = response.to_dict()

    assert response.execution_status.state == "timeout"
    assert response.execution_status.terminal is True
    assert response.execution_status.summary == "timeout"
    assert response.execution_status.external_status == "timeout"
    assert response.operation == "poll_execution_status"
    assert response.request_id == "request-1"
    assert response.correlation_id.value == "corr-1"
    assert response.result_payload == {}
    assert response.evaluation_result == {}
    assert response.error is None
    assert payload["execution_status"]["state"] == "timeout"
    assert payload["result_payload"] == {}
    assert payload["evaluation_result"] == {}
    round_tripped = TPPResponseEnvelope.from_dict(payload)
    assert round_tripped.execution_status.state == "timeout"
    assert round_tripped.result_payload == {}
    assert round_tripped.evaluation_result == {}
    assert call_count == 3
    assert sleeps == [1.0, 2.0, 2.0]


def test_poll_does_not_require_second_external_call_to_detect_timeout() -> None:
    clock = FakeClock()
    call_count = 0

    def provider(_request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        nonlocal call_count
        call_count += 1
        return _response("running", terminal=False)

    service = TPPPollingService(provider, timeout_seconds=1.0, sleeper=clock.sleep, now=clock.now)

    response = service.poll(_request())

    assert response.execution_status.state == "timeout"
    assert call_count == 1


def test_poll_timeout_returns_empty_payload_and_evaluation_result_lookup() -> None:
    clock = FakeClock()

    def provider(_request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        return _response("running", terminal=False)

    service = TPPPollingService(provider, timeout_seconds=1.0, sleeper=clock.sleep, now=clock.now)

    response = service.poll(_request())
    payload = response.to_dict()

    assert response.execution_status.state == "timeout"
    assert response.result_payload == {}
    assert response.evaluation_result == {}
    assert payload["evaluation_result"] == {}
    assert response.error is None


def test_poll_truncates_first_sleep_to_remaining_timeout() -> None:
    clock = FakeClock()
    sleeps: list[float] = []
    call_count = 0

    def provider(_request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        nonlocal call_count
        call_count += 1
        return _response("running", terminal=False)

    def sleeper(seconds: float) -> None:
        sleeps.append(seconds)
        clock.sleep(seconds)

    service = TPPPollingService(provider, timeout_seconds=0.5, sleeper=sleeper, now=clock.now)

    response = service.poll(_request())

    assert response.execution_status.state == "timeout"
    assert response.result_payload == {}
    assert response.evaluation_result == {}
    assert sleeps == [0.5]
    assert call_count == 1


def test_poll_uses_capped_cadence_and_truncates_final_sleep_to_timeout_remaining() -> None:
    clock = FakeClock()
    sleeps: list[float] = []
    calls = 0

    def provider(_request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        nonlocal calls
        calls += 1
        return _response("running", terminal=False)

    def sleeper(seconds: float) -> None:
        sleeps.append(seconds)
        clock.sleep(seconds)

    service = TPPPollingService(provider, timeout_seconds=95.0, sleeper=sleeper, now=clock.now)

    response = service.poll(_request())

    assert response.execution_status.state == "timeout"
    assert sleeps == [1.0, 2.0, 4.0, 8.0, 16.0, 30.0, 30.0, 4.0]
    assert calls == 8


def test_polling_service_rejects_non_callable_provider() -> None:
    with pytest.raises(ValueError, match="poll_response_provider must be callable"):
        TPPPollingService(None, timeout_seconds=1.0)  # type: ignore[arg-type]
