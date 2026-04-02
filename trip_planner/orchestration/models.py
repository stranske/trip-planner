"""Planner-turn, workflow-state, and output contracts."""

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

from .actions import (
    ACTION_KINDS,
    ACTION_STATUSES,
    OUTPUT_KINDS,
    OUTPUT_SURFACES,
    TRANSITION_TRIGGERS,
    TURN_KINDS,
    WORKFLOW_KINDS,
    WORKFLOW_STAGES,
    WORKFLOW_STATUSES,
)

ORCHESTRATION_SCHEMA_VERSION = "0.1.0"


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


def _payload_mapping(
    payload: dict[str, Any], field_name: str, default: dict[str, Any]
) -> dict[str, Any]:
    value = payload.get(field_name, default)
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a mapping")
    return dict(value)


@dataclass(slots=True)
class DecisionOption:
    choice_id: str
    label: str
    description: str = ""
    recommended: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.choice_id, "choice_id")
        require_non_empty(self.label, "label")
        require_string_mapping(self.metadata, "metadata")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DecisionOption":
        return cls(
            choice_id=payload["choice_id"],
            label=payload["label"],
            description=payload.get("description", ""),
            recommended=payload.get("recommended", False),
            metadata=_payload_mapping(payload, "metadata", {}),
        )


@dataclass(slots=True)
class PendingDecision:
    decision_id: str
    prompt: str
    requested_at: str
    choices: list[DecisionOption] = field(default_factory=list)
    blocking: bool = True
    selected_choice_id: str | None = None
    due_by: str | None = None
    notes: list[str] = field(default_factory=list)
    related_option_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.decision_id, "decision_id")
        require_non_empty(self.prompt, "prompt")
        require_non_empty(self.requested_at, "requested_at")
        require_optional_non_empty(self.selected_choice_id, "selected_choice_id")
        require_optional_non_empty(self.due_by, "due_by")
        if not self.choices:
            raise ValueError("choices must contain at least one option")
        if any(not isinstance(choice, DecisionOption) for choice in self.choices):
            raise ValueError("choices must contain DecisionOption instances")
        choice_ids = [choice.choice_id for choice in self.choices]
        if len(set(choice_ids)) != len(choice_ids):
            raise ValueError("choices cannot repeat choice_id values")
        if (
            self.selected_choice_id is not None
            and self.selected_choice_id not in choice_ids
        ):
            raise ValueError("selected_choice_id must be one of choices")
        _require_string_list(self.notes, "notes")
        _require_unique_strings(self.related_option_ids, "related_option_ids")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PendingDecision":
        return cls(
            decision_id=payload["decision_id"],
            prompt=payload["prompt"],
            requested_at=payload["requested_at"],
            choices=[
                DecisionOption.from_dict(item)
                for item in _payload_list(payload, "choices", [])
            ],
            blocking=payload.get("blocking", True),
            selected_choice_id=payload.get("selected_choice_id"),
            due_by=payload.get("due_by"),
            notes=_payload_list(payload, "notes", []),
            related_option_ids=_payload_list(payload, "related_option_ids", []),
        )


@dataclass(slots=True)
class PlannerAction:
    action_id: str
    action_kind: str
    title: str
    stage: str
    status: str = "pending"
    actor: str = "planner"
    depends_on_action_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.action_id, "action_id")
        require_non_empty(self.title, "title")
        require_non_empty(self.actor, "actor")
        if self.action_kind not in ACTION_KINDS:
            raise ValueError(f"action_kind must be one of {ACTION_KINDS}")
        if self.stage not in WORKFLOW_STAGES:
            raise ValueError(f"stage must be one of {WORKFLOW_STAGES}")
        if self.status not in ACTION_STATUSES:
            raise ValueError(f"status must be one of {ACTION_STATUSES}")
        _require_unique_strings(self.depends_on_action_ids, "depends_on_action_ids")
        if self.action_id in self.depends_on_action_ids:
            raise ValueError("depends_on_action_ids cannot include action_id itself")
        _require_string_list(self.notes, "notes")
        require_string_mapping(self.payload, "payload")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PlannerAction":
        return cls(
            action_id=payload["action_id"],
            action_kind=payload["action_kind"],
            title=payload["title"],
            stage=payload["stage"],
            status=payload.get("status", "pending"),
            actor=payload.get("actor", "planner"),
            depends_on_action_ids=_payload_list(payload, "depends_on_action_ids", []),
            notes=_payload_list(payload, "notes", []),
            payload=_payload_mapping(payload, "payload", {}),
        )


