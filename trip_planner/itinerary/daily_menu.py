"""Deterministic daily activity menu assembly."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import Any

from trip_planner._validators import (
    require_non_empty,
    require_non_negative,
    require_probability,
    require_strings,
)


@dataclass(frozen=True, slots=True)
class MenuStop:
    stop_id: str
    name: str
    category: str
    priority_tier: int
    priority_score: float
    est_visit_minutes: int
    visit_minutes_basis: str
    detour_minutes: int
    commerciality: float
    source_id: str
    source_tier: str
    why_go: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.stop_id, "stop_id")
        require_non_empty(self.name, "name")
        require_non_empty(self.category, "category")
        if self.priority_tier not in (1, 2, 3):
            raise ValueError("priority_tier must be 1, 2, or 3")
        require_probability(self.priority_score, "priority_score")
        require_non_negative(self.est_visit_minutes, "est_visit_minutes")
        require_non_empty(self.visit_minutes_basis, "visit_minutes_basis")
        require_non_negative(self.detour_minutes, "detour_minutes")
        require_probability(self.commerciality, "commerciality")
        require_non_empty(self.source_id, "source_id")
        require_non_empty(self.source_tier, "source_tier")

    @property
    def value_per_minute(self) -> float:
        cost = self.est_visit_minutes + self.detour_minutes
        return self.priority_score / cost if cost > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SourceMix:
    commercial_target: float
    tolerance: float = 0.15

    def __post_init__(self) -> None:
        require_probability(self.commercial_target, "commercial_target")
        require_probability(self.tolerance, "tolerance")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class MenuRollup:
    total_visit_minutes: int
    total_detour_minutes: int
    realized_commercial_mix: float
    tier_histogram: dict[int, int]
    n_selected: int

    def __post_init__(self) -> None:
        require_non_negative(self.total_visit_minutes, "total_visit_minutes")
        require_non_negative(self.total_detour_minutes, "total_detour_minutes")
        require_probability(self.realized_commercial_mix, "realized_commercial_mix")
        require_non_negative(self.n_selected, "n_selected")
        if any(tier not in (1, 2, 3) or count < 0 for tier, count in self.tier_histogram.items()):
            raise ValueError("tier_histogram must use tiers 1, 2, or 3 with non-negative counts")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DailyMenu:
    trip_id: str
    day_index: int
    time_budget_minutes: int
    mix_target: SourceMix
    candidates: list[MenuStop] = field(default_factory=list)
    suggested_selection: list[str] = field(default_factory=list)
    rollup: MenuRollup = field(
        default_factory=lambda: MenuRollup(
            total_visit_minutes=0,
            total_detour_minutes=0,
            realized_commercial_mix=0.0,
            tier_histogram={},
            n_selected=0,
        )
    )

    def __post_init__(self) -> None:
        require_non_empty(self.trip_id, "trip_id")
        require_non_negative(self.day_index, "day_index")
        require_non_negative(self.time_budget_minutes, "time_budget_minutes")
        if not isinstance(self.mix_target, SourceMix):
            raise ValueError("mix_target must be a SourceMix")
        if any(not isinstance(item, MenuStop) for item in self.candidates):
            raise ValueError("candidates must contain MenuStop instances")
        require_strings(self.suggested_selection, "suggested_selection")
        known_ids = {item.stop_id for item in self.candidates}
        if not set(self.suggested_selection).issubset(known_ids):
            raise ValueError("suggested_selection must reference candidate stop_id values")
        if not isinstance(self.rollup, MenuRollup):
            raise ValueError("rollup must be a MenuRollup")

    def selected_stops(self) -> list[MenuStop]:
        by_id = {stop.stop_id: stop for stop in self.candidates}
        return [by_id[stop_id] for stop_id in self.suggested_selection]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SourceFeedbackBandit:
    """Deterministic UCB1 source weighting by context bucket."""

    def __init__(self, exploration: float = 0.5) -> None:
        require_non_negative(exploration, "exploration")
        self.exploration = exploration
        self._stats: dict[tuple[str, str], list[float]] = {}
        self._total: dict[str, int] = {}

    @staticmethod
    def _bucket(context_tags: Iterable[str]) -> str:
        return "|".join(sorted(context_tags)) or "_global"

    def update(
        self,
        source_id: str,
        productivity: float,
        context_tags: Iterable[str],
        *,
        added_to_itinerary: bool = False,
    ) -> None:
        require_non_empty(source_id, "source_id")
        reward = max(0.0, min(1.0, 0.5 + 0.5 * productivity))
        if added_to_itinerary:
            reward = min(1.0, reward + 0.25)
        bucket = self._bucket(context_tags)
        key = (bucket, source_id)
        stats = self._stats.setdefault(key, [0.0, 0.0])
        stats[0] += reward
        stats[1] += 1.0
        self._total[bucket] = self._total.get(bucket, 0) + 1

    def weight(self, source_id: str, context_tags: Iterable[str]) -> float:
        require_non_empty(source_id, "source_id")
        bucket = self._bucket(context_tags)
        stats = self._stats.get((bucket, source_id))
        total = max(1, self._total.get(bucket, 0))
        if not stats or stats[1] == 0:
            mean = 0.5
            bonus = self.exploration * math.sqrt(math.log(total + 1))
        else:
            mean = stats[0] / stats[1]
            bonus = self.exploration * math.sqrt(math.log(total + 1) / stats[1])
        return mean + bonus


def calibrate(
    candidates: list[MenuStop],
    mix: SourceMix,
    time_budget_minutes: int,
    *,
    bandit: SourceFeedbackBandit | None = None,
    context_tags: Iterable[str] = (),
    balance_lambda: float = 2.0,
) -> list[str]:
    """Greedily fill the day while steering toward the requested commercial mix."""

    require_non_negative(time_budget_minutes, "time_budget_minutes")
    if any(not isinstance(item, MenuStop) for item in candidates):
        raise ValueError("candidates must contain MenuStop instances")
    context = tuple(context_tags)

    def base_score(stop: MenuStop) -> float:
        source_weight = bandit.weight(stop.source_id, context) if bandit is not None else 1.0
        return stop.value_per_minute * (0.5 + 0.5 * stop.priority_score) * source_weight

    remaining = sorted(candidates, key=base_score, reverse=True)
    selected: list[MenuStop] = []
    spent = 0

    while remaining:
        current_mean = (
            sum(stop.commerciality for stop in selected) / len(selected)
            if selected
            else mix.commercial_target
        )

        def adjusted_score(stop: MenuStop) -> float:
            if spent + stop.est_visit_minutes + stop.detour_minutes > time_budget_minutes:
                return float("-inf")
            selected_count = len(selected)
            projected_mean = (current_mean * selected_count + stop.commerciality) / (
                selected_count + 1
            )
            drift = abs(projected_mean - mix.commercial_target)
            penalty = balance_lambda * max(0.0, drift - mix.tolerance)
            return base_score(stop) - penalty

        best = max(remaining, key=adjusted_score)
        if adjusted_score(best) == float("-inf"):
            break
        selected.append(best)
        spent += best.est_visit_minutes + best.detour_minutes
        remaining.remove(best)

    return [stop.stop_id for stop in selected]


def build_daily_menu(
    trip_id: str,
    day_index: int,
    candidates: list[MenuStop],
    time_budget_minutes: int,
    mix: SourceMix,
    *,
    bandit: SourceFeedbackBandit | None = None,
    context_tags: Iterable[str] = (),
) -> DailyMenu:
    selection = calibrate(
        candidates,
        mix,
        time_budget_minutes,
        bandit=bandit,
        context_tags=context_tags,
    )
    by_id = {stop.stop_id: stop for stop in candidates}
    chosen = [by_id[stop_id] for stop_id in selection]
    realized = sum(stop.commerciality for stop in chosen) / len(chosen) if chosen else 0.0
    tier_histogram: dict[int, int] = {}
    for stop in chosen:
        tier_histogram[stop.priority_tier] = tier_histogram.get(stop.priority_tier, 0) + 1
    ranked = sorted(candidates, key=lambda stop: stop.value_per_minute, reverse=True)
    return DailyMenu(
        trip_id=trip_id,
        day_index=day_index,
        time_budget_minutes=time_budget_minutes,
        mix_target=mix,
        candidates=ranked,
        suggested_selection=selection,
        rollup=MenuRollup(
            total_visit_minutes=sum(stop.est_visit_minutes for stop in chosen),
            total_detour_minutes=sum(stop.detour_minutes for stop in chosen),
            realized_commercial_mix=round(realized, 3),
            tier_histogram=tier_histogram,
            n_selected=len(chosen),
        ),
    )
