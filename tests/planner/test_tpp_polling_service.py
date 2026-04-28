from __future__ import annotations

import pytest

from trip_planner.app.models.tpp import PollingOutcome
from trip_planner.app.services.tpp_polling_service import (
    TPPPollingService,
    map_poll_response_state_to_outcome,
)
from trip_planner.integrations.tpp.client import TPPContractError


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("approved", PollingOutcome.APPROVED),
        ("rejected", PollingOutcome.REJECTED),
        ("failed", PollingOutcome.FAILED),
        ("pending", PollingOutcome.PENDING),
    ],
)
def test_map_poll_response_state_to_outcome_maps_expected_states(
    state: str, expected: PollingOutcome
) -> None:
    assert map_poll_response_state_to_outcome(state) == expected


def test_polling_service_maps_state_from_payload() -> None:
    service = TPPPollingService()

    assert service.map_poll_response_to_outcome({"state": "approved"}) == PollingOutcome.APPROVED


@pytest.mark.parametrize("payload", [{}, {"state": ""}, {"state": "   "}, {"state": None}])
def test_polling_service_rejects_missing_or_blank_state(payload: dict[str, object]) -> None:
    service = TPPPollingService()

    with pytest.raises(TPPContractError, match="requires non-empty 'state'"):
        service.map_poll_response_to_outcome(payload)