@dataclass(slots=True)
class PlannerOutput:
    output_id: str
    output_kind: str
    title: str
    emitted_at: str
    surface: str = "planner_chat"
    summary: str = ""
    ref_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.output_id, "output_id")
        require_non_empty(self.title, "title")
        require_non_empty(self.emitted_at, "emitted_at")
        if self.output_kind not in OUTPUT_KINDS:
            raise ValueError(f"output_kind must be one of {OUTPUT_KINDS}")
        if self.surface not in OUTPUT_SURFACES:
            raise ValueError(f"surface must be one of {OUTPUT_SURFACES}")
        _require_unique_strings(self.ref_ids, "ref_ids")
        _require_string_list(self.warnings, "warnings")
        require_string_mapping(self.payload, "payload")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PlannerOutput":
        return cls(
            output_id=payload["output_id"],
            output_kind=payload["output_kind"],
            title=payload["title"],
            emitted_at=payload["emitted_at"],
            surface=payload.get("surface", "planner_chat"),
            summary=payload.get("summary", ""),
            ref_ids=_payload_list(payload, "ref_ids", []),
            warnings=_payload_list(payload, "warnings", []),
            payload=_payload_mapping(payload, "payload", {}),
        )


@dataclass(slots=True)
class WorkflowTransition:
    from_stage: str
    to_stage: str
    trigger: str
    changed_at: str
    reason: str
    changed_by: str = "planner"
    blocker_ids: list[str] = field(default_factory=list)
    warning_codes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.from_stage not in WORKFLOW_STAGES:
            raise ValueError(f"from_stage must be one of {WORKFLOW_STAGES}")
        if self.to_stage not in WORKFLOW_STAGES:
            raise ValueError(f"to_stage must be one of {WORKFLOW_STAGES}")
        if self.trigger not in TRANSITION_TRIGGERS:
            raise ValueError(f"trigger must be one of {TRANSITION_TRIGGERS}")
        require_non_empty(self.changed_at, "changed_at")
        require_non_empty(self.reason, "reason")
        require_non_empty(self.changed_by, "changed_by")
        _require_unique_strings(self.blocker_ids, "blocker_ids")
        _require_unique_strings(self.warning_codes, "warning_codes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WorkflowTransition":
        return cls(
            from_stage=payload["from_stage"],
            to_stage=payload["to_stage"],
            trigger=payload["trigger"],
            changed_at=payload["changed_at"],
            reason=payload["reason"],
            changed_by=payload.get("changed_by", "planner"),
            blocker_ids=_payload_list(payload, "blocker_ids", []),
            warning_codes=_payload_list(payload, "warning_codes", []),
        )


@dataclass(slots=True)
class NextStepSummary:
    headline: str
    recommended_action_id: str | None = None
    blocking_decision_ids: list[str] = field(default_factory=list)
    expected_output_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.headline, "headline")
        require_optional_non_empty(self.recommended_action_id, "recommended_action_id")
        _require_unique_strings(self.blocking_decision_ids, "blocking_decision_ids")
        _require_unique_strings(self.expected_output_ids, "expected_output_ids")
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NextStepSummary":
        return cls(
            headline=payload["headline"],
            recommended_action_id=payload.get("recommended_action_id"),
            blocking_decision_ids=_payload_list(payload, "blocking_decision_ids", []),
            expected_output_ids=_payload_list(payload, "expected_output_ids", []),
            notes=_payload_list(payload, "notes", []),
        )


