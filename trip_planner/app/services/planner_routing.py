"""Planner runtime model-routing policy.

Maps planner turn task classes to a discrete model effort class
(``fast`` / ``standard`` / ``deep``) so traveler interactions feel
responsive while planning-heavy turns receive deeper synthesis. The
policy is deterministic, takes pure inputs (message text, the existing
maturity-derived base task class, the selected planning mode, and
provider/fallback state), and returns a :class:`RoutingDecision` that
the planner runtime persists on per-turn metadata for diagnostics and
tests. Traveler-facing planner copy does not consume these values.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

EFFORT_FAST: Final = "fast"
EFFORT_STANDARD: Final = "standard"
EFFORT_DEEP: Final = "deep"

EFFORT_CLASSES: Final = (EFFORT_FAST, EFFORT_STANDARD, EFFORT_DEEP)

TASK_QUICK_ACKNOWLEDGEMENT: Final = "quick_acknowledgement"
TASK_NOTE_CAPTURE: Final = "note_capture"
TASK_FOCUS_SWITCH: Final = "focus_switch"
TASK_CLARIFYING_QUESTION: Final = "clarifying_question"
TASK_FIRST_TURN_TRIAGE: Final = "first_turn_triage"
TASK_PLANNING_SYNTHESIS: Final = "planning_synthesis"
TASK_ROUTE_COMPARISON: Final = "route_comparison"
TASK_MAJOR_REVISION: Final = "major_revision"
TASK_POLICY_PREPARATION: Final = "policy_preparation"
TASK_RESEARCH_TOOL_PASS: Final = "research_tool_pass"
TASK_FINAL_SUMMARY: Final = "final_summary"

TASK_CLASSES: Final = (
    TASK_QUICK_ACKNOWLEDGEMENT,
    TASK_NOTE_CAPTURE,
    TASK_FOCUS_SWITCH,
    TASK_CLARIFYING_QUESTION,
    TASK_FIRST_TURN_TRIAGE,
    TASK_PLANNING_SYNTHESIS,
    TASK_ROUTE_COMPARISON,
    TASK_MAJOR_REVISION,
    TASK_POLICY_PREPARATION,
    TASK_RESEARCH_TOOL_PASS,
    TASK_FINAL_SUMMARY,
)

_BASE_EFFORT_BY_TASK: Final[dict[str, str]] = {
    TASK_QUICK_ACKNOWLEDGEMENT: EFFORT_FAST,
    TASK_NOTE_CAPTURE: EFFORT_FAST,
    TASK_FOCUS_SWITCH: EFFORT_FAST,
    TASK_CLARIFYING_QUESTION: EFFORT_STANDARD,
    TASK_FIRST_TURN_TRIAGE: EFFORT_STANDARD,
    TASK_PLANNING_SYNTHESIS: EFFORT_DEEP,
    TASK_ROUTE_COMPARISON: EFFORT_DEEP,
    TASK_MAJOR_REVISION: EFFORT_DEEP,
    TASK_POLICY_PREPARATION: EFFORT_DEEP,
    TASK_RESEARCH_TOOL_PASS: EFFORT_DEEP,
    TASK_FINAL_SUMMARY: EFFORT_DEEP,
}

_ACK_PATTERN = re.compile(
    r"^(?:thanks|thank you|thx|ok|okay|got it|sounds good|great|perfect)[.! ]*$"
)
_NOTE_PATTERN = re.compile(
    r"\b(?:remember (?:this|that)|save this|note this|remind me|jot (?:that|this) down)\b"
)
_FOCUS_PATTERN = re.compile(
    r"\b(?:working on|focus(?:ing)? on|switch(?:ed)? to|let's switch to|moving on to)\s+"
    r"(?:route|lodging|activities|budget|documents|policy)\b"
)
_FINAL_SUMMARY_PATTERN = re.compile(
    r"\b(?:final summary|wrap (?:this|the trip) up|trip summary|"
    r"finalize the (?:plan|itinerary)|close out the trip)\b"
)
_MAJOR_REVISION_PATTERN = re.compile(
    r"\b(?:start over|rebuild the (?:plan|itinerary)|major (?:revision|change)|"
    r"overhaul|scrap (?:this|the plan)|redo the plan)\b"
)
_POLICY_PREP_PATTERN = re.compile(
    r"\b(?:policy (?:submission|approval|packet)|prepare (?:the )?(?:policy|approval)|"
    r"business approval (?:packet|prep))\b"
)
_RESEARCH_PATTERN = re.compile(
    r"\b(?:look up|search for|find sources|pull provider data|provider lookup|"
    r"research (?:flights?|hotels?|restaurants?|the route))\b"
)
_DEEP_REQUEST_PATTERN = re.compile(
    r"\b(?:think this through|deeper (?:look|review)|deep dive|reason carefully|"
    r"take your time on this)\b"
)
_CLARIFYING_PATTERN = re.compile(
    r"\b(?:could you clarify|what do you mean|can you explain|" r"i'?m not sure what you mean)\b"
)


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """The result of routing one planner turn.

    ``base_effort_class`` is the effort the task class alone implies;
    ``effort_class`` is the final effort after applying any planning-mode
    bias. ``fallback_reason`` is reported separately from ``effort_class``
    so callers can see the model selection without losing the deterministic
    fallback rationale when no provider is configured.
    """

    task_class: str
    base_effort_class: str
    effort_class: str
    planning_mode: str | None
    provider_state: str
    fallback_reason: str | None
    reasoning: str

    def to_payload(self) -> dict[str, str | None]:
        return {
            "task_class": self.task_class,
            "base_effort_class": self.base_effort_class,
            "effort_class": self.effort_class,
            "selected_planning_mode": self.planning_mode,
            "provider_state": self.provider_state,
            "fallback_reason": self.fallback_reason,
            "reasoning": self.reasoning,
        }


def classify_task_class(message: str, *, base_task_class: str) -> str:
    """Refine the maturity-derived base task class with explicit lexical markers.

    Returns one of :data:`TASK_CLASSES`. The base task class — provided by
    the existing turn-metadata heuristic — is preserved when no explicit
    marker is found, so existing message-shape behavior is unchanged for
    messages that do not match an explicit pattern.
    """

    lowered = message.lower().strip()
    if not lowered:
        return base_task_class
    if _ACK_PATTERN.search(lowered):
        return TASK_QUICK_ACKNOWLEDGEMENT
    if _NOTE_PATTERN.search(lowered):
        return TASK_NOTE_CAPTURE
    if _FOCUS_PATTERN.search(lowered):
        return TASK_FOCUS_SWITCH
    if _FINAL_SUMMARY_PATTERN.search(lowered):
        return TASK_FINAL_SUMMARY
    if _MAJOR_REVISION_PATTERN.search(lowered):
        return TASK_MAJOR_REVISION
    if _POLICY_PREP_PATTERN.search(lowered):
        return TASK_POLICY_PREPARATION
    if _RESEARCH_PATTERN.search(lowered):
        return TASK_RESEARCH_TOOL_PASS
    if _DEEP_REQUEST_PATTERN.search(lowered):
        if base_task_class in {TASK_FIRST_TURN_TRIAGE, TASK_CLARIFYING_QUESTION}:
            return TASK_PLANNING_SYNTHESIS
        return base_task_class
    if _CLARIFYING_PATTERN.search(lowered) and base_task_class != TASK_PLANNING_SYNTHESIS:
        return TASK_CLARIFYING_QUESTION
    return base_task_class


def base_effort_for(task_class: str) -> str:
    """Return the unbiased effort class implied by ``task_class``."""

    return _BASE_EFFORT_BY_TASK.get(task_class, EFFORT_STANDARD)


def apply_planning_mode(
    effort: str,
    *,
    planning_mode: str | None,
    task_class: str,
) -> tuple[str, str]:
    """Bias the effort by planning mode without overriding explicit fast/deep.

    Returns ``(effort_class, reasoning)``. Deep stays deep regardless of mode
    (planning mode must not override explicit high-effort tasks). Fast stays
    fast (quick acknowledgements / note capture / focus switches do not need
    deep synthesis). Only the ``standard`` band is adjusted.
    """

    if effort == EFFORT_DEEP:
        return EFFORT_DEEP, f"task_class_{task_class}_pins_deep"
    if effort == EFFORT_FAST:
        return EFFORT_FAST, f"task_class_{task_class}_pins_fast"
    if planning_mode == "delegated":
        return EFFORT_DEEP, "delegated_mode_prefers_autonomous_synthesis"
    if planning_mode == "in-trip":
        return EFFORT_FAST, "in_trip_mode_prefers_quick_response"
    if planning_mode == "collaborative":
        return EFFORT_STANDARD, "collaborative_mode_prefers_clarification"
    return effort, "default_standard"


def route_planner_turn(
    *,
    message: str,
    base_task_class: str,
    planning_mode: str | None,
    provider_state: str,
    fallback_reason: str | None,
) -> RoutingDecision:
    """Classify one planner turn into a task class and model effort class.

    ``provider_state`` is ``"model"`` when a provider is configured and
    ``"fallback"`` when the deterministic fallback runtime is selected.
    ``fallback_reason`` (e.g. ``planner_model_not_configured``) is recorded
    on the decision so diagnostics distinguish "no provider" from a chosen
    effort class.
    """

    refined = classify_task_class(message, base_task_class=base_task_class)
    base_effort = base_effort_for(refined)
    final_effort, reasoning = apply_planning_mode(
        base_effort,
        planning_mode=planning_mode,
        task_class=refined,
    )
    return RoutingDecision(
        task_class=refined,
        base_effort_class=base_effort,
        effort_class=final_effort,
        planning_mode=planning_mode,
        provider_state=provider_state,
        fallback_reason=fallback_reason,
        reasoning=reasoning,
    )
