"""Golden ranking scenario eval harness (B2-047).

Runs deterministic leisure ranking against checked-in fixtures without live APIs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from tests.ranking.test_leisure_ranking import (
    _candidate_set,
    _objectives_from_fixture,
    _profile_from_fixture,
    _result_option_id,
)
from trip_planner.ranking import LeisureRankingEngine

_EVAL_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "golden_scenario.json"
_SCORE_TOLERANCE = 1e-4


def _load_golden_scenario() -> dict[str, Any]:
    return json.loads(_EVAL_FIXTURE.read_text(encoding="utf-8"))


def _rank_fixture(fixture_name: str) -> dict[str, float]:
    engine = LeisureRankingEngine()
    ranked = engine.rank_candidate_set(
        _profile_from_fixture(fixture_name),
        _objectives_from_fixture(fixture_name),
        _candidate_set(),
    )
    return {_result_option_id(result): result.score for result in ranked.results}


def test_golden_scenario_scores() -> None:
    golden = _load_golden_scenario()
    fixture_name = cast(str, golden["ranking_fixture"])
    expected_order = cast(list[str], golden["expected_rank_order"])
    expected_scores = cast(dict[str, float], golden["expected_scores"])

    actual_scores = _rank_fixture(fixture_name)
    actual_order = sorted(actual_scores, key=lambda key: (-actual_scores[key], key))

    assert actual_order == expected_order
    for candidate_id, expected_score in expected_scores.items():
        assert candidate_id in actual_scores
        assert abs(actual_scores[candidate_id] - expected_score) <= _SCORE_TOLERANCE