@dataclass(slots=True)
class WorkflowStateSnapshot:
    workflow_state_id: str
    trip_id: str
    mode: str
    workflow_kind: str
    current_stage: str
    status: str
    recorded_at: str
    pending_decisions: list[PendingDecision] = field(default_factory=list)
    open_action_ids: list[str] = field(default_factory=list)
    completed_action_ids: list[str] = field(default_factory=list)
    recent_output_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    schema_version: str = ORCHESTRATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_non_empty(self.workflow_state_id, "workflow_state_id")
        require_non_empty(self.trip_id, "trip_id")
        require_non_empty(self.recorded_at, "recorded_at")
        if self.mode not in TRIP_MODES:
            raise ValueError(f"mode must be one of {TRIP_MODES}")
        if self.workflow_kind not in WORKFLOW_KINDS:
            raise ValueError(f"workflow_kind must be one of {WORKFLOW_KINDS}")
        if self.current_stage not in WORKFLOW_STAGES:
            raise ValueError(f"current_stage must be one of {WORKFLOW_STAGES}")
        if self.status not in WORKFLOW_STATUSES:
            raise ValueError(f"status must be one of {WORKFLOW_STATUSES}")
        if any(
            not isinstance(item, PendingDecision) for item in self.pending_decisions
        ):
            raise ValueError("pending_decisions must contain PendingDecision instances")
        decision_ids = [decision.decision_id for decision in self.pending_decisions]
        if len(set(decision_ids)) != len(decision_ids):
            raise ValueError("pending_decisions cannot repeat decision_id values")
        _require_unique_strings(self.open_action_ids, "open_action_ids")
        _require_unique_strings(self.completed_action_ids, "completed_action_ids")
        overlapping_actions = set(self.open_action_ids) & set(self.completed_action_ids)
        if overlapping_actions:
            raise ValueError(
                "open_action_ids and completed_action_ids must not overlap"
            )
        _require_unique_strings(self.recent_output_ids, "recent_output_ids")
        _require_unique_strings(self.tags, "tags")
        _require_string_list(self.notes, "notes")
        if self.schema_version != ORCHESTRATION_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {ORCHESTRATION_SCHEMA_VERSION!r}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WorkflowStateSnapshot":
        return cls(
            workflow_state_id=payload["workflow_state_id"],
            trip_id=payload["trip_id"],
            mode=payload["mode"],
            workflow_kind=payload["workflow_kind"],
            current_stage=payload["current_stage"],
            status=payload["status"],
            recorded_at=payload["recorded_at"],
            pending_decisions=[
                PendingDecision.from_dict(item)
                for item in _payload_list(payload, "pending_decisions", [])
            ],
            open_action_ids=_payload_list(payload, "open_action_ids", []),
            completed_action_ids=_payload_list(payload, "completed_action_ids", []),
            recent_output_ids=_payload_list(payload, "recent_output_ids", []),
            notes=_payload_list(payload, "notes", []),
            tags=_payload_list(payload, "tags", []),
            schema_version=payload.get(
                "schema_version",
                ORCHESTRATION_SCHEMA_VERSION,
            ),
        )


