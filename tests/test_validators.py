import pytest

from trip_planner._validators import require_finite, require_non_negative


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_validators_reject_non_finite_values(value: float) -> None:
    with pytest.raises(ValueError, match="must be finite"):
        require_finite(value, "amount")
    with pytest.raises(ValueError, match="must be finite"):
        require_non_negative(value, "amount")


def test_non_negative_validator_accepts_zero_and_positive_finite_values() -> None:
    require_non_negative(0.0, "amount")
    require_non_negative(10.5, "amount")
