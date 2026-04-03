import json
from pathlib import Path

import pytest

from trip_planner.integrations.tpp import (
    BaseTPPIntegrationClient,
    TPPRequestEnvelope,
    TPPResponseEnvelope,
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