@dataclass(slots=True)
class PlannerTurn:
    turn_id: str
    trip_id: str
    mode: str
    workflow_kind: str
    turn_kind: str
    started_at: str
    workflow_state: WorkflowStateSnapshot
    transition: WorkflowTransition
    next_step: NextStepSummary
    actions: list[PlannerAction] = field(default_factory=list)
    outputs: list[PlannerOutput] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    schema_version: str = ORCHESTRATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_non_empty(self.turn_id, "turn_id")
        require_non_empty(self.trip_id, "trip_id")
        require_non_empty(self.started_at, "started_at")
        if self.mode not in TRIP_MODES:
            raise ValueError(f"mode must be one of {TRIP_MODES}")
        if self.workflow_kind not in WORKFLOW_KINDS:
            raise ValueError(f"workflow_kind must be one of {WORKFLOW_KINDS}")
        if self.turn_kind not in TURN_KINDS:
            raise ValueError(f"turn_kind must be one of {TURN_KINDS}")
        if not isinstance(self.workflow_state, WorkflowStateSnapshot):
            raise ValueError("workflow_state must be a WorkflowStateSnapshot")
        if not isinstance(self.transition, WorkflowTransition):
            raise ValueError("transition must be a WorkflowTransition")
        if not isinstance(self.next_step, NextStepSummary):
            raise ValueError("next_step must be a NextStepSummary")
        if self.workflow_state.trip_id != self.trip_id:
            raise ValueError("workflow_state.trip_id must match trip_id")
        if self.workflow_state.mode != self.mode:
            raise ValueError("workflow_state.mode must match mode")
        if self.workflow_state.workflow_kind != self.workflow_kind:
            raise ValueError("workflow_state.workflow_kind must match workflow_kind")
        if self.transition.to_stage != self.workflow_state.current_stage:
            raise ValueError(
                "transition.to_stage must match workflow_state.current_stage"
            )
        if any(not isinstance(item, PlannerAction) for item in self.actions):
            raise ValueError("actions must contain PlannerAction instances")
        if any(not isinstance(item, PlannerOutput) for item in self.outputs):
            raise ValueError("outputs must contain PlannerOutput instances")
        action_ids = [action.action_id for action in self.actions]
        if len(set(action_ids)) != len(action_ids):
            raise ValueError("actions cannot repeat action_id values")
        output_ids = [output.output_id for output in self.outputs]
        if len(set(output_ids)) != len(output_ids):
            raise ValueError("outputs cannot repeat output_id values")
        all_known_action_ids = set(action_ids)
        unknown_open = set(self.workflow_state.open_action_ids) - all_known_action_ids
        unknown_completed = (
            set(self.workflow_state.completed_action_ids) - all_known_action_ids
        )
        if unknown_open or unknown_completed:
            raise ValueError("workflow_state action ids must be present in actions")
        all_decision_ids = {
            decision.decision_id for decision in self.workflow_state.pending_decisions
        }
        if not set(self.next_step.blocking_decision_ids).issubset(all_decision_ids):
            raise ValueError(
                "next_step.blocking_decision_ids must refer to pending_decisions"
            )
        if self.next_step.recommended_action_id is not None and (
            self.next_step.recommended_action_id not in all_known_action_ids
        ):
            raise ValueError("next_step.recommended_action_id must refer to an action")
        if not set(self.next_step.expected_output_ids).issubset(set(output_ids)):
            raise ValueError("next_step.expected_output_ids must refer to outputs")
        _require_string_list(self.notes, "notes")
        if self.schema_version != ORCHESTRATION_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {ORCHESTRATION_SCHEMA_VERSION!r}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PlannerTurn":
        return cls(
            turn_id=payload["turn_id"],
            trip_id=payload["trip_id"],
            mode=payload["mode"],
            workflow_kind=payload["workflow_kind"],
            turn_kind=payload["turn_kind"],
            started_at=payload["started_at"],
            workflow_state=WorkflowStateSnapshot.from_dict(payload["workflow_state"]),
            transition=WorkflowTransition.from_dict(payload["transition"]),
            next_step=NextStepSummary.from_dict(payload["next_step"]),
            actions=[
                PlannerAction.from_dict(item)
                for item in _payload_list(payload, "actions", [])
            ],
            outputs=[
                PlannerOutput.from_dict(item)
                for item in _payload_list(payload, "outputs", [])
            ],
            notes=_payload_list(payload, "notes", []),
            schema_version=payload.get(
                "schema_version",
                ORCHESTRATION_SCHEMA_VERSION,
            ),
        )
