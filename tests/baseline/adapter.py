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
# for coverage purposes). Keep this list aligned with the source-quality and
# ranking-adjacent symbols asserted in the coverage manifest.
METRIC_KEYS = [
    "anchor_alignment",
    "quality_floor_fit",
    "discovery_fit",
    "freshness_confidence",
    "commerciality",
    "fit_signal",
    "value_signal",
    "quality_signal",
    "input_coverage",
    "scoring_stability",
    "schedule_fit_signal",
    "friction_fit_signal",
    "policy_fit_signal",
    "overall_signal",
]

_SIGNAL_KEYS = [k for k in METRIC_KEYS if k.endswith("_signal")]


def load_option(fixture_name: str):
    from trip_planner.options import TransportOption

    payload = _load_payload(fixture_name)
    return TransportOption.from_dict(payload)


def _fixture_path(fixture_name: str) -> Path:
    path = Path(fixture_name)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "tests":
        return REPO_ROOT / path
    return FIXTURES_DIR / fixture_name


def _load_payload(fixture_name: str) -> dict:
    return json.loads(_fixture_path(fixture_name).read_text(encoding="utf-8"))


def _amount(money) -> float:
    return (
        float(getattr(money, "typical_amount", float("nan"))) if money is not None else float("nan")
    )


def _collect_numeric_keys(value: object, metrics: dict[str, float]) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in METRIC_KEYS and isinstance(nested, int | float):
                metrics[key] = float(nested)
            _collect_numeric_keys(nested, metrics)
    elif isinstance(value, list):
        for nested in value:
            _collect_numeric_keys(nested, metrics)


def _collect_ranking_aliases(payload: dict, metrics: dict[str, float]) -> None:
    results = payload.get("results")
    if not isinstance(results, list) or not results:
        return
    first = results[0]
    if not isinstance(first, dict):
        return

    target_option = first.get("target_option")
    if isinstance(target_option, dict):
        quality = target_option.get("quality_summary")
        if isinstance(quality, dict):
            if isinstance(quality.get("quality_signal"), int | float):
                metrics.setdefault("quality_floor_fit", float(quality["quality_signal"]))
            if isinstance(quality.get("value_signal"), int | float):
                metrics.setdefault("value_signal", float(quality["value_signal"]))
            if isinstance(quality.get("fit_signal"), int | float):
                metrics.setdefault("fit_signal", float(quality["fit_signal"]))

    breakdown = first.get("score_breakdown")
    if isinstance(breakdown, dict):
        contributions = breakdown.get("component_contributions")
        if isinstance(contributions, list):
            numeric_signals = [
                float(item["normalized_signal"])
                for item in contributions
                if isinstance(item, dict) and isinstance(item.get("normalized_signal"), int | float)
            ]
            if numeric_signals:
                metrics.setdefault("anchor_alignment", numeric_signals[0])
            if len(numeric_signals) > 1:
                metrics.setdefault("discovery_fit", numeric_signals[1])


def metrics_for(fixture_name: str) -> dict[str, float]:
    """Reduce one transport option to a flat metrics dict."""
    raw_metrics: dict[str, float] = {}
    payload = _load_payload(fixture_name)
    _collect_numeric_keys(payload, raw_metrics)
    _collect_ranking_aliases(payload, raw_metrics)

    path = _fixture_path(fixture_name)
    legacy_metrics = {
        "cost_total": float("nan"),
        "cost_base_fare": float("nan"),
        "cost_taxes_and_fees": float("nan"),
        "transfer_count": 0.0,
        "minimum_connection_minutes": 0.0,
        "self_navigation_burden_signal": 0.0,
        "baggage_complexity_signal": 0.0,
        "schedule_protection_signal": 0.0,
        "connection_risk_signal": 0.0,
    }
    if FIXTURES_DIR in path.parents:
        o = load_option(fixture_name)
        c, t = o.cost_summary, o.transfer_burden
        f = o.fit_summary
        raw_metrics.update(
            {
                "schedule_fit_signal": float(f.schedule_fit_signal),
                "friction_fit_signal": float(f.friction_fit_signal),
                "experiential_fit_signal": float(f.experiential_fit_signal),
                "policy_fit_signal": float(f.policy_fit_signal),
                "overall_signal": float(f.overall_signal),
            }
        )
        legacy_metrics.update(
            {
                "cost_total": _amount(c.total),
                "cost_base_fare": _amount(c.base_fare),
                "cost_taxes_and_fees": _amount(c.taxes_and_fees),
                "transfer_count": float(t.transfer_count),
                "minimum_connection_minutes": float(t.minimum_connection_minutes or 0.0),
                "self_navigation_burden_signal": float(t.self_navigation_burden_signal),
                "baggage_complexity_signal": float(t.baggage_complexity_signal),
                "schedule_protection_signal": float(t.schedule_protection_signal),
                "connection_risk_signal": float(t.connection_risk_signal),
            }
        )

    return {
        **legacy_metrics,
        "anchor_alignment": raw_metrics.get("anchor_alignment", 0.0),
        "quality_floor_fit": raw_metrics.get("quality_floor_fit", 0.0),
        "discovery_fit": raw_metrics.get("discovery_fit", 0.0),
        "freshness_confidence": raw_metrics.get("freshness_confidence", 0.0),
        "commerciality": raw_metrics.get("commerciality", 0.0),
        "fit_signal": raw_metrics.get("fit_signal", 0.0),
        "value_signal": raw_metrics.get("value_signal", 0.0),
        "quality_signal": raw_metrics.get("quality_signal", 0.0),
        "input_coverage": raw_metrics.get("input_coverage", 0.0),
        "scoring_stability": raw_metrics.get("scoring_stability", 0.0),
        "schedule_fit_signal": raw_metrics.get("schedule_fit_signal", 0.0),
        "friction_fit_signal": raw_metrics.get("friction_fit_signal", 0.0),
        "policy_fit_signal": raw_metrics.get("policy_fit_signal", 0.0),
        "overall_signal": raw_metrics.get("overall_signal", 0.0),
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
    if FIXTURES_DIR not in _fixture_path(fixture_name).parents:
        return True

    from trip_planner.options import TransportOption

    once = load_option(fixture_name).to_dict()
    twice = TransportOption.from_dict(once).to_dict()
    return once == twice
