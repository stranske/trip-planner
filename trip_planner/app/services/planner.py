"""Trip-scoped planner conversation services."""

from __future__ import annotations

import json
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from trip_planner.app.services.auth import AuthenticatedUser
from trip_planner.app.services.planner_memory import (
    build_planner_memory_payload,
    ensure_planner_memory_persisted,
    refresh_planner_memory,
)
from trip_planner.app.services.planner_runtime_config import (
    PlannerRuntimeConfig,
    get_planner_runtime_config,
)
from trip_planner.app.services.planner_tools import (
    execute_planner_tool_call,
    list_planner_tools,
)
from trip_planner.preferences.autonomy import AutonomyGuardrails
from trip_planner.app.services.workspace import (
    WORKSPACE_ACTIVITY_LOG_LIMIT,
    _add_planning_ledger_entry,
    _append_activity_event,
    _get_or_create_workspace_session_record,
    _get_owned_trip_record,
    _isoformat,
    _record_planner_action,
    _serialize_activity_record,
    _serialize_session_record,
    get_workspace_payload,
)
from trip_planner.persistence.models.activity import (
    PersistedActivityLogEvent,
    PersistedPlannerAction,
)
from trip_planner.state.sessions import PlanningSessionState


class WorkspacePlannerTripNotFoundError(ValueError):
    """Raised when the planner conversation targets an unknown trip."""


@dataclass(frozen=True, slots=True)
class PlannerConversationRequest:
    trip_id: str
    message: str
    planner_panel_state: dict[str, Any]
    session: PlanningSessionState
    runtime_context: dict[str, Any]


@dataclass(frozen=True, slots=True)
class PlannerConversationReply:
    content: str
    refs: list[str]
    tool_calls: list[dict[str, Any]]
    requested_tool_calls: list[dict[str, Any]] | None = None
    structured_blocks: list[dict[str, Any]] | None = None
    turn_metadata: dict[str, Any] | None = None


