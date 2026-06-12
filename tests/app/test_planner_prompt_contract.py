from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from trip_planner.app.services.planner import (
    _CLARIFYING_SKIP_AFFORDANCE,
    _PLANNER_SYSTEM_PROMPT,
    _planner_response_structured_blocks,
    _planner_turn_metadata,
)
from trip_planner.app.services.planner_routing import IntentResult
from trip_planner.app.services.planner_runtime_config import build_planner_runtime_config


class BaseTaskClassifier:
    def classify(self, message: str, context: Mapping[str, Any]) -> IntentResult:
        return IntentResult(
            task_class=str(context["base_task_class"]),
            intent=str(context["base_task_class"]),
        )


def _metadata_for(message: str) -> dict[str, Any]:
    return _planner_turn_metadata(
        message=message,
        runtime_config=build_planner_runtime_config({}),
        turn_index=0,
        intent_classifier=BaseTaskClassifier(),
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

    text = " ".join(
        item
        for block in blocks
        for item in list(block.get("items") or [])
    ).lower()
    assert "source coverage is thin" in text
    assert "uncertain" in text
