import math

from trip_planner.penalty import calc_penalty


def test_world_class_no_penalty():
    assert calc_penalty(3, 5, 1) == 0


def test_budget_no_penalty():
    assert calc_penalty(1, 2, 1) == 0


def test_midrange_penalty():
    assert math.isclose(calc_penalty(2, 3, 0.5), 0.05, rel_tol=1e-6)