class PlannerChatModel(Protocol):
    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return planner content and optional tool call requests."""


PlannerChatModelFactory = Callable[[PlannerRuntimeConfig], PlannerChatModel]

_PLANNER_CHAT_MODEL_FACTORY: PlannerChatModelFactory | None = None
_GROUNDING_TOOL_NAMES: tuple[str, ...] = (
    "read_workspace_state",
    "refresh_inventory",
    "refresh_scenarios",
    "read_budget_state",
    "read_policy_state",
    "read_proposal_state",
)

_DATE_MARKERS = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
    "weekend",
    "week",
    "days",
    "nights",
)
_CONSTRAINT_MARKERS = (
    "budget",
    "hotel",
    "flight",
    "train",
    "museum",
    "food",
    "kids",
    "family",
    "business",
    "approval",
    "accessible",
    "walking",
    "transfer",
)
_SYNTHESIS_MARKERS = (
    "compare",
    "option",
    "route",
    "itinerary",
    "plan",
    "summary",
    "decide",
)
_PREFERENCE_MARKERS = (
    "prefer",
    "want",
    "like",
    "love",
    "avoid",
    "interested",
    "priority",
    "important",
    "pace",
    "quiet",
    "scenic",
    "food",
    "museum",
    "nature",
)
_UNCERTAINTY_MARKERS = (
    "maybe",
    "not sure",
    "unsure",
    "could",
    "might",
    "probably",
    "possibly",
    "depends",
    "?",
)
_NOTE_MARKERS = (
    "also",
    "note",
    "remember",
    "remind",
    "later",
    "future",
    "unrelated",
    "parking",
    "passport",
    "visa",
)
_NON_DESTINATION_CAPITALIZED_TOKENS = {
    "i",
    "i'd",
    "i'll",
    "i'm",
    "we",
    "we'd",
    "we'll",
    "we're",
    "can",
    "could",
    "help",
    "maybe",
    "not",
    "please",
}


def _structured_block(
    *,
    kind: str,
    title: str,
    body: str = "",
    items: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    hidden: bool = False,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "title": title,
        "body": body,
        "items": list(items or []),
        "metadata": dict(metadata or {}),
        "hidden": hidden,
    }


def _looks_like_destination_token(token: str, index: int) -> bool:
    if not token[:1].isupper():
        return False
    lowered = token.lower()
    if lowered in _DATE_MARKERS:
        return False
    return index > 0 or lowered not in _NON_DESTINATION_CAPITALIZED_TOKENS


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    return [item for item in dict.fromkeys(item.strip() for item in items if item.strip()) if item]


def _split_user_clauses(message: str) -> list[str]:
    clauses = re.split(r"(?:\n+|[.;]|(?:\s+-\s+))", message)
    return [clause.strip(" ,") for clause in clauses if clause.strip(" ,")]


def _extract_destination_mentions(message: str) -> list[str]:
    mentions: list[str] = []
    for match in re.finditer(r"\b[A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*){0,3}\b", message):
        words = match.group(0).split()
        while words and words[0].lower() in _NON_DESTINATION_CAPITALIZED_TOKENS:
            words = words[1:]
        if not words:
            continue
        if any(word.lower() in _DATE_MARKERS for word in words):
            continue
        if any(
            word.lower()
            in _CONSTRAINT_MARKERS + _PREFERENCE_MARKERS + _UNCERTAINTY_MARKERS + _NOTE_MARKERS
            for word in words
        ):
            continue
        mentions.append(" ".join(words))
    return _dedupe_preserve_order(mentions)


def _extract_date_mentions(message: str) -> list[str]:
    lowered = message.lower()
    date_mentions = [
        marker
        for marker in _DATE_MARKERS
        if re.search(rf"\b{re.escape(marker)}\b", lowered)
        and marker not in {"days", "nights", "week"}
    ]
    date_mentions.extend(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", message))
    date_mentions.extend(re.findall(r"\b\d+\s+(?:days|nights|weeks)\b", lowered))
    return _dedupe_preserve_order(date_mentions)


def _matching_clauses(message: str, markers: tuple[str, ...]) -> list[str]:
    matches: list[str] = []
    for clause in _split_user_clauses(message):
        lowered = clause.lower()
        if any(marker in lowered for marker in markers):
            matches.append(clause)
    return _dedupe_preserve_order(matches)


def _should_summarize_traveler_message(message: str, summary: dict[str, list[str]]) -> bool:
    signal_count = sum(len(items) for items in summary.values())
    return len(message.split()) >= 28 or "\n" in message or ";" in message or signal_count >= 4


def _traveler_input_summary_blocks(message: str) -> list[dict[str, Any]]:
    summary = {
        "destinations": _extract_destination_mentions(message),
        "dates": _extract_date_mentions(message),
        "constraints": _matching_clauses(message, _CONSTRAINT_MARKERS),
        "preferences": _matching_clauses(message, _PREFERENCE_MARKERS),
        "uncertainties": _matching_clauses(message, _UNCERTAINTY_MARKERS),
        "notebook_notes": _matching_clauses(message, _NOTE_MARKERS),
    }
    if not _should_summarize_traveler_message(message, summary):
        return []

    items: list[str] = []
    labels = {
        "destinations": "Destinations",
        "dates": "Timing",
        "constraints": "Constraints",
        "preferences": "Preferences",
        "uncertainties": "Open questions",
        "notebook_notes": "Notes to remember",
    }
    for key, label in labels.items():
        values = summary[key]
        if values:
            items.append(f"{label}: {', '.join(values[:3])}")

    return [
        _structured_block(
            kind="traveler_input_summary",
            title="Traveler input summary",
            body="Key details pulled out of the message so the next planner turn can keep them in view.",
            items=items,
            metadata=summary,
        )
    ]


def _record_traveler_message_ledger_entries(
    db_session: Session,
    *,
    trip_id: str,
    session_state_id: str,
    message: str,
    activity_event_id: str,
    structured_blocks: list[dict[str, Any]],
) -> None:
    lowered = message.lower()
    metadata = (
        structured_blocks[0].get("metadata", {})
        if structured_blocks
        and structured_blocks[0].get("kind") == "traveler_input_summary"
        else {}
    )
    for constraint in list(metadata.get("constraints") or [])[:3]:
        _add_planning_ledger_entry(
            db_session,
            trip_id=trip_id,
            session_state_id=session_state_id,
            item_type="constraint",
            summary=str(constraint),
            source_refs=[activity_event_id],
            metadata={"source": "planner_turn"},
        )
    for question in list(metadata.get("uncertainties") or [])[:3]:
        _add_planning_ledger_entry(
            db_session,
            trip_id=trip_id,
            session_state_id=session_state_id,
            item_type="open_question",
            summary=str(question),
            source_refs=[activity_event_id],
            metadata={"source": "planner_turn"},
        )
    for note in list(metadata.get("notebook_notes") or [])[:3]:
        _add_planning_ledger_entry(
            db_session,
            trip_id=trip_id,
            session_state_id=session_state_id,
            item_type="assumption",
            summary=str(note),
            source_refs=[activity_event_id],
            metadata={"source": "planner_turn"},
        )
    if "decide" in lowered or "decision" in lowered:
        _add_planning_ledger_entry(
            db_session,
            trip_id=trip_id,
            session_state_id=session_state_id,
            item_type="decision",
            summary=_first_sentence(message)[:280],
            source_refs=[activity_event_id],
            metadata={"source": "planner_turn"},
        )
    if "source" in lowered or "link" in lowered or "reference" in lowered:
        _add_planning_ledger_entry(
            db_session,
            trip_id=trip_id,
            session_state_id=session_state_id,
            item_type="source_reference",
            summary=_first_sentence(message)[:280],
            source_refs=[activity_event_id],
            metadata={"source": "planner_turn"},
        )


def _planner_turn_metadata(
    *,
    message: str,
    runtime_config: PlannerRuntimeConfig,
    turn_index: int,
) -> dict[str, Any]:
    lowered = message.lower()
    raw_tokens = [token.strip(".,!?;:()[]{}\"'") for token in message.split()]
    tokens = [token.lower() for token in raw_tokens]
    destination_hits = sum(
        1 for index, token in enumerate(raw_tokens) if _looks_like_destination_token(token, index)
    )
    date_hits = sum(1 for marker in _DATE_MARKERS if marker in tokens)
    constraint_hits = sum(1 for marker in _CONSTRAINT_MARKERS if marker in lowered)
    synthesis_hits = sum(1 for marker in _SYNTHESIS_MARKERS if marker in lowered)
    question_hits = lowered.count("?")

    if lowered in {"help", "plan a trip", "vacation ideas"}:
        plan_maturity = "open_ended"
        task_class = "first_turn_triage"
        blocks = [
            {
                "kind": "guidance",
                "title": "Start with a direction",
                "items": [
                    "Choose a destination or region.",
                    "Add timing, trip length, and traveler constraints.",
                    "Name one priority such as food, pace, budget, or business approval.",
                ],
            },
            {
                "kind": "clarifying_questions",
                "title": "Quick questions",
                "items": [
                    "Where are you considering going?",
                    "When would you like to travel?",
                    "What would make this trip feel successful?",
                ],
            },
        ]
    elif constraint_hits >= 5 or question_hits >= 3 or len(tokens) >= 45:
        plan_maturity = "overloaded_constraints"
        task_class = "planning_synthesis"
        blocks = [
            {
                "kind": "summary",
                "title": "Organize the constraints",
                "items": [
                    "Group timing, budget, traveler needs, and approval constraints before generating routes.",
                    "Separate firm requirements from preferences so tradeoffs are visible.",
                ],
            },
            {
                "kind": "next_steps",
                "title": "Next planning moves",
                "items": [
                    "Confirm must-haves.",
                    "Rank the top tradeoff areas.",
                    "Generate fewer, clearer options after the constraints are sorted.",
                ],
            },
        ]
    elif destination_hits >= 1 and date_hits >= 1 and constraint_hits >= 1:
        plan_maturity = "coherent_plan"
        task_class = "route_comparison" if synthesis_hits else "planning_synthesis"
        blocks = [
            {
                "kind": "summary",
                "title": "Understood plan",
                "items": [
                    "You have enough destination, timing, and constraint detail to start shaping options.",
                    "The next turn can compare routes, pace, stays, or approval needs instead of restarting intake.",
                ],
            },
            {
                "kind": "next_steps",
                "title": "Next planning moves",
                "items": [
                    "Confirm the most important tradeoff.",
                    "Compare a small set of route or stay options.",
                    "Preserve open decisions for the workspace checklist.",
                ],
            },
        ]
    else:
        plan_maturity = "partial_plan"
        task_class = "first_turn_triage"
        blocks = [
            {
                "kind": "summary",
                "title": "Partial plan",
                "items": [
                    "There is enough context to continue, but a few planning decisions are still missing.",
                    "Targeted questions should close the largest gaps before deeper synthesis.",
                ],
            },
            {
                "kind": "clarifying_questions",
                "title": "Targeted questions",
                "items": [
                    "What dates or trip length should the planner assume?",
                    "Which tradeoff matters most: budget, pace, lodging, route, or approvals?",
                ],
            },
        ]

    return {
        "plan_maturity": plan_maturity,
        "task_class": task_class,
        "visible_response_blocks": blocks,
        "debug_routing_details": {
            "runtime_mode": runtime_config.mode,
            "runtime_provider": runtime_config.provider,
            "runtime_model": runtime_config.model,
            "turn_index": turn_index,
            "signals": {
                "token_count": len(tokens),
                "date_hits": date_hits,
                "constraint_hits": constraint_hits,
                "synthesis_hits": synthesis_hits,
                "question_hits": question_hits,
            },
        },
    }


def _fallback_content_from_metadata(
    *,
    trip_title: str,
    message: str,
    metadata: dict[str, Any],
) -> str:
    maturity = metadata["plan_maturity"]
    if maturity == "coherent_plan":
        return (
            f"I can use the details you gave for {trip_title} to move into option shaping. "
            "The next useful step is to compare a small set of routes, stays, or pacing tradeoffs "
            "instead of asking broad intake questions again."
        )
    if maturity == "open_ended":
        return (
            f"Let's narrow {trip_title} before building options. Share a destination or region, "
            "rough timing, and one priority, and I will turn it into a focused planning path."
        )
    if maturity == "overloaded_constraints":
        return (
            f"I will organize the constraints for {trip_title} before generating options. "
            "First I would separate firm requirements from preferences, then compare only the "
            "routes or stays that satisfy the must-haves."
        )
    return (
        f"{trip_title} has a useful starting point. I would close the biggest missing decision "
        "from your note, then move into targeted planning."
    )


def _first_sentence(content: str) -> str:
    sentence = re.split(r"(?<=[.!?])\s+", content.strip(), maxsplit=1)[0].strip()
    return sentence or content.strip()


def _visible_block_items(
    metadata: dict[str, Any],
    *,
    kinds: set[str],
) -> list[str]:
    items: list[str] = []
    for block in list(metadata.get("visible_response_blocks") or []):
        if str(block.get("kind") or "") in kinds:
            items.extend(str(item) for item in list(block.get("items") or []))
    return _dedupe_preserve_order(items)


def _planner_response_structured_blocks(
    *,
    content: str,
    metadata: dict[str, Any],
    panel: dict[str, Any],
    runtime_context: dict[str, Any],
    tool_calls: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    decisions = list(panel.get("pending_decisions") or [])
    options = list((panel.get("option_set") or {}).get("options") or [])
    next_step_actions = list(panel.get("next_step_actions") or [])
    runtime_comparison = runtime_context.get("runtime_scenario_comparison") or {}
    scenarios = list(runtime_comparison.get("scenarios") or [])
    planning_ledger = runtime_context.get("planning_ledger") or {}
    ledger_summary = planning_ledger.get("summary") or {}

    summary_items = _visible_block_items(metadata, kinds={"summary", "guidance"})
    blocks.append(
        _structured_block(
            kind="summary",
            title="Planner summary",
            body=_first_sentence(content),
            items=summary_items[:3],
        )
    )

    question_items = _visible_block_items(
        metadata,
        kinds={"clarifying_questions", "question", "questions"},
    )
    if decisions:
        active_decision = decisions[0]
        question_items.insert(
            0, str(active_decision.get("prompt") or active_decision.get("title") or "")
        )
    if question_items:
        blocks.append(
            _structured_block(
                kind="question",
                title="Questions to settle",
                items=_dedupe_preserve_order(question_items)[:4],
            )
        )

    ledger_items: list[str] = []
    ledger_entry_ids: list[str] = []
    for label, key in (
        ("Decision", "active_decisions"),
        ("Open question", "open_questions"),
        ("Option in view", "active_options"),
        ("Rejected option", "rejected_options"),
        ("Constraint", "constraints"),
        ("Assumption", "assumptions"),
        ("Source", "source_references"),
    ):
        for entry in list(ledger_summary.get(key) or [])[:2]:
            summary = str(entry.get("summary") or "").strip()
            if not summary:
                continue
            ledger_items.append(f"{label}: {summary}")
            ledger_entry_ids.append(str(entry.get("ledger_entry_id") or ""))
    if ledger_items:
        blocks.append(
            _structured_block(
                kind="planning_ledger",
                title="Planning memory",
                items=_dedupe_preserve_order(ledger_items)[:6],
                metadata={
                    "ledger_entry_ids": [
                        item for item in _dedupe_preserve_order(ledger_entry_ids) if item
                    ][:6]
                },
            )
        )

    if decisions:
        decision_items: list[str] = []
        for decision in decisions[:3]:
            prompt = str(decision.get("prompt") or decision.get("title") or "")
            choices = ", ".join(str(choice) for choice in list(decision.get("choices") or []))
            decision_items.append(f"{prompt} Choices: {choices}" if choices else prompt)
        blocks.append(
            _structured_block(
                kind="decision",
                title="Open decisions",
                items=_dedupe_preserve_order(decision_items),
                metadata={"decision_ids": [item.get("decision_id") for item in decisions[:3]]},
            )
        )

    if options:
        option_items = [
            f"{option.get('label')}: {option.get('summary')}"
            for option in options[:4]
            if option.get("label") or option.get("summary")
        ]
        blocks.append(
            _structured_block(
                kind="route_option",
                title="Route options in view",
                items=_dedupe_preserve_order(option_items),
                metadata={"option_ids": [item.get("option_id") for item in options[:4]]},
            )
        )

    comparison_items: list[str] = []
    if len(scenarios) > 1:
        for scenario in scenarios[:4]:
            metrics = scenario.get("metrics") or {}
            route_summary = scenario.get("route_summary") or "route details pending"
            comparison_items.append(
                (
                    f"{scenario.get('title')}: {route_summary}; "
                    f"{metrics.get('travel_minutes', 'pending')} travel minutes; "
                    f"{metrics.get('transfers', 'pending')} transfers."
                )
            )
    elif len(options) > 1:
        comparison_items = [
            f"{option.get('label')}: {option.get('summary')}"
            for option in options[:4]
            if option.get("label") or option.get("summary")
        ]
    if comparison_items:
        blocks.append(
            _structured_block(
                kind="comparison",
                title="Comparison frame",
                items=_dedupe_preserve_order(comparison_items),
            )
        )

    assumption_items = [
        f"Planning maturity: {str(metadata.get('plan_maturity') or '').replace('_', ' ')}",
        f"Current work type: {str(metadata.get('task_class') or '').replace('_', ' ')}",
    ]
    context_readiness = runtime_context.get("context_readiness") or {}
    missing_sections = list(context_readiness.get("missing_sections") or [])
    if missing_sections:
        assumption_items.append(f"Missing workspace context: {', '.join(missing_sections)}")
    blocks.append(
        _structured_block(
            kind="assumption",
            title="Working assumptions",
            items=_dedupe_preserve_order([item for item in assumption_items if item.strip(": ")]),
        )
    )

    next_action_items = _visible_block_items(metadata, kinds={"next_steps", "next_action"})
    next_action_items.extend(
        str(action.get("description") or action.get("label") or "")
        for action in next_step_actions[:3]
    )
    if next_action_items:
        blocks.append(
            _structured_block(
                kind="next_action",
                title="Next actions",
                items=_dedupe_preserve_order(next_action_items)[:4],
            )
        )

    return blocks


def _ensure_top_level_planner_blocks(
    *,
    blocks: list[dict[str, Any]],
    metadata: dict[str, Any],
    tool_calls: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized_blocks = [
        block
        for block in blocks
        if str(block.get("kind") or "") not in {"visible_sections", "diagnostic", "debug"}
    ]
    visible_blocks = [block for block in normalized_blocks if not bool(block.get("hidden"))]
    hidden_blocks = [block for block in normalized_blocks if bool(block.get("hidden"))]

    section_items: list[str] = []
    for block in visible_blocks:
        title = str(block.get("title") or block.get("kind") or "").strip()
        body = str(block.get("body") or "").strip()
        first_item = str((block.get("items") or [""])[0]).strip()
        summary = body or first_item
        section_items.append(f"{title}: {summary}" if summary else title)

    section_block = _structured_block(
        kind="visible_sections",
        title="Planner response sections",
        body="Traveler-visible planning sections for this reply.",
        items=_dedupe_preserve_order(section_items)[:6],
        metadata={
            "section_kinds": [str(block.get("kind") or "") for block in visible_blocks],
            "section_count": len(visible_blocks),
        },
    )

    diagnostic_block = _structured_block(
        kind="diagnostic",
        title="Planner diagnostics",
        body="Routing details and tool traces are hidden from the normal traveler view.",
        metadata={
            "routing": metadata.get("debug_routing_details") or {},
            "tool_call_count": len(tool_calls),
            "tool_names": [item.get("tool_name") for item in tool_calls],
            "hidden_block_kinds": [str(block.get("kind") or "") for block in hidden_blocks],
        },
        hidden=True,
    )
    return [section_block, *visible_blocks, *hidden_blocks, diagnostic_block]


def set_planner_chat_model_factory_for_tests(
    factory: PlannerChatModelFactory | None,
) -> None:
    global _PLANNER_CHAT_MODEL_FACTORY
    _PLANNER_CHAT_MODEL_FACTORY = factory


class PlannerConversationRunnable(Protocol):
    """LangChain-style runnable abstraction for planner conversation turns."""

    def invoke(self, request: PlannerConversationRequest) -> PlannerConversationReply:
        """Return one planner response for the provided turn."""


class DeterministicPlannerConversationRunnable:
    """Provider-neutral fallback when planner model configuration is absent."""

    def invoke(self, request: PlannerConversationRequest) -> PlannerConversationReply:
        panel = request.planner_panel_state
        trip = panel["trip"]
        metadata = _planner_turn_metadata(
            message=request.message,
            runtime_config=get_planner_runtime_config(),
            turn_index=len(request.runtime_context.get("recent_activity") or []),
        )
        outputs = list(panel.get("outputs") or [])
        decisions = list(panel.get("pending_decisions") or [])
        options = list((panel.get("option_set") or {}).get("options") or [])
        ledger_summary = (
            (request.runtime_context.get("planning_ledger") or {}).get("summary") or {}
        )

        lines = [
            _fallback_content_from_metadata(
                trip_title=trip["title"],
                message=request.message,
                metadata=metadata,
            )
        ]
        refs = [request.session.session_state_id]

        if decisions:
            active = decisions[0]
            choice_labels = ", ".join(active.get("choices") or [])
            lines.append(f"Current blocking decision: {active['prompt']} Choices: {choice_labels}.")
            refs.append(active["decision_id"])
        elif options:
            lead = options[0]
            lines.append(f"Current lead option: {lead['label']}. {lead['summary']}")
            if len(options) > 1:
                lines.append(f"Alternative to compare next: {options[1]['label']}.")
            refs.append(lead["option_id"])
        else:
            lines.append(
                "No ranked planner options exist yet, so the session should stay focused on refining trip scope."
            )

        if outputs:
            latest_titles = ", ".join(output["title"] for output in outputs[:2])
            lines.append(f"Latest workspace signals: {latest_titles}.")
            refs.extend(output["output_id"] for output in outputs[:2])

        ledger_focus: list[str] = []
        for label, key in (
            ("decision", "active_decisions"),
            ("open question", "open_questions"),
            ("option in view", "active_options"),
            ("rejected option", "rejected_options"),
            ("constraint", "constraints"),
            ("assumption", "assumptions"),
        ):
            entries = list(ledger_summary.get(key) or [])
            if not entries:
                continue
            first = entries[0]
            summary = str(first.get("summary") or "").strip()
            if not summary:
                continue
            ledger_focus.append(f"{label}: {summary}")
            refs.append(str(first.get("ledger_entry_id") or ""))
        if ledger_focus:
            lines.append(
                "Planning ledger remembers "
                + "; ".join(_dedupe_preserve_order(ledger_focus)[:3])
                + "."
            )

        deduped_refs = list(dict.fromkeys(refs))
        return PlannerConversationReply(
            content=" ".join(lines),
            refs=deduped_refs,
            tool_calls=[],
            turn_metadata=metadata,
        )


class _OpenAIPlannerChatModel:
    def __init__(self, config: PlannerRuntimeConfig) -> None:
        if not config.model:
            raise ValueError("Planner model name is required.")
        from langchain_openai import ChatOpenAI

        self._model = ChatOpenAI(model=config.model, temperature=0)

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": tool["tool_name"],
                    "description": tool["description"],
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": True,
                    },
                },
            }
            for tool in payload["available_tools"]
        ]
        model = self._model.bind_tools(tools)
        response = model.invoke(
            [
                (
                    "system",
                    "You are a trip-scoped planner. Use only the listed app tools for "
                    "workspace, inventory, scenario, budget, policy, or proposal facts. "
                    "Do not invent persisted state.",
                ),
                (
                    "human",
                    json.dumps(
                        {
                            "message": payload["message"],
                            "context": payload["runtime_context"],
                        },
                        default=str,
                    ),
                ),
            ]
        )
        tool_calls: list[dict[str, Any]] = []
        for call in getattr(response, "tool_calls", []) or []:
            tool_calls.append(
                {
                    "tool_name": call.get("name") or call.get("tool_name") or "",
                    "arguments": call.get("args") or call.get("arguments") or {},
                }
            )
        return {"content": str(response.content), "tool_calls": tool_calls}


class ModelBackedPlannerConversationRunnable:
    def __init__(self, config: PlannerRuntimeConfig, chat_model: PlannerChatModel) -> None:
        self._config = config
        self._chat_model = chat_model

    def invoke(self, request: PlannerConversationRequest) -> PlannerConversationReply:
        raw = self._chat_model.invoke(
            {
                "message": request.message,
                "trip_id": request.trip_id,
                "available_tools": list_planner_tools(),
                "runtime_context": request.runtime_context,
                "provider": self._config.provider,
                "model": self._config.model,
            }
        )
        content = str(raw.get("content") or "").strip()
        if not content:
            content = (
                "Planner model returned an empty response after reading the current trip context."
            )
        requested_tool_calls = [
            {
                "tool_name": str(item.get("tool_name") or item.get("name") or ""),
                "arguments": item.get("arguments") or item.get("args") or {},
            }
            for item in list(raw.get("tool_calls") or [])
        ]
        return PlannerConversationReply(
            content=content,
            refs=[request.session.session_state_id],
            tool_calls=[],
            requested_tool_calls=requested_tool_calls,
            turn_metadata=_planner_turn_metadata(
                message=request.message,
                runtime_config=self._config,
                turn_index=len(request.runtime_context.get("recent_activity") or []),
            ),
        )


def _planner_runnable(config: PlannerRuntimeConfig) -> PlannerConversationRunnable:
    if config.mode != "model":
        return DeterministicPlannerConversationRunnable()
    factory = _PLANNER_CHAT_MODEL_FACTORY or (
        lambda runtime_config: _OpenAIPlannerChatModel(runtime_config)
    )
    return ModelBackedPlannerConversationRunnable(config, factory(config))


def _conversation_id(trip_id: str) -> str:
    return f"planner-conversation:{trip_id}"


def _message_payload(
    *,
    message_id: str,
    role: str,
    content: str,
    created_at: str,
    refs: list[str] | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
    structured_blocks: list[dict[str, Any]] | None = None,
    turn_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "message_id": message_id,
        "role": role,
        "content": content,
        "created_at": created_at,
        "refs": list(refs or []),
        "tool_calls": list(tool_calls or []),
        "structured_blocks": list(structured_blocks or []),
        "turn_metadata": turn_metadata,
    }


def _conversation_messages(
    db_session: Session,
    *,
    session_state_id: str,
) -> list[dict[str, Any]]:
    records = db_session.scalars(
        select(PersistedPlannerAction)
        .where(PersistedPlannerAction.session_state_id == session_state_id)
        .where(PersistedPlannerAction.action_type.in_(["planner_user_turn", "planner_response"]))
        .order_by(
            PersistedPlannerAction.created_at.asc(),
            PersistedPlannerAction.planner_action_id.asc(),
        )
    ).all()
    messages: list[dict[str, Any]] = []
    for record in records:
        role = record.payload.get("role") or (
            "user" if record.action_type == "planner_user_turn" else "planner"
        )
        raw_refs = record.payload.get("refs", "")
        refs = [item for item in raw_refs.split(",") if item]
        tool_calls = list(record.payload.get("tool_calls") or [])
        structured_blocks = list(record.payload.get("structured_blocks") or [])
        turn_metadata = record.payload.get("turn_metadata")
        if not isinstance(turn_metadata, dict):
            turn_metadata = None
        messages.append(
            _message_payload(
                message_id=record.planner_action_id,
                role=role,
                content=record.payload.get("content", ""),
                created_at=record.occurred_at,
                refs=refs,
                tool_calls=tool_calls,
                structured_blocks=structured_blocks,
                turn_metadata=turn_metadata,
            )
        )
    return messages


def _activity_log(
    db_session: Session,
    *,
    trip_id: str,
) -> list[dict[str, Any]]:
    records = db_session.scalars(
        select(PersistedActivityLogEvent)
        .where(PersistedActivityLogEvent.trip_id == trip_id)
        .order_by(PersistedActivityLogEvent.occurred_at.desc())
        .limit(WORKSPACE_ACTIVITY_LOG_LIMIT)
    ).all()
    return [_serialize_activity_record(record) for record in records]


def _planner_runtime_context(
    workspace_payload: dict[str, Any],
    *,
    session: PlanningSessionState,
    planner_memory: dict[str, Any],
    activity_log: list[dict[str, Any]],
) -> dict[str, Any]:
    panel = workspace_payload["planner_panel_state"]
    required_sections = {
        "inventory_summary": workspace_payload.get("inventory_summary") or {},
        "scenario_search": workspace_payload.get("scenario_search") or {},
        "runtime_scenario_comparison": workspace_payload.get("runtime_scenario_comparison") or {},
        "budget_state": workspace_payload.get("budget_state") or {},
        "planner_memory": planner_memory,
    }
    planning_ledger = workspace_payload.get("planning_ledger") or {}
    missing_sections = [key for key, value in required_sections.items() if not value]
    return {
        "trip": panel["trip"],
        "pending_decisions": panel.get("pending_decisions") or [],
        "option_set": panel.get("option_set") or {},
        "outputs": panel.get("outputs") or [],
        "planning_ledger": planning_ledger,
        **required_sections,
        "policy_state": workspace_payload.get("policy_state") or {},
        "proposal_state": workspace_payload.get("proposal_state") or {},
        "autonomy_preferences": {
            "interaction_state": session.interaction_state.to_dict(),
            "guardrails": AutonomyGuardrails().to_dict(),
            "planner_behavior": panel.get("planner_behavior") or {},
        },
        "recent_activity": activity_log[:8],
        "context_readiness": {
            "status": "partial" if missing_sections else "ready",
            "missing_sections": missing_sections,
        },
    }


def _planner_session_payload(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    resumed_at: str | None = None,
) -> dict[str, Any]:
    workspace_payload = get_workspace_payload(db_session, user=user, trip_id=trip_id)
    if workspace_payload is None:
        raise WorkspacePlannerTripNotFoundError(f"Trip '{trip_id}' was not found.")

    session = workspace_payload["session"]
    session_state_id = session["session_state_id"]
    planner_memory = build_planner_memory_payload(
        db_session,
        trip_id=trip_id,
        session_state_id=session_state_id,
    )
    activity_log = _activity_log(db_session, trip_id=trip_id)
    return {
        "trip_id": trip_id,
        "session_state_id": session_state_id,
        "conversation_id": _conversation_id(trip_id),
        "resumed_at": resumed_at,
        "runtime": get_planner_runtime_config().to_payload(),
        "session": session,
        "planner_panel_state": workspace_payload["planner_panel_state"],
        "planning_ledger": workspace_payload.get("planning_ledger") or {},
        "planner_memory": planner_memory,
        "available_tools": list_planner_tools(),
        "activity_log": activity_log,
        "messages": _conversation_messages(db_session, session_state_id=session_state_id),
    }


def _tool_call_error(tool_name: str, message: str) -> dict[str, Any]:
    return {
        "tool_name": tool_name or "unknown",
        "status": "error",
        "summary": message,
        "mutates_state": False,
        "refs": [],
        "output": {"error": message},
    }


def _planner_model_error_reply(
    *,
    session_state_id: str,
    error: Exception,
) -> PlannerConversationReply:
    message = (
        "Planner model runtime failed before it could complete the turn. "
        "The traveler message was saved, and the visible error state is available for retry."
    )
    return PlannerConversationReply(
        content=f"{message} Error: {error}",
        refs=[session_state_id],
        tool_calls=[_tool_call_error("planner_model", str(error))],
    )


def _execute_model_tool_calls(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    tool_calls: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    executed: list[dict[str, Any]] = []
    for tool_call in tool_calls or []:
        tool_name = str(tool_call.get("tool_name") or "")
        try:
            result = execute_planner_tool_call(
                db_session,
                user=user,
                trip_id=trip_id,
                tool_name=tool_name,
                arguments=tool_call.get("arguments") or {},
            )
        except Exception as error:
            executed.append(_tool_call_error(tool_name, str(error)))
        else:
            executed.append(result.to_dict())
    return executed


def _missing_grounding_tool_calls(
    executed_tool_calls: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    seen = {
        str(item.get("tool_name") or "")
        for item in executed_tool_calls
        if str(item.get("status") or "") == "completed"
    }
    return [
        {"tool_name": tool_name, "arguments": {}}
        for tool_name in _GROUNDING_TOOL_NAMES
        if tool_name not in seen
    ]


def get_planner_session_payload(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
) -> dict[str, Any]:
    try:
        record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    except ValueError as error:
        raise WorkspacePlannerTripNotFoundError(str(error)) from error
    _get_or_create_workspace_session_record(db_session, record=record)
    db_session.commit()
    return _planner_session_payload(db_session, user=user, trip_id=trip_id)


def resume_planner_session_payload(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
) -> dict[str, Any]:
    try:
        record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    except ValueError as error:
        raise WorkspacePlannerTripNotFoundError(str(error)) from error
    session_record = _get_or_create_workspace_session_record(db_session, record=record)
    resumed_at = _isoformat(datetime.now(UTC))
    session_record.last_updated_at = resumed_at
    record.updated_at = datetime.now(UTC)
    ensure_planner_memory_persisted(
        db_session,
        trip_id=trip_id,
        session_state_id=session_record.session_state_id,
        occurred_at=resumed_at,
    )
    db_session.commit()
    return _planner_session_payload(
        db_session,
        user=user,
        trip_id=trip_id,
        resumed_at=resumed_at,
    )


def submit_planner_turn(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    message: str,
    tool_calls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized_message = message.strip()
    if not normalized_message:
        raise ValueError("Planner turn message is required.")

    try:
        record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    except ValueError as error:
        raise WorkspacePlannerTripNotFoundError(str(error)) from error
    session_record = _get_or_create_workspace_session_record(db_session, record=record)
    now = datetime.now(UTC)
    occurred_at = _isoformat(now)
    session = PlanningSessionState.from_dict(_serialize_session_record(session_record))

    session.updated_at = occurred_at
    session.notes.append(f"planner-turn:{occurred_at}")
    session_record.last_updated_at = occurred_at
    session_record.notes = list(session.notes)
    record.updated_at = now
    traveler_structured_blocks = _traveler_input_summary_blocks(normalized_message)

    user_activity_event_id = f"activity:{trip_id}:{secrets.token_hex(4)}"
    _append_activity_event(
        db_session,
        activity_event_id=user_activity_event_id,
        trip_id=trip_id,
        session_state_id=session.session_state_id,
        occurred_at=occurred_at,
        event_kind="planner_message",
        summary="Traveler submitted a planner conversation turn.",
        metadata={
            "message_length": str(len(normalized_message)),
            "structured_block_count": str(len(traveler_structured_blocks)),
        },
    )
    _record_planner_action(
        db_session,
        trip_id=trip_id,
        session_state_id=session.session_state_id,
        activity_event_id=user_activity_event_id,
        occurred_at=occurred_at,
        action_type="planner_user_turn",
        payload={
            "role": "user",
            "content": normalized_message,
            "refs": session.session_state_id,
            "tool_calls": [],
            "structured_blocks": traveler_structured_blocks,
            "selected_planning_mode": session.selected_planning_mode,
        },
    )
    _record_traveler_message_ledger_entries(
        db_session,
        trip_id=trip_id,
        session_state_id=session.session_state_id,
        message=normalized_message,
        activity_event_id=user_activity_event_id,
        structured_blocks=traveler_structured_blocks,
    )

    executed_tool_calls: list[dict[str, Any]] = []
    for tool_call in tool_calls or []:
        result = execute_planner_tool_call(
            db_session,
            user=user,
            trip_id=trip_id,
            tool_name=str(tool_call.get("tool_name") or ""),
            arguments=tool_call.get("arguments") or {},
        )
        executed_tool_calls.append(result.to_dict())

    workspace_payload = get_workspace_payload(db_session, user=user, trip_id=trip_id)
    if workspace_payload is None:
        raise WorkspacePlannerTripNotFoundError(f"Trip '{trip_id}' was not found.")
    session = PlanningSessionState.from_dict(_serialize_session_record(session_record))
    planner_memory = build_planner_memory_payload(
        db_session,
        trip_id=trip_id,
        session_state_id=session.session_state_id,
    )
    activity_log = _activity_log(db_session, trip_id=trip_id)
    runtime_config = get_planner_runtime_config()
    runnable = _planner_runnable(runtime_config)
    runtime_context = _planner_runtime_context(
        workspace_payload,
        session=session,
        planner_memory=planner_memory,
        activity_log=activity_log,
    )
    try:
        reply = runnable.invoke(
            PlannerConversationRequest(
                trip_id=trip_id,
                message=normalized_message,
                planner_panel_state=workspace_payload["planner_panel_state"],
                session=session,
                runtime_context=runtime_context,
            )
        )
    except Exception as error:
        reply = _planner_model_error_reply(
            session_state_id=session.session_state_id,
            error=error,
        )
    if reply.turn_metadata is None:
        reply = PlannerConversationReply(
            content=reply.content,
            refs=reply.refs,
            tool_calls=reply.tool_calls,
            requested_tool_calls=reply.requested_tool_calls,
            structured_blocks=reply.structured_blocks,
            turn_metadata=_planner_turn_metadata(
                message=normalized_message,
                runtime_config=runtime_config,
                turn_index=len(activity_log),
            ),
        )
    model_tool_calls = _execute_model_tool_calls(
        db_session,
        user=user,
        trip_id=trip_id,
        tool_calls=reply.requested_tool_calls,
    )
    executed_tool_calls.extend(model_tool_calls)
    model_runtime_failed = any(
        item.get("tool_name") == "planner_model" and item.get("status") == "error"
        for item in reply.tool_calls
    )
    if runtime_config.mode == "model" and not model_runtime_failed:
        grounding_tool_calls = _missing_grounding_tool_calls(executed_tool_calls)
        if grounding_tool_calls:
            executed_tool_calls.extend(
                _execute_model_tool_calls(
                    db_session,
                    user=user,
                    trip_id=trip_id,
                    tool_calls=grounding_tool_calls,
                )
            )
    if executed_tool_calls:
        reply = PlannerConversationReply(
            content=reply.content,
            refs=list(
                dict.fromkeys(
                    reply.refs + [ref for item in executed_tool_calls for ref in item["refs"]]
                )
            ),
            tool_calls=executed_tool_calls,
            structured_blocks=reply.structured_blocks,
            turn_metadata=reply.turn_metadata,
        )
    if not reply.structured_blocks:
        reply = PlannerConversationReply(
            content=reply.content,
            refs=reply.refs,
            tool_calls=reply.tool_calls,
            requested_tool_calls=reply.requested_tool_calls,
            structured_blocks=_planner_response_structured_blocks(
                content=reply.content,
                metadata=reply.turn_metadata or {},
                panel=workspace_payload["planner_panel_state"],
                runtime_context=runtime_context,
                tool_calls=reply.tool_calls,
            ),
            turn_metadata=reply.turn_metadata,
        )
    reply = PlannerConversationReply(
        content=reply.content,
        refs=reply.refs,
        tool_calls=reply.tool_calls,
        requested_tool_calls=reply.requested_tool_calls,
        structured_blocks=_ensure_top_level_planner_blocks(
            blocks=reply.structured_blocks or [],
            metadata=reply.turn_metadata or {},
            tool_calls=reply.tool_calls,
        ),
        turn_metadata=reply.turn_metadata,
    )

    planner_activity_event_id = f"activity:{trip_id}:{secrets.token_hex(4)}"
    _append_activity_event(
        db_session,
        activity_event_id=planner_activity_event_id,
        trip_id=trip_id,
        session_state_id=session.session_state_id,
        occurred_at=occurred_at,
        event_kind="planner_message",
        summary="Planner conversation service generated the next trip-scoped reply.",
        actor="planner",
        metadata={"ref_count": str(len(reply.refs))},
    )
    _record_planner_action(
        db_session,
        trip_id=trip_id,
        session_state_id=session.session_state_id,
        activity_event_id=planner_activity_event_id,
        occurred_at=occurred_at,
        action_type="planner_response",
        payload={
            "role": "planner",
            "content": reply.content,
            "refs": ",".join(reply.refs),
            "tool_calls": reply.tool_calls,
            "structured_blocks": reply.structured_blocks,
            "turn_metadata": reply.turn_metadata,
            "selected_planning_mode": session.selected_planning_mode,
            "planning_stage": (
                workspace_payload["planner_panel_state"]
                .get("planner_behavior", {})
                .get("trip_stage")
            ),
            "runtime_mode": runtime_config.mode,
            "context_readiness": runtime_context["context_readiness"],
        },
    )
    refresh_planner_memory(
        db_session,
        trip_id=trip_id,
        session_state_id=session.session_state_id,
        occurred_at=occurred_at,
    )

    db_session.commit()
    return _planner_session_payload(db_session, user=user, trip_id=trip_id)
