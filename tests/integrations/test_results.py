import json
from http.client import HTTPMessage
from pathlib import Path
from typing import Literal
from urllib import error as urllib_error

import pytest

from trip_planner.integrations.tpp import (
    BaseTPPIntegrationClient,
    EvaluationResultIngestionError,
    TPPEvaluationResultIngestionService,
    TPPRequestEnvelope,
    TPPResponseEnvelope,
    TPPTransportError,
)


PreservedTransportErrorCode = Literal["breaker_open", "unauthorized", "invalid_response"]


def _fixture_path(name: str) -> Path:
    return (
        Path(__file__).resolve().parents[1] / "fixtures" / "integrations" / "tpp" / "results" / name
    )


def _load_fixture(name: str) -> dict:
    return json.loads(_fixture_path(name).read_text(encoding="utf-8"))


class FakeTPPResultClient(BaseTPPIntegrationClient):
    def __init__(self, response: TPPResponseEnvelope) -> None:
        self.response = response

    def execute(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        return self.response


class RaisingTPPResultClient(BaseTPPIntegrationClient):
    def __init__(self, error: Exception) -> None:
        self.error = error

    def execute(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        del request
        raise self.error


def test_result_ingestion_normalizes_approved_evaluation() -> None:
    fixture = _load_fixture("approved_evaluation.json")
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    service = TPPEvaluationResultIngestionService(FakeTPPResultClient(response))

    record = service.fetch_evaluation_result(
        request,
        proposal_version="proposal-v3",
        scenario_id="scenario-a",
    )

    assert record.linkage.execution_id == "exec-approved-001"
    assert record.linkage.trip_id == "trip-100"
    assert record.evaluation_result is not None
    assert record.evaluation_result.status == "compliant"
    assert record.evaluation_result.approval_requirements[0].role == "manager"
    assert record.is_pending is False


def test_result_ingestion_normalizes_non_compliant_result() -> None:
    fixture = _load_fixture("non_compliant_evaluation.json")
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    service = TPPEvaluationResultIngestionService(FakeTPPResultClient(response))

    record = service.fetch_evaluation_result(
        request,
        proposal_version="proposal-v3",
        scenario_id="scenario-a",
    )

    assert record.evaluation_result is not None
    assert record.evaluation_result.status == "non_compliant"
    assert record.evaluation_result.failure_reasons[0].code == "lodging_cap_exceeded"
    assert record.evaluation_result.preferred_alternatives[0].category == "lodging"


def test_result_ingestion_keeps_deferred_responses_pending() -> None:
    fixture = _load_fixture("deferred_evaluation.json")
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    service = TPPEvaluationResultIngestionService(FakeTPPResultClient(response))

    record = service.fetch_evaluation_result(
        request,
        proposal_version="proposal-v3",
        scenario_id="scenario-a",
    )

    assert record.evaluation_result is None
    assert record.execution_status.state == "deferred"
    assert record.is_pending is True
    assert record.retry is not None
    assert record.retry.backoff_seconds == 45


def test_result_ingestion_rejects_succeeded_payload_without_evaluation_result() -> None:
    fixture = _load_fixture("approved_evaluation.json")
    del fixture["response"]["result_payload"]["evaluation_result"]
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    service = TPPEvaluationResultIngestionService(FakeTPPResultClient(response))

    with pytest.raises(EvaluationResultIngestionError, match="evaluation_result"):
        service.fetch_evaluation_result(
            request,
            proposal_version="proposal-v3",
            scenario_id="scenario-a",
        )


def test_result_ingestion_rejects_missing_linkage_trip_id_with_clear_error() -> None:
    fixture = _load_fixture("approved_evaluation.json")
    fixture["request"]["trip_id"] = None
    del fixture["response"]["result_payload"]["trip_id"]
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    service = TPPEvaluationResultIngestionService(FakeTPPResultClient(response))

    with pytest.raises(EvaluationResultIngestionError, match="trip_id is required"):
        service.fetch_evaluation_result(
            request,
            proposal_version="proposal-v3",
            scenario_id="scenario-a",
        )


def test_result_ingestion_rejects_missing_linkage_proposal_id_with_clear_error() -> None:
    fixture = _load_fixture("approved_evaluation.json")
    fixture["request"]["proposal_id"] = None
    del fixture["response"]["result_payload"]["proposal_id"]
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    service = TPPEvaluationResultIngestionService(FakeTPPResultClient(response))

    with pytest.raises(
        EvaluationResultIngestionError,
        match="proposal_id is required",
    ):
        service.fetch_evaluation_result(
            request,
            proposal_version="proposal-v3",
            scenario_id="scenario-a",
        )


def test_result_ingestion_handles_failed_execution_state() -> None:
    fixture = _load_fixture("failed_execution.json")
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    service = TPPEvaluationResultIngestionService(FakeTPPResultClient(response))

    record = service.fetch_evaluation_result(
        request,
        proposal_version="proposal-v3",
        scenario_id="scenario-a",
    )

    assert record.execution_status.state == "failed"
    assert record.execution_status.terminal is True
    assert record.evaluation_result is None
    assert record.is_pending is False
    assert record.error is not None
    assert record.error.code == "upstream_unavailable"
    assert record.error.retryable is True
    assert record.retry is not None
    assert record.retry.attempt == 1
    assert record.retry.max_attempts == 4


def test_result_ingestion_normalizes_exception_required_result() -> None:
    fixture = _load_fixture("exception_required_evaluation.json")
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    service = TPPEvaluationResultIngestionService(FakeTPPResultClient(response))

    record = service.fetch_evaluation_result(
        request,
        proposal_version="proposal-v3",
        scenario_id="scenario-b",
    )

    assert record.execution_status.state == "succeeded"
    assert record.is_pending is False
    assert record.evaluation_result is not None
    assert record.evaluation_result.status == "exception_required"
    assert record.evaluation_result.evaluation_id == "eval-exception-001"
    assert record.evaluation_result.failure_reasons[0].code == "airfare_cap_exceeded"
    assert record.evaluation_result.failure_reasons[0].severity == "blocking"
    assert record.evaluation_result.approval_requirements[0].role == "vp"
    assert len(record.evaluation_result.exception_guidance) == 1


def test_result_ingestion_handles_cancelled_timeout_execution_state() -> None:
    fixture = _load_fixture("cancelled_execution.json")
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    service = TPPEvaluationResultIngestionService(FakeTPPResultClient(response))

    record = service.fetch_evaluation_result(
        request,
        proposal_version="proposal-v3",
        scenario_id="scenario-a",
    )

    assert record.execution_status.state == "cancelled"
    assert record.execution_status.terminal is True
    assert record.evaluation_result is None
    assert record.is_pending is False
    assert record.error is not None
    assert record.error.code == "evaluation_timeout"
    assert record.error.retryable is False


def test_result_ingestion_rejects_malformed_evaluation_result_shape() -> None:
    fixture = _load_fixture("approved_evaluation.json")
    fixture["response"]["result_payload"]["evaluation_result"] = "not-a-dict"
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    service = TPPEvaluationResultIngestionService(FakeTPPResultClient(response))

    with pytest.raises((EvaluationResultIngestionError, ValueError)):
        service.fetch_evaluation_result(
            request,
            proposal_version="proposal-v3",
            scenario_id="scenario-a",
        )


def test_result_ingestion_converts_raw_transport_exception_with_cause() -> None:
    fixture = _load_fixture("approved_evaluation.json")
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    error = TimeoutError("upstream timeout")
    service = TPPEvaluationResultIngestionService(RaisingTPPResultClient(error))

    with pytest.raises(TPPTransportError) as exc_info:
        service.fetch_evaluation_result(
            request,
            proposal_version="proposal-v3",
            scenario_id="scenario-a",
        )

    assert exc_info.value.error_code == "timeout"
    assert exc_info.value.__cause__ is error


def test_result_ingestion_converts_raw_url_error_to_connection_error_with_cause() -> None:
    fixture = _load_fixture("approved_evaluation.json")
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    error = urllib_error.URLError(ConnectionRefusedError("connection refused"))
    service = TPPEvaluationResultIngestionService(RaisingTPPResultClient(error))

    with pytest.raises(TPPTransportError) as exc_info:
        service.fetch_evaluation_result(
            request,
            proposal_version="proposal-v3",
            scenario_id="scenario-a",
        )

    assert exc_info.value.error_code == "connection_error"
    assert exc_info.value.__cause__ is error


def test_result_ingestion_converts_http_error_to_server_error_with_cause() -> None:
    fixture = _load_fixture("approved_evaluation.json")
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    error = urllib_error.HTTPError(
        url="https://tpp.example.test/api/results",
        code=503,
        msg="Service Unavailable",
        hdrs=HTTPMessage(),
        fp=None,
    )
    service = TPPEvaluationResultIngestionService(RaisingTPPResultClient(error))

    with pytest.raises(TPPTransportError) as exc_info:
        service.fetch_evaluation_result(
            request,
            proposal_version="proposal-v3",
            scenario_id="scenario-a",
        )

    assert exc_info.value.error_code == "server_error"
    assert exc_info.value.__cause__ is error


def test_result_ingestion_converts_unclassified_exception_to_unknown_transport_error() -> None:
    fixture = _load_fixture("approved_evaluation.json")
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    error = RuntimeError("unexpected transport crash")
    service = TPPEvaluationResultIngestionService(RaisingTPPResultClient(error))

    with pytest.raises(TPPTransportError) as exc_info:
        service.fetch_evaluation_result(
            request,
            proposal_version="proposal-v3",
            scenario_id="scenario-a",
        )

    assert exc_info.value.error_code == "unknown"
    assert exc_info.value.status_code == 502
    assert exc_info.value.retryable is False
    assert exc_info.value.__cause__ is error


@pytest.mark.parametrize("error_code", ["breaker_open", "unauthorized", "invalid_response"])
def test_result_ingestion_preserves_typed_transport_error(
    error_code: PreservedTransportErrorCode,
) -> None:
    fixture = _load_fixture("approved_evaluation.json")
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    typed_error = TPPTransportError(f"typed error: {error_code}", error_code=error_code)
    service = TPPEvaluationResultIngestionService(RaisingTPPResultClient(typed_error))

    with pytest.raises(TPPTransportError) as exc_info:
        service.fetch_evaluation_result(
            request,
            proposal_version="proposal-v3",
            scenario_id="scenario-a",
        )

    assert exc_info.value is typed_error
    assert exc_info.value.error_code == error_code
