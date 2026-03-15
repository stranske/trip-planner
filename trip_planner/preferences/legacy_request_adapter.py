"""Map the repo's legacy request shape into the canonical leisure contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from . import schema
from .models import (
    Anchor,
    BudgetModel,
    DateWindow,
    DurationBounds,
    EvidenceSummary,
    HardConstraints,
    HybridFactor,
    LeisurePreferenceProfile,
    TradeoffDimension,
    TripFrame,
)


def _empty_anchor_groups() -> dict[str, list[Anchor]]:
    return {key: [] for key in schema.ANCHOR_GROUPS}


def _empty_tradeoff_dimensions() -> dict[str, TradeoffDimension]:
    return {
        key: TradeoffDimension()
        for key in schema.TRADEOFF_DIMENSION_KEYS
    }


def _empty_hybrid_factors() -> dict[str, HybridFactor]:
    return {
        "food": HybridFactor(mode="tradeoff"),
        "rest": HybridFactor(mode="tradeoff"),
        "music": HybridFactor(mode="anchor"),
        "route_modes": HybridFactor(mode="tradeoff"),
    }


def _nature_ratio_to_axis(nature_ratio: float) -> float:
    return (2.0 * nature_ratio) - 1.0


def _normalize_route_preferences(values: Mapping[str, Any]) -> dict[str, float]:
    if not values:
        return {}
    scale = 4.0
    preferences: dict[str, float] = {}
    for old_key, new_key in (("train", "rail"), ("boat", "boat"), ("road", "road")):
        raw_value = float(values.get(old_key, 0.0))
        preferences[new_key] = max(0.0, min(raw_value / scale, 1.0))
    return preferences


def adapt_legacy_request(raw_request: Mapping[str, Any]) -> LeisurePreferenceProfile:
    trip_window = raw_request.get("trip_window", {})
    min_weeks = trip_window.get("min_weeks")
    max_weeks = trip_window.get("max_weeks")
    months = [str(month) for month in trip_window.get("months", [])]
    must_see = [str(place) for place in raw_request.get("must_see", [])]

    trip_frame = TripFrame(
        duration_days=int(max_weeks * 7) if isinstance(max_weeks, (int, float)) else None,
        season_window=months,
        trip_stage="mixed",
    )
    hard_constraints = HardConstraints(
        date_window=DateWindow(
            start=str(raw_request["trip_start"]) if raw_request.get("trip_start") else None,
            end=str(raw_request["trip_end"]) if raw_request.get("trip_end") else None,
        ),
        duration_bounds=DurationBounds(
            min_days=int(min_weeks * 7) if isinstance(min_weeks, (int, float)) else None,
            max_days=int(max_weeks * 7) if isinstance(max_weeks, (int, float)) else None,
        ),
        must_include_places=must_see,
    )

    anchors = _empty_anchor_groups()
    anchors["place_anchors"] = [
        Anchor(
            type="place",
            label=place,
            strength=1.0,
            flexibility=0.0,
            notes="Mapped from legacy must_see list.",
        )
        for place in must_see
    ]

    budget_model = BudgetModel(
        total_budget_sensitivity=float(raw_request.get("cost_sensitivity", 0.0)),
    )

    tradeoff_dimensions = _empty_tradeoff_dimensions()
    nature_ratio = float(raw_request.get("nature_ratio", 0.5))
    tradeoff_dimensions["nature_vs_culture"] = TradeoffDimension(
        value=_nature_ratio_to_axis(nature_ratio),
        confidence=0.7,
        salience=0.8,
        stability=0.7,
        trip_stage_sensitivity={
            "initial_design": 0.9,
            "inventory_selection": 0.7,
            "daily_activity_design": 0.5,
            "in_trip_adjustment": 0.3,
        },
        notes="Mapped from legacy nature_ratio field.",
    )

    complexity = str(raw_request.get("complexity_tolerance", "medium"))
    for key, value in schema.COMPLEXITY_TOLERANCE_MAP.get(
        complexity,
        schema.COMPLEXITY_TOLERANCE_MAP["medium"],
    ).items():
        tradeoff_dimensions[key] = TradeoffDimension(
            value=value,
            confidence=0.6,
            salience=0.7,
            stability=0.6,
            trip_stage_sensitivity={
                "initial_design": 0.8,
                "inventory_selection": 0.8,
                "daily_activity_design": 0.5,
                "in_trip_adjustment": 0.4,
            },
            notes=f"Mapped from legacy complexity_tolerance={complexity!r}.",
        )

    hybrid_factors = _empty_hybrid_factors()
    route_preferences = _normalize_route_preferences(raw_request.get("route_passions", {}))
    if route_preferences:
        highest_preference = max(route_preferences.values())
        hybrid_factors["route_modes"] = HybridFactor(
            mode="both" if highest_preference >= 0.5 else "tradeoff",
            salience=highest_preference,
            anchor_strength=highest_preference,
            tradeoff_role="route_design",
            preferences=route_preferences,
            notes="Mapped from legacy route_passions field.",
        )

    evidence_summary = EvidenceSummary(
        sources={
            "legacy_request_fields": [
                "must_see",
                "nature_ratio",
                "complexity_tolerance",
                "cost_sensitivity",
                "route_passions",
            ]
        },
        confidence_notes=[
            "Legacy request inputs provide only a partial view of the planned leisure profile."
        ],
    )

    return LeisurePreferenceProfile(
        trip_frame=trip_frame,
        hard_constraints=hard_constraints,
        anchors=anchors,
        budget_model=budget_model,
        tradeoff_dimensions=tradeoff_dimensions,
        hybrid_factors=hybrid_factors,
        evidence_summary=evidence_summary,
    )


def load_legacy_request(path: str | Path = "request.json") -> LeisurePreferenceProfile:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return adapt_legacy_request(payload)
