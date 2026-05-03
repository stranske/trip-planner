import json
from http.client import HTTPMessage
from pathlib import Path
from urllib import error as urllib_error

import pytest

from trip_planner.business.policy_contracts import TripPlanProposal
from trip_planner.integrations.tpp import (
    BaseTPPIntegrationClient,
    ProposalSubmissionError,
    TPPProposalSubmissionService,
    TPPRequestEnvelope,
    TPPResponseEnvelope,
    TPPTransportError,
)


def _fixture_path(name: str) -> Path:
    fixtures_dir = Path(__file__).resolve().parents[1] / "fixtures" / "integrations" / "tpp"
    return fixtures_dir / name


def _load_fixture(name: str) -> dict:
    return json.loads(_fixture_path(name).read_text(encoding="utf-8"))


def _proposal_fixture() -> TripPlanProposal:
    return TripPlanProposal.from_dict(
        {
            "proposal_id": "proposal-123",
            "trip_id": "trip-100",
            "mode": "business",
            "traveler_context": {
                "employee_type": "employee",
                "traveler_experience": "frequent",
                "home_airport": "ORD",
                "loyalty_programs": ["United"],
                "mobility_or_access_needs": [],
            },
            "selected_options": [
                {
                    "category": "airfare",
                    "option_id": "flight-1",
                    "label": "United 123",
                    "vendor": "United",
                    "booking_channel": "Navan",
                    "estimated_cost": {
                        "currency": "USD",
                        "typical_amount": 620.0,
                        "min_amount": 620.0,
                        "max_amount": 620.0,
                    },
                    "justification_refs": ["fare-policy"],
                },
                {
                    "category": "lodging",
                    "option_id": "hotel-1",
                    "label": "Conference Hotel",
                    "vendor": "Marriott",
                    "booking_channel": "Navan",
                    "estimated_cost": {
                        "currency": "USD",
                        "typical_amount": 245.0,
                        "min_amount": 245.0,
                        "max_amount": 245.0,
                    },
                    "justification_refs": ["meeting-proximity"],
                },
            ],
            "cost_summary": {
                "currency": "USD",
                "total_estimated_cost": 1265.0,
                "category_estimates": {
                    "airfare": 620.0,
                    "lodging": 490.0,
                    "ground_transport": 75.0,
                    "meals": 80.0,
                },
                "notes": ["Costs include taxes and expected local transport."],
            },
            "comparables": [
                {
                    "category": "lodging",
                    "label": "Compliant Hotel",
                    "vendor": "Hilton",
                    "booking_channel": "Concur",
                    "estimated_cost": {
                        "currency": "USD",
                        "typical_amount": 198.0,
                        "min_amount": 198.0,
                        "max_amount": 198.0,
                    },
                    "notes": ["Available but farther from venue."],
                }
            ],
            "justifications": [
                {
                    "category": "lodging",
                    "summary": "Conference hotel shortens transfer time before the keynote.",
                    "evidence": ["venue_adjacent"],
                }
            ],
            "booking_channel_summaries": [
                {
                    "category": "airfare",
                    "selected_channel": "Navan",
                    "approved": True,
                    "rationale": "Preferred company channel",
                }
            ],
            "approval_notes": ["International leg requires manager review."],
            "constraint_set_id": "policy-standard-2026-02",
        }
    )


