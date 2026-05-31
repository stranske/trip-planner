"""App-specific adapter for trip-planner.

This is the ONLY app-specific piece the shared ``baseline_kit`` needs: a way to
turn an input (here, a transport-option fixture) into a flat dict of named
scalar metrics. Everything else -- directional checks, invariants, golden
masters, the coverage manifest -- is generic and lives in ``baseline_kit``.

The deterministic compute surface is ``TransportOption.from_dict`` (no DB, no
network, no LLM), so baselines here are stable.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "options" / "transport"

# The metric dimensions this adapter exposes (the kit's "input parameter" space
# for coverage purposes).
METRIC_KEYS = [
    "cost_total",
    "cost_base_fare",
    "cost_taxes_and_fees",
    "transfer_count",
    "minimum_connection_minutes",
    "overall_signal",
    "schedule_fit_signal",
    "friction_fit_signal",
    "experiential_fit_signal",
    "policy_fit_signal",
    "self_navigation_burden_signal",
    "baggage_complexity_signal",
    "schedule_protection_signal",
    "connection_risk_signal",
]

_SIGNAL_KEYS = [k for k in METRIC_KEYS if k.endswith("_signal")]


def load_option(fixture_name: str):
    from trip_planner.options import TransportOption

    payload = json.loads((FIXTURES_DIR / fixture_name).read_text(encoding="utf-8"))
    return TransportOption.from_dict(payload)


def _amount(money) -> float:
    return (
        float(getattr(money, "typical_amount", float("nan"))) if money is not None else float("nan")
    )


def metrics_for(fixture_name: str) -> dict[str, float]:
    """Reduce one transport option to a flat metrics dict."""
    o = load_option(fixture_name)
    c, f, t = o.cost_summary, o.fit_summary, o.transfer_burden
    return {
        "cost_total": _amount(c.total),
        "cost_base_fare": _amount(c.base_fare),
        "cost_taxes_and_fees": _amount(c.taxes_and_fees),
        "transfer_count": float(t.transfer_count),
        "minimum_connection_minutes": float(t.minimum_connection_minutes or 0.0),
        "overall_signal": float(f.overall_signal),
        "schedule_fit_signal": float(f.schedule_fit_signal),
        "friction_fit_signal": float(f.friction_fit_signal),
        "experiential_fit_signal": float(f.experiential_fit_signal),
        "policy_fit_signal": float(f.policy_fit_signal),
        "self_navigation_burden_signal": float(t.self_navigation_burden_signal),
        "baggage_complexity_signal": float(t.baggage_complexity_signal),
        "schedule_protection_signal": float(t.schedule_protection_signal),
        "connection_risk_signal": float(t.connection_risk_signal),
    }


def signal_keys() -> list[str]:
    return list(_SIGNAL_KEYS)


def roundtrip_is_stable(fixture_name: str) -> bool:
    """Structural integrity: from_dict/to_dict is idempotent.

    The first parse may normalize (fill defaults, canonicalize legacy keys), so
    we don't require equality with the raw fixture. We require that re-parsing
    the serialized form yields the *same* serialization -- i.e. the model has a
    stable canonical representation.
    """
    from trip_planner.options import TransportOption

    once = load_option(fixture_name).to_dict()
    twice = TransportOption.from_dict(once).to_dict()
    return once == twice
