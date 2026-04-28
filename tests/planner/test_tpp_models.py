from trip_planner.app.models.tpp import PollingOutcome


def test_polling_outcome_enum_defines_expected_states() -> None:
    assert PollingOutcome.APPROVED == "approved"
    assert PollingOutcome.REJECTED == "rejected"
    assert PollingOutcome.FAILED == "failed"
    assert PollingOutcome.PENDING == "pending"
    assert PollingOutcome.TIMEOUT == "timeout"
