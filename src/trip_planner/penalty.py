"""Cost penalty helpers used by planning workflows."""


def calc_penalty(segment_cost: int, global_significance: int, cost_sensitivity: float) -> float:
    """Return the soft cost penalty for a segment.

    segment_cost: 1 (budget), 2 (mid), 3 (premium)
    global_significance: 1-5
    cost_sensitivity: cost sensitivity slider 0-1
    """
    cost_weight = 0.25
    if global_significance >= 4:
        return 0.0
    if cost_sensitivity == 0:
        return 0.0
    return cost_weight * (segment_cost - 1) * cost_sensitivity * (
        1 - global_significance / 5
    )
