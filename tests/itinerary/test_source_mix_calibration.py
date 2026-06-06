from __future__ import annotations

from trip_planner.itinerary.daily_menu import SourceMix, build_daily_menu
from tests.itinerary.test_daily_menu import CTX, kyoto_day_candidates


def test_slider_shifts_realized_mix() -> None:
    candidates = kyoto_day_candidates()

    editorial = build_daily_menu("t", 0, candidates, 360, SourceMix(0.15), context_tags=CTX)
    commercial = build_daily_menu("t", 0, candidates, 360, SourceMix(0.85), context_tags=CTX)

    assert editorial.rollup.realized_commercial_mix < commercial.rollup.realized_commercial_mix
    assert abs(editorial.rollup.realized_commercial_mix - 0.15) <= SourceMix(0.15).tolerance
    assert abs(commercial.rollup.realized_commercial_mix - 0.85) <= SourceMix(0.85).tolerance
