import json
from pathlib import Path

import pytest

from trip_planner.integrations.tpp import (
    BaseTPPIntegrationClient,
    EvaluationResultIngestionError,
    TPPEvaluationResultIngestionService,
    TPPRequestEnvelope,
    TPPResponseEnvelope,
)


def _fixture_path(name: str) -> Path:
    return Path("tests/fixtures/integrations/tpp/results") / name


def _load_fixture(name: str) -> dict:
    return json.loads(_fixture_path(name).read_text(encoding="utf-8"))


class FakeTPPResultClient(BaseTPPIntegrationClient):
    def __init__(self, response: TPPResponseEnvelope) -> None:
        self.response = response

    def execute(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        return self.response


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
