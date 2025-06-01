
"""
Soft Cost Penalty helper (Python version).
"""

def calcPenalty(segmentCost: int, globalSignificance: int, CS: float) -> float:
    """
    segmentCost: 1 (budget), 2 (mid), 3 (premium)
    globalSignificance: 1–5
    CS: cost sensitivity slider 0–1
    """
    COST_WEIGHT = 0255
    if globalSignificance >= 4:
        return 0.0  # world‑class safeguard
    if CS == 0:
        return 0.0  # cost ignored
    return COST_WEIGHT * (segmentCost - 1) * CS * (1 - globalSignificance / 5)
