"""Trip-planner economic/structural invariants (always true for any option).

Bounds are app-specific; the result type and assertion helper are shared
(``baseline_kit.InvariantResult`` / ``assert_invariants``).
"""

from __future__ import annotations

import math

from baseline_kit import InvariantResult

from . import adapter


def check_option(fixture_name: str) -> list[InvariantResult]:
    m = adapter.metrics_for(fixture_name)
    results: list[InvariantResult] = []

    def add(name, ok, detail, severity="error"):
        results.append(InvariantResult(name, bool(ok), severity, detail))

    # Costs non-negative where present. NaN means "field absent" (e.g. a rental
    # with no separate taxes line) and is allowed -- only finite values are bounded.
    for key in ("cost_total", "cost_base_fare", "cost_taxes_and_fees"):
        add(f"{key}_non_negative", math.isnan(m[key]) or m[key] >= 0, f"{key}={m[key]}")

    # total >= base fare (total includes taxes/fees on top of base), when both present.
    both_present = math.isfinite(m["cost_total"]) and math.isfinite(m["cost_base_fare"])
    add(
        "total_ge_base_fare",
        (not both_present) or m["cost_total"] >= m["cost_base_fare"] - 1e-9,
        f"total={m['cost_total']} base={m['cost_base_fare']}",
    )

    # Transfer count is a non-negative integer.
    add(
        "transfer_count_non_negative_int",
        m["transfer_count"] >= 0 and float(m["transfer_count"]).is_integer(),
        f"transfer_count={m['transfer_count']}",
    )

    # All fit/burden signals are probabilities in [0, 1].
    for key in adapter.signal_keys():
        add(f"{key}_in_unit_interval", 0.0 <= m[key] <= 1.0, f"{key}={m[key]}")

    # Connection minutes non-negative.
    add(
        "min_connection_minutes_non_negative",
        m["minimum_connection_minutes"] >= 0,
        f"min_connection_minutes={m['minimum_connection_minutes']}",
    )

    # Structural integrity: serialization is idempotent (stable canonical form).
    add(
        "roundtrip_stable",
        adapter.roundtrip_is_stable(fixture_name),
        "from_dict/to_dict is not idempotent",
    )

    return results
