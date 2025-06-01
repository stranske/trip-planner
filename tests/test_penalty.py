import math
from scripts.calc_penalty import calcPenalty

def test_world_class_no_penalty():
    assert calcPenalty(3, 5, 1) == 0   # GS ≥4 → no penalty

def test_budget_no_penalty():
    assert calcPenalty(1, 2, 1) == 0   # cost tier 1 → no penalty

def test_midrange_penalty():
    # segmentCost=2, GS=3, CS=0.5 → 0.5*(2-1)*0.5*(1-3/5) = 0.05
    assert math.isclose(calcPenalty(2, 3, 0.5), 0.05, rel_tol=1e-6)
