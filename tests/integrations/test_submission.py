import json
from pathlib import Path

import pytest

from trip_planner.business.policy_contracts import TripPlanProposal
from trip_planner.integrations.tpp import (
    BaseTPPIntegrationClient,
    ProposalSubmissionError,
    TPPProposalSubmissionService,
    TPPRequestEnvelope,
    TPPResponseEnvelope,
)


def _fixture_path(name: str) -> Path:
    fixtures_dir = (
        Path(__file__).resolve().parents[1] / "fixtures" / "integrations" / "tpp"
    )
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
