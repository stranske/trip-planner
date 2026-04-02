"""Persisted planning-session and activity-log contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from trip_planner.contracts._validators import (
    require_non_empty,
    require_optional_non_empty,
    require_string_mapping,
    require_strings,
)
from trip_planner.contracts.trip import TRIP_MODES
from trip_planner.state.accounts import INTERACTION_STYLES, SUMMARY_GRANULARITIES

SESSION_STATE_SCHEMA_VERSION = "0.1.0"
PLANNING_SESSION_STATUSES: tuple[str, ...] = (
    "active",
    "paused",
    "completed",
    "archived",
)
INITIATIVE_LEVELS: tuple[str, ...] = (
    "user_led",
    "balanced",
    "planner_led",
    "planner_first",
)
CHECKPOINT_FREQUENCIES: tuple[str, ...] = (
    "manual",
    "milestone",
    "phase",
    "turn",
)
OPTION_PREVIEW_TIMINGS: tuple[str, ...] = (
    "immediate",
    "early",
    "balanced",
    "deferred",
)
OPTION_PRESENTATION_KINDS: tuple[str, ...] = (
    "ranked_results",
    "scenario_comparison",
    "budget_review",
    "in_trip_update",
)
ACTIVITY_LOG_EVENT_KINDS: tuple[str, ...] = (
    "session_started",
    "checkpoint_created",
    "scenario_saved",
    "rerank_requested",
    "option_rejected",
    "budget_updated",
    "decision_recorded",
    "in_trip_change_requested",
)


def _require_string_list(values: list[str], field_name: str) -> None:
    if isinstance(values, str) or not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list of strings")
    require_strings(values, field_name)


def _require_unique_strings(values: list[str], field_name: str) -> None:
    _require_string_list(values, field_name)
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} cannot contain duplicates")


def _payload_list(
    payload: dict[str, Any], field_name: str, default: list[Any]
) -> list[Any]:
    value = payload.get(field_name, default)
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    return list(value)


@dataclass(slots=True)
class PlanningInteractionState:
    interaction_style: str = "guided"
    initiative_level: str = "balanced"
    checkpoint_frequency: str = "milestone"
    option_preview_timing: str = "balanced"
    summary_granularity: str = "balanced"
    auto_advance_research_passes: int = 1
    ask_before_major_change: bool = True
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.interaction_style not in INTERACTION_STYLES:
            raise ValueError(f"interaction_style must be one of {INTERACTION_STYLES}")
        if self.initiative_level not in INITIATIVE_LEVELS:
            raise ValueError(f"initiative_level must be one of {INITIATIVE_LEVELS}")
        if self.checkpoint_frequency not in CHECKPOINT_FREQUENCIES:
            raise ValueError(
                f"checkpoint_frequency must be one of {CHECKPOINT_FREQUENCIES}"
            )
        if self.option_preview_timing not in OPTION_PREVIEW_TIMINGS:
            raise ValueError(
                f"option_preview_timing must be one of {OPTION_PREVIEW_TIMINGS}"
            )
        if self.summary_granularity not in SUMMARY_GRANULARITIES:
            raise ValueError(
                f"summary_granularity must be one of {SUMMARY_GRANULARITIES}"
            )
        if self.auto_advance_research_passes < 0:
            raise ValueError("auto_advance_research_passes must be non-negative")
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PlanningInteractionState":
        return cls(
            interaction_style=payload.get("interaction_style", "guided"),
            initiative_level=payload.get("initiative_level", "balanced"),
            checkpoint_frequency=payload.get("checkpoint_frequency", "milestone"),
            option_preview_timing=payload.get("option_preview_timing", "balanced"),
            summary_granularity=payload.get("summary_granularity", "balanced"),
            auto_advance_research_passes=payload.get(
                "auto_advance_research_passes",
                1,
            ),
            ask_before_major_change=payload.get("ask_before_major_change", True),
            notes=_payload_list(payload, "notes", []),
        )


@dataclass(slots=True)
class OptionPresentationRecord:
    presentation_id: str
    option_set_id: str
    shown_at: str
    surface_kind: str = "ranked_results"
    surfaced_option_ids: list[str] = field(default_factory=list)
    highlighted_option_id: str | None = None
    selected_option_id: str | None = None
    rejected_option_ids: list[str] = field(default_factory=list)
    summary: str = ""
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.presentation_id, "presentation_id")
        require_non_empty(self.option_set_id, "option_set_id")
        require_non_empty(self.shown_at, "shown_at")
        if self.surface_kind not in OPTION_PRESENTATION_KINDS:
            raise ValueError(
                f"surface_kind must be one of {OPTION_PRESENTATION_KINDS}"
            )
        if not self.surfaced_option_ids:
            raise ValueError("surfaced_option_ids must contain at least one option id")
        _require_unique_strings(self.surfaced_option_ids, "surfaced_option_ids")
        require_optional_non_empty(self.highlighted_option_id, "highlighted_option_id")
        require_optional_non_empty(self.selected_option_id, "selected_option_id")
        _require_unique_strings(self.rejected_option_ids, "rejected_option_ids")
        _require_string_list(self.notes, "notes")
        if (
            self.highlighted_option_id is not None
            and self.highlighted_option_id not in self.surfaced_option_ids
        ):
            raise ValueError("highlighted_option_id must be one of surfaced_option_ids")
        if (
            self.selected_option_id is not None
            and self.selected_option_id not in self.surfaced_option_ids
        ):
            raise ValueError("selected_option_id must be one of surfaced_option_ids")
        if any(
            option_id not in self.surfaced_option_ids
            for option_id in self.rejected_option_ids
        ):
            raise ValueError("rejected_option_ids must be drawn from surfaced options")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "OptionPresentationRecord":
        return cls(
            presentation_id=payload["presentation_id"],
            option_set_id=payload["option_set_id"],
            shown_at=payload["shown_at"],
            surface_kind=payload.get("surface_kind", "ranked_results"),
            surfaced_option_ids=_payload_list(payload, "surfaced_option_ids", []),
            highlighted_option_id=payload.get("highlighted_option_id"),
            selected_option_id=payload.get("selected_option_id"),
            rejected_option_ids=_payload_list(payload, "rejected_option_ids", []),
            summary=payload.get("summary", ""),
            notes=_payload_list(payload, "notes", []),
        )


@dataclass(slots=True)
class PendingDecision:
    decision_id: str
    prompt: str
    created_at: str
    title: str = ""
    choices: list[str] = field(default_factory=list)
    selected_choice: str | None = None
    blocking: bool = True
    due_by: str | None = None
    related_option_set_id: str | None = None
    related_saved_scenario_id: str | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.decision_id, "decision_id")
        require_non_empty(self.prompt, "prompt")
        require_non_empty(self.created_at, "created_at")
        if not self.choices:
            raise ValueError("choices must contain at least one option")
        _require_unique_strings(self.choices, "choices")
        require_optional_non_empty(self.selected_choice, "selected_choice")
        require_optional_non_empty(self.due_by, "due_by")
        require_optional_non_empty(self.related_option_set_id, "related_option_set_id")
        require_optional_non_empty(
            self.related_saved_scenario_id,
            "related_saved_scenario_id",
        )
        _require_string_list(self.notes, "notes")
        if self.selected_choice is not None and self.selected_choice not in self.choices:
            raise ValueError("selected_choice must be one of choices")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PendingDecision":
        return cls(
            decision_id=payload["decision_id"],
            prompt=payload["prompt"],
            created_at=payload["created_at"],
            title=payload.get("title", ""),
            choices=_payload_list(payload, "choices", []),
            selected_choice=payload.get("selected_choice"),
            blocking=payload.get("blocking", True),
            due_by=payload.get("due_by"),
            related_option_set_id=payload.get("related_option_set_id"),
            related_saved_scenario_id=payload.get("related_saved_scenario_id"),
            notes=_payload_list(payload, "notes", []),
        )


@dataclass(slots=True)
class PlanningSessionState:
    session_state_id: str
    trip_id: str
    user_id: str
    owner_profile_id: str
    mode: str
    started_at: str
    updated_at: str
    interaction_state: PlanningInteractionState = field(
        default_factory=PlanningInteractionState
    )
    recent_option_presentations: list[OptionPresentationRecord] = field(
        default_factory=list
    )
    pending_decisions: list[PendingDecision] = field(default_factory=list)
    status: str = "active"
    current_checkpoint_id: str | None = None
    current_saved_scenario_id: str | None = None
    active_budget_plan_id: str | None = None
    activity_log_id: str | None = None
    schema_version: str = SESSION_STATE_SCHEMA_VERSION
    tags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.session_state_id, "session_state_id")
        require_non_empty(self.trip_id, "trip_id")
        require_non_empty(self.user_id, "user_id")
        require_non_empty(self.owner_profile_id, "owner_profile_id")
        require_non_empty(self.started_at, "started_at")
        require_non_empty(self.updated_at, "updated_at")
        if self.mode not in TRIP_MODES:
            raise ValueError(f"mode must be one of {TRIP_MODES}")
        if self.status not in PLANNING_SESSION_STATUSES:
            raise ValueError(
                f"status must be one of {PLANNING_SESSION_STATUSES}"
            )
        if not isinstance(self.interaction_state, PlanningInteractionState):
            raise ValueError("interaction_state must be a PlanningInteractionState")
        if any(
            not isinstance(item, OptionPresentationRecord)
            for item in self.recent_option_presentations
        ):
            raise ValueError(
                "recent_option_presentations must contain OptionPresentationRecord instances"
            )
        if any(not isinstance(item, PendingDecision) for item in self.pending_decisions):
            raise ValueError("pending_decisions must contain PendingDecision instances")
        presentation_ids = [
            presentation.presentation_id
            for presentation in self.recent_option_presentations
        ]
        if len(set(presentation_ids)) != len(presentation_ids):
            raise ValueError(
                "recent_option_presentations cannot repeat presentation_id values"
            )
        decision_ids = [decision.decision_id for decision in self.pending_decisions]
        if len(set(decision_ids)) != len(decision_ids):
            raise ValueError("pending_decisions cannot repeat decision_id values")
        for field_name in (
            "current_checkpoint_id",
            "current_saved_scenario_id",
            "active_budget_plan_id",
            "activity_log_id",
        ):
            require_optional_non_empty(getattr(self, field_name), field_name)
        if self.schema_version != SESSION_STATE_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SESSION_STATE_SCHEMA_VERSION!r}")
        _require_unique_strings(self.tags, "tags")
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PlanningSessionState":
        return cls(
            session_state_id=payload["session_state_id"],
            trip_id=payload["trip_id"],
            user_id=payload["user_id"],
            owner_profile_id=payload["owner_profile_id"],
            mode=payload["mode"],
            started_at=payload["started_at"],
            updated_at=payload["updated_at"],
            interaction_state=PlanningInteractionState.from_dict(
                payload.get("interaction_state", {})
            ),
            recent_option_presentations=[
                OptionPresentationRecord.from_dict(item)
                for item in _payload_list(payload, "recent_option_presentations", [])
            ],
            pending_decisions=[
                PendingDecision.from_dict(item)
                for item in _payload_list(payload, "pending_decisions", [])
            ],
            status=payload.get("status", "active"),
            current_checkpoint_id=payload.get("current_checkpoint_id"),
            current_saved_scenario_id=payload.get("current_saved_scenario_id"),
            active_budget_plan_id=payload.get("active_budget_plan_id"),
            activity_log_id=payload.get("activity_log_id"),
            schema_version=payload.get(
                "schema_version",
                SESSION_STATE_SCHEMA_VERSION,
            ),
            tags=_payload_list(payload, "tags", []),
            notes=_payload_list(payload, "notes", []),
        )


@dataclass(slots=True)
class ActivityLogEvent:
    activity_event_id: str
    trip_id: str
    session_state_id: str
    occurred_at: str
    event_kind: str
    summary: str
    actor: str = "system"
    related_decision_id: str | None = None
    related_option_set_id: str | None = None
    saved_scenario_id: str | None = None
    budget_plan_id: str | None = None
    scenario_budget_id: str | None = None
    checkpoint_id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.activity_event_id, "activity_event_id")
        require_non_empty(self.trip_id, "trip_id")
        require_non_empty(self.session_state_id, "session_state_id")
        require_non_empty(self.occurred_at, "occurred_at")
        require_non_empty(self.summary, "summary")
        require_non_empty(self.actor, "actor")
        if self.event_kind not in ACTIVITY_LOG_EVENT_KINDS:
            raise ValueError(
                f"event_kind must be one of {ACTIVITY_LOG_EVENT_KINDS}"
            )
        for field_name in (
            "related_decision_id",
            "related_option_set_id",
            "saved_scenario_id",
            "budget_plan_id",
            "scenario_budget_id",
            "checkpoint_id",
        ):
            require_optional_non_empty(getattr(self, field_name), field_name)
        require_string_mapping(self.metadata, "metadata")
        if any(not isinstance(value, str) or not value for value in self.metadata.values()):
            raise ValueError("metadata must contain non-empty string values")
        _require_unique_strings(self.tags, "tags")
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ActivityLogEvent":
        return cls(
            activity_event_id=payload["activity_event_id"],
            trip_id=payload["trip_id"],
            session_state_id=payload["session_state_id"],
            occurred_at=payload["occurred_at"],
            event_kind=payload["event_kind"],
            summary=payload["summary"],
            actor=payload.get("actor", "system"),
            related_decision_id=payload.get("related_decision_id"),
            related_option_set_id=payload.get("related_option_set_id"),
            saved_scenario_id=payload.get("saved_scenario_id"),
            budget_plan_id=payload.get("budget_plan_id"),
            scenario_budget_id=payload.get("scenario_budget_id"),
            checkpoint_id=payload.get("checkpoint_id"),
            metadata=payload.get("metadata", {}),
            tags=_payload_list(payload, "tags", []),
            notes=_payload_list(payload, "notes", []),
        )
