from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from trip_planner.app.services.planner import (
    _CLARIFYING_SKIP_AFFORDANCE,
    _PLANNER_SYSTEM_PROMPT,
    _extract_date_mentions,
    _extract_destination_mentions,
    _planner_response_structured_blocks,
    _planner_turn_metadata,
)
from trip_planner.app.services.planner_routing import IntentResult
from trip_planner.app.services.planner_runtime_config import (
    build_planner_runtime_config,
)


class BaseTaskClassifier:
    def classify(self, message: str, context: Mapping[str, Any]) -> IntentResult:
        return IntentResult(
            task_class=str(context["base_task_class"]),
            intent=str(context["base_task_class"]),
        )


def _metadata_for(
    message: str,
    *,
    trip_frame: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return _planner_turn_metadata(
        message=message,
        runtime_config=build_planner_runtime_config({}),
        turn_index=0,
        intent_classifier=BaseTaskClassifier(),
        trip_frame=trip_frame,
    )


def test_system_prompt_contract() -> None:
    prompt = _PLANNER_SYSTEM_PROMPT.lower()

    assert "concise" in prompt
    assert "lead with concrete options" in prompt
    assert "uncertainty" in prompt


def test_first_turn_triage_question_cap() -> None:
    open_ended = _metadata_for("help")
    partial_plan = _metadata_for("We want a quiet trip with museums")

    for metadata in (open_ended, partial_plan):
        question_blocks = [
            block
            for block in metadata["visible_response_blocks"]
            if block["kind"] == "clarifying_questions"
        ]
        assert question_blocks
        for block in question_blocks:
            assert len(block["items"]) <= 3
            assert _CLARIFYING_SKIP_AFFORDANCE in block["items"]


def test_month_abbreviation_is_timing_not_destination() -> None:
    message = "We fly Seattle to Boston on Nov 16 with a quiet hotel"

    assert "nov" in _extract_date_mentions(message)
    assert _extract_destination_mentions(message) == ["Seattle", "Boston"]

    metadata = _metadata_for(message)
    signals = metadata["debug_routing_details"]["signals"]
    assert signals["date_hits"] == 1
    assert metadata["plan_maturity"] == "coherent_plan"


def test_persisted_trip_timing_suppresses_redundant_date_question() -> None:
    metadata = _metadata_for(
        "Plan a quiet Boston trip",
        trip_frame={"start_date": "2026-11-16", "end_date": "2026-11-19"},
    )
    questions = [
        item
        for block in metadata["visible_response_blocks"]
        if block["kind"] == "clarifying_questions"
        for item in block["items"]
    ]

    assert not any(
        "date" in question.lower() or "when" in question.lower()
        for question in questions
    )


def test_undated_trip_without_saved_timing_still_asks_for_dates() -> None:
    metadata = _metadata_for("Plan a quiet Boston trip")
    questions = [
        item
        for block in metadata["visible_response_blocks"]
        if block["kind"] == "clarifying_questions"
        for item in block["items"]
    ]

    assert any("date" in question.lower() for question in questions)


def test_standalone_duration_marker_remains_a_timing_signal() -> None:
    metadata = _metadata_for("Plan a week in Boston with a quiet hotel")

    assert metadata["debug_routing_details"]["signals"]["date_hits"] == 1
    assert metadata["plan_maturity"] == "coherent_plan"


def test_low_confidence_surfaces_uncertainty() -> None:
    blocks = _planner_response_structured_blocks(
        content="Compare these options next.",
        metadata={
            "visible_response_blocks": [
                {
                    "kind": "guidance",
                    "title": "Guidance",
                    "items": ["Compare two routes before choosing."],
                }
            ]
        },
        panel={"pending_decisions": [], "option_set": {"options": []}, "next_step_actions": []},
        runtime_context={"source_confidence_summary": {"confidence_label": "sparse"}},
        tool_calls=[],
    )

    text = " ".join(item for block in blocks for item in list(block.get("items") or [])).lower()
    assert "source coverage is thin" in text
    assert "uncertain" in text
