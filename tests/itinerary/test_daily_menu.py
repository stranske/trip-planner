from __future__ import annotations

from trip_planner.itinerary.daily_menu import (
    MenuStop,
    SourceFeedbackBandit,
    SourceMix,
    build_daily_menu,
)

CTX = ("kyoto", "stage:planning")


def kyoto_day_candidates() -> list[MenuStop]:
    return [
        MenuStop(
            "fushimi",
            "Fushimi Inari Taisha",
            "landmark",
            3,
            0.95,
            120,
            "editorial",
            25,
            0.05,
            "wikivoyage",
            "green",
            "Thousand torii gates up the mountain; go early.",
        ),
        MenuStop(
            "kiyomizu",
            "Kiyomizu-dera",
            "landmark",
            3,
            0.90,
            75,
            "editorial",
            15,
            0.10,
            "wikivoyage",
            "green",
            "Hillside temple with the famous wooden stage.",
        ),
        MenuStop(
            "nishiki",
            "Nishiki Market",
            "market",
            2,
            0.78,
            60,
            "pageview_inferred",
            10,
            0.20,
            "wikipedia",
            "green",
            "Covered food market, Kyoto's kitchen.",
        ),
        MenuStop(
            "philosophers",
            "Philosopher's Path",
            "walk",
            2,
            0.72,
            45,
            "editorial",
            20,
            0.0,
            "osm",
            "green",
            "Canal-side cherry-tree walk between temples.",
        ),
        MenuStop(
            "gion",
            "Gion district stroll",
            "walk",
            2,
            0.70,
            50,
            "category_default",
            5,
            0.15,
            "wikivoyage",
            "green",
            "Historic geisha district; lanterns at dusk.",
        ),
        MenuStop(
            "teahouse",
            "Premium tea ceremony",
            "meal",
            2,
            0.68,
            60,
            "editorial",
            8,
            0.95,
            "viator",
            "yellow",
            "Reserved hands-on matcha ceremony.",
        ),
        MenuStop(
            "kaiseki",
            "Michelin kaiseki dinner",
            "meal",
            3,
            0.80,
            120,
            "editorial",
            12,
            0.98,
            "opentable",
            "yellow",
            "Multi-course seasonal tasting; reservation required.",
        ),
        MenuStop(
            "bus_tour",
            "Hop-on bus city tour",
            "tour",
            1,
            0.45,
            90,
            "category_default",
            0,
            0.92,
            "getyourguide",
            "yellow",
            "Packaged loop past major sights.",
        ),
        MenuStop(
            "arashiyama",
            "Arashiyama bamboo grove",
            "viewpoint",
            2,
            0.82,
            60,
            "pageview_inferred",
            40,
            0.08,
            "wikipedia",
            "green",
            "Bamboo grove and river; farther west.",
        ),
        MenuStop(
            "blog_cafe",
            "Backstreet kissaten",
            "meal",
            1,
            0.60,
            40,
            "editorial",
            6,
            0.25,
            "indie_blog",
            "yellow",
            "Retro coffee house from an independent travel blog.",
        ),
    ]


def _total_minutes(menu) -> int:
    return menu.rollup.total_visit_minutes + menu.rollup.total_detour_minutes


def test_respects_time_budget() -> None:
    candidates = kyoto_day_candidates()
    for budget in (120, 240, 360, 600):
        menu = build_daily_menu("t", 0, candidates, budget, SourceMix(0.5), context_tags=CTX)
        assert _total_minutes(menu) <= budget
        assert menu.rollup.n_selected >= 1


def test_slider_shifts_commercial_mix() -> None:
    candidates = kyoto_day_candidates()
    local = build_daily_menu("t", 0, candidates, 360, SourceMix(0.10), context_tags=CTX)
    commercial = build_daily_menu("t", 0, candidates, 360, SourceMix(0.85), context_tags=CTX)
    assert local.rollup.realized_commercial_mix < commercial.rollup.realized_commercial_mix
    assert local.rollup.realized_commercial_mix <= 0.45
    assert commercial.rollup.realized_commercial_mix >= 0.45


def test_selection_favors_efficient_high_value_stops() -> None:
    candidates = kyoto_day_candidates()
    menu = build_daily_menu("t", 0, candidates, 180, SourceMix(0.3), context_tags=CTX)
    chosen = set(menu.suggested_selection)
    assert "blog_cafe" in chosen
    assert "kaiseki" not in chosen
    assert "bus_tour" not in chosen


def test_feedback_flips_a_contested_slot() -> None:
    local = MenuStop("A", "Local pick", "walk", 2, 0.80, 55, "editorial", 0, 0.20, "indie_blog", "yellow")
    operator = MenuStop("B", "Operator pick", "tour", 2, 0.80, 55, "editorial", 0, 0.20, "bigco", "yellow")
    candidates = [operator, local]

    base = build_daily_menu("t", 0, candidates, 55, SourceMix(0.2), context_tags=CTX)
    assert base.suggested_selection == ["B"]

    bandit = SourceFeedbackBandit()
    for _ in range(8):
        bandit.update("indie_blog", productivity=1.0, context_tags=CTX, added_to_itinerary=True)
        bandit.update("bigco", productivity=-1.0, context_tags=CTX)
    fed = build_daily_menu(
        "t",
        0,
        candidates,
        55,
        SourceMix(0.2),
        bandit=bandit,
        context_tags=CTX,
    )
    assert fed.suggested_selection == ["A"]
    assert base.suggested_selection != fed.suggested_selection


def test_bandit_weight_orders_sources() -> None:
    bandit = SourceFeedbackBandit()
    for _ in range(5):
        bandit.update("good", productivity=1.0, context_tags=CTX, added_to_itinerary=True)
        bandit.update("bad", productivity=-1.0, context_tags=CTX)
    assert bandit.weight("good", CTX) > bandit.weight("bad", CTX)
    assert bandit.weight("unseen", CTX) > 0.0


def test_determinism() -> None:
    candidates = kyoto_day_candidates()
    a = build_daily_menu("t", 0, candidates, 300, SourceMix(0.4), context_tags=CTX)
    b = build_daily_menu("t", 0, candidates, 300, SourceMix(0.4), context_tags=CTX)
    assert a.suggested_selection == b.suggested_selection
    assert a.rollup.realized_commercial_mix == b.rollup.realized_commercial_mix