class FakeTPPSubmissionClient(BaseTPPIntegrationClient):
    def __init__(self, response: TPPResponseEnvelope) -> None:
        self.response = response

    def execute(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        return self.response


class RaisingTPPSubmissionClient(BaseTPPIntegrationClient):
    def __init__(self, error: Exception) -> None:
        self.error = error

    def execute(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        del request
        raise self.error


def test_submission_normalizes_deferred_response_and_linkage() -> None:
    fixture = _load_fixture("proposal_submit_deferred.json")
    proposal = _proposal_fixture()
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    service = TPPProposalSubmissionService(FakeTPPSubmissionClient(response))

    record = service.submit_proposal(
        request,
        proposal,
        proposal_version="proposal-v3",
        scenario_id="scenario-a",
    )

    assert record.linkage.trip_id == "trip-100"
    assert record.linkage.proposal_id == "proposal-123"
    assert record.linkage.proposal_version == "proposal-v3"
    assert record.linkage.scenario_id == "scenario-a"
    assert record.execution_id == "exec-001"
    assert record.execution_status.state == "deferred"
    assert record.requires_polling is True
    assert record.retry is not None
    assert record.retry.next_retry_at == "2026-04-03T00:41:31Z"


def test_submission_rejects_non_terminal_response_without_execution_id() -> None:
    fixture = _load_fixture("proposal_submit_deferred.json")
    proposal = _proposal_fixture()
    del fixture["response"]["result_payload"]["execution_id"]
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    service = TPPProposalSubmissionService(FakeTPPSubmissionClient(response))

    with pytest.raises(ProposalSubmissionError, match="execution_id"):
        service.submit_proposal(
            request,
            proposal,
            proposal_version="proposal-v3",
            scenario_id="scenario-a",
        )


def test_submission_normalizes_terminal_failed_state() -> None:
    fixture = _load_fixture("proposal_submit_failed.json")
    proposal = _proposal_fixture()
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    service = TPPProposalSubmissionService(FakeTPPSubmissionClient(response))

    record = service.submit_proposal(
        request,
        proposal,
        proposal_version="proposal-v3",
        scenario_id=None,
    )

    assert record.execution_status.state == "failed"
    assert record.execution_status.terminal is True
    assert record.requires_polling is False
    assert record.error is not None
    assert record.error.code == "proposal_contract_invalid"
    assert record.error.retryable is False
    assert record.linkage.trip_id == "trip-100"
    assert record.linkage.proposal_id == "proposal-123"


def test_submission_normalizes_accepted_state_stores_proposal_id() -> None:
    fixture = _load_fixture("proposal_submit_deferred.json")
    proposal = _proposal_fixture()
    fixture["response"]["execution_status"]["state"] = "accepted"
    fixture["response"]["execution_status"]["terminal"] = False
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    service = TPPProposalSubmissionService(FakeTPPSubmissionClient(response))

    record = service.submit_proposal(
        request,
        proposal,
        proposal_version="proposal-v4",
        scenario_id="scenario-x",
    )

    assert record.execution_status.state == "accepted"
    assert record.requires_polling is True
    assert record.execution_id == "exec-001"
    assert record.linkage.proposal_id == "proposal-123"
    assert record.linkage.proposal_version == "proposal-v4"


def test_submission_converts_raw_transport_exception_with_cause() -> None:
    fixture = _load_fixture("proposal_submit_deferred.json")
    proposal = _proposal_fixture()
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    error = TimeoutError("upstream timeout")
    service = TPPProposalSubmissionService(RaisingTPPSubmissionClient(error))

    with pytest.raises(TPPTransportError) as exc_info:
        service.submit_proposal(
            request,
            proposal,
            proposal_version="proposal-v3",
            scenario_id="scenario-a",
        )

    assert exc_info.value.error_code == "timeout"
    assert exc_info.value.__cause__ is error


def test_submission_converts_raw_url_error_to_connection_error_with_cause() -> None:
    fixture = _load_fixture("proposal_submit_deferred.json")
    proposal = _proposal_fixture()
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    error = urllib_error.URLError(ConnectionRefusedError("connection refused"))
    service = TPPProposalSubmissionService(RaisingTPPSubmissionClient(error))

    with pytest.raises(TPPTransportError) as exc_info:
        service.submit_proposal(
            request,
            proposal,
            proposal_version="proposal-v3",
            scenario_id="scenario-a",
        )

    assert exc_info.value.error_code == "connection_error"
    assert exc_info.value.__cause__ is error


def test_submission_converts_http_error_to_server_error_with_cause() -> None:
    fixture = _load_fixture("proposal_submit_deferred.json")
    proposal = _proposal_fixture()
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    error = urllib_error.HTTPError(
        url="https://tpp.example.test/api/proposals",
        code=503,
        msg="Service Unavailable",
        hdrs=HTTPMessage(),
        fp=None,
    )
    service = TPPProposalSubmissionService(RaisingTPPSubmissionClient(error))

    with pytest.raises(TPPTransportError) as exc_info:
        service.submit_proposal(
            request,
            proposal,
            proposal_version="proposal-v3",
            scenario_id="scenario-a",
        )

    assert exc_info.value.error_code == "server_error"
    assert exc_info.value.__cause__ is error


def test_submission_converts_unclassified_exception_to_unknown_transport_error() -> None:
    fixture = _load_fixture("proposal_submit_deferred.json")
    proposal = _proposal_fixture()
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    error = RuntimeError("unexpected transport crash")
    service = TPPProposalSubmissionService(RaisingTPPSubmissionClient(error))

    with pytest.raises(TPPTransportError) as exc_info:
        service.submit_proposal(
            request,
            proposal,
            proposal_version="proposal-v3",
            scenario_id="scenario-a",
        )

    assert exc_info.value.error_code == "unknown"
    assert exc_info.value.status_code == 502
    assert exc_info.value.retryable is False
    assert exc_info.value.__cause__ is error
