"""Persisted saved-scenario, checkpoint, and version-history contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from trip_planner._option_contracts import OPTION_SET_SCOPES
from trip_planner.contracts._validators import (
    require_non_empty,
    require_optional_non_empty,
    require_strings,
)

SCENARIO_STATE_SCHEMA_VERSION = "0.1.0"
SAVED_SCENARIO_LABELS: tuple[str, ...] = (
    "baseline",
    "preferred",
    "fallback",
    "compliant_first",
    "exception_nearest",
    "in_trip_revision",
)
CHECKPOINT_KINDS: tuple[str, ...] = (
    "baseline_capture",
    "decision_gate",
    "fallback_capture",
    "policy_review",
    "in_trip_revision",
)
COMPARISON_OUTCOMES: tuple[str, ...] = (
    "preferred",
    "fallback",
    "equivalent",
    "tradeoff",
)


def _require_unique_strings(values: list[str], field_name: str) -> None:
    if isinstance(values, str) or not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list of strings")
    require_strings(values, field_name)
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
class ScenarioArtifactRefs:
    objective_id: str | None = None
    scenario_search_id: str | None = None
    source_result_set_id: str | None = None
    itinerary_scenario_id: str | None = None
    ranked_result_set_id: str | None = None
    option_set_ids: list[str] = field(default_factory=list)
    budget_state_id: str | None = None
    policy_state_id: str | None = None
    session_state_id: str | None = None
    leisure_profile_id: str | None = None
    business_profile_id: str | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in (
            "objective_id",
            "scenario_search_id",
            "source_result_set_id",
            "itinerary_scenario_id",
            "ranked_result_set_id",
            "budget_state_id",
            "policy_state_id",
            "session_state_id",
            "leisure_profile_id",
            "business_profile_id",
        ):
            require_optional_non_empty(getattr(self, field_name), field_name)
        _require_unique_strings(self.option_set_ids, "option_set_ids")
        require_strings(self.notes, "notes")

        if not any(
            (
                self.objective_id,
                self.scenario_search_id,
                self.source_result_set_id,
                self.itinerary_scenario_id,
                self.ranked_result_set_id,
                self.option_set_ids,
                self.budget_state_id,
                self.policy_state_id,
                self.session_state_id,
            )
        ):
            raise ValueError("ScenarioArtifactRefs must capture at least one saved reference")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ScenarioArtifactRefs":
        return cls(
            objective_id=payload.get("objective_id"),
            scenario_search_id=payload.get("scenario_search_id"),
            source_result_set_id=payload.get("source_result_set_id"),
            itinerary_scenario_id=payload.get("itinerary_scenario_id"),
            ranked_result_set_id=payload.get("ranked_result_set_id"),
            option_set_ids=_payload_list(payload, "option_set_ids", []),
            budget_state_id=payload.get("budget_state_id"),
            policy_state_id=payload.get("policy_state_id"),
            session_state_id=payload.get("session_state_id"),
            leisure_profile_id=payload.get("leisure_profile_id"),
            business_profile_id=payload.get("business_profile_id"),
            notes=_payload_list(payload, "notes", []),
        )


@dataclass(slots=True)
class ScenarioVersion:
    version_id: str
    saved_scenario_id: str
    trip_id: str
    title: str
    label: str
    created_at: str
    created_by: str = "system"
    scope: str = "route"
    snapshot_refs: ScenarioArtifactRefs = field(default_factory=ScenarioArtifactRefs)
    based_on_version_id: str | None = None
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.version_id, "version_id")
        require_non_empty(self.saved_scenario_id, "saved_scenario_id")
        require_non_empty(self.trip_id, "trip_id")
        require_non_empty(self.title, "title")
        require_non_empty(self.created_at, "created_at")
        require_non_empty(self.created_by, "created_by")
        if self.label not in SAVED_SCENARIO_LABELS:
            raise ValueError(f"label must be one of {SAVED_SCENARIO_LABELS}")
        if self.scope not in OPTION_SET_SCOPES:
            raise ValueError(f"scope must be one of {OPTION_SET_SCOPES}")
        if not isinstance(self.snapshot_refs, ScenarioArtifactRefs):
            raise ValueError("snapshot_refs must be a ScenarioArtifactRefs")
        require_optional_non_empty(self.based_on_version_id, "based_on_version_id")
        _require_unique_strings(self.tags, "tags")
        require_strings(self.notes, "notes")

        if self.label in {"compliant_first", "exception_nearest"}:
            if self.snapshot_refs.business_profile_id is None:
                raise ValueError(
                    f"{self.label} versions require snapshot_refs.business_profile_id"
                )
            if self.snapshot_refs.policy_state_id is None:
                raise ValueError(
                    f"{self.label} versions require snapshot_refs.policy_state_id"
                )
        if self.label == "in_trip_revision" and self.snapshot_refs.session_state_id is None:
            raise ValueError("in_trip_revision versions require snapshot_refs.session_state_id")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ScenarioVersion":
        return cls(
            version_id=payload["version_id"],
            saved_scenario_id=payload["saved_scenario_id"],
            trip_id=payload["trip_id"],
            title=payload["title"],
            label=payload["label"],
            created_at=payload["created_at"],
            created_by=payload.get("created_by", "system"),
            scope=payload.get("scope", "route"),
            snapshot_refs=ScenarioArtifactRefs.from_dict(
                payload.get("snapshot_refs", {})
            ),
            based_on_version_id=payload.get("based_on_version_id"),
            summary=payload.get("summary", ""),
            tags=_payload_list(payload, "tags", []),
            notes=_payload_list(payload, "notes", []),
        )


@dataclass(slots=True)
class ScenarioComparison:
    comparison_id: str
    trip_id: str
    baseline_scenario_id: str
    candidate_scenario_id: str
    compared_at: str
    outcome: str
    summary: str
    focus_areas: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.comparison_id, "comparison_id")
        require_non_empty(self.trip_id, "trip_id")
        require_non_empty(self.baseline_scenario_id, "baseline_scenario_id")
        require_non_empty(self.candidate_scenario_id, "candidate_scenario_id")
        require_non_empty(self.compared_at, "compared_at")
        require_non_empty(self.summary, "summary")
        if self.outcome not in COMPARISON_OUTCOMES:
            raise ValueError(f"outcome must be one of {COMPARISON_OUTCOMES}")
        if self.baseline_scenario_id == self.candidate_scenario_id:
            raise ValueError("candidate_scenario_id must differ from baseline_scenario_id")
        _require_unique_strings(self.focus_areas, "focus_areas")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ScenarioComparison":
        return cls(
            comparison_id=payload["comparison_id"],
            trip_id=payload["trip_id"],
            baseline_scenario_id=payload["baseline_scenario_id"],
            candidate_scenario_id=payload["candidate_scenario_id"],
            compared_at=payload["compared_at"],
            outcome=payload["outcome"],
            summary=payload["summary"],
            focus_areas=_payload_list(payload, "focus_areas", []),
            notes=_payload_list(payload, "notes", []),
        )


@dataclass(slots=True)
class SavedScenarioRecord:
    saved_scenario_id: str
    trip_id: str
    current_version_id: str
    versions: list[ScenarioVersion]
    comparisons: list[ScenarioComparison] = field(default_factory=list)
    schema_version: str = SCENARIO_STATE_SCHEMA_VERSION
    tags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.saved_scenario_id, "saved_scenario_id")
        require_non_empty(self.trip_id, "trip_id")
        require_non_empty(self.current_version_id, "current_version_id")
        if not self.versions:
            raise ValueError("versions must contain at least one ScenarioVersion")
        if any(not isinstance(item, ScenarioVersion) for item in self.versions):
            raise ValueError("versions must contain ScenarioVersion instances")
        if any(not isinstance(item, ScenarioComparison) for item in self.comparisons):
            raise ValueError("comparisons must contain ScenarioComparison instances")
        if self.schema_version != SCENARIO_STATE_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be {SCENARIO_STATE_SCHEMA_VERSION!r}"
            )
        _require_unique_strings(self.tags, "tags")
        require_strings(self.notes, "notes")

        version_ids = [item.version_id for item in self.versions]
        if len(set(version_ids)) != len(version_ids):
            raise ValueError("versions cannot repeat version_id values")
        if self.current_version_id not in version_ids:
            raise ValueError("current_version_id must reference a saved version")
        for version in self.versions:
            if version.saved_scenario_id != self.saved_scenario_id:
                raise ValueError("all versions must share the record saved_scenario_id")
            if version.trip_id != self.trip_id:
                raise ValueError("all versions must share the record trip_id")

        for comparison in self.comparisons:
            if comparison.trip_id != self.trip_id:
                raise ValueError("comparisons must share the record trip_id")
            if comparison.baseline_scenario_id != self.saved_scenario_id:
                raise ValueError("comparisons must reference the record scenario as baseline")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SavedScenarioRecord":
        return cls(
            saved_scenario_id=payload["saved_scenario_id"],
            trip_id=payload["trip_id"],
            current_version_id=payload["current_version_id"],
            versions=[
                ScenarioVersion.from_dict(item)
                for item in _payload_list(payload, "versions", [])
            ],
            comparisons=[
                ScenarioComparison.from_dict(item)
                for item in _payload_list(payload, "comparisons", [])
            ],
            schema_version=payload.get(
                "schema_version", SCENARIO_STATE_SCHEMA_VERSION
            ),
            tags=_payload_list(payload, "tags", []),
            notes=_payload_list(payload, "notes", []),
        )


@dataclass(slots=True)
class ScenarioCheckpoint:
    checkpoint_id: str
    trip_id: str
    saved_scenario_id: str
    version_id: str
    created_at: str
    checkpoint_kind: str
    title: str
    summary: str = ""
    pending_decision_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.checkpoint_id, "checkpoint_id")
        require_non_empty(self.trip_id, "trip_id")
        require_non_empty(self.saved_scenario_id, "saved_scenario_id")
        require_non_empty(self.version_id, "version_id")
        require_non_empty(self.created_at, "created_at")
        require_non_empty(self.title, "title")
        if self.checkpoint_kind not in CHECKPOINT_KINDS:
            raise ValueError(f"checkpoint_kind must be one of {CHECKPOINT_KINDS}")
        _require_unique_strings(self.pending_decision_ids, "pending_decision_ids")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ScenarioCheckpoint":
        return cls(
            checkpoint_id=payload["checkpoint_id"],
            trip_id=payload["trip_id"],
            saved_scenario_id=payload["saved_scenario_id"],
            version_id=payload["version_id"],
            created_at=payload["created_at"],
            checkpoint_kind=payload["checkpoint_kind"],
            title=payload["title"],
            summary=payload.get("summary", ""),
            pending_decision_ids=_payload_list(payload, "pending_decision_ids", []),
            notes=_payload_list(payload, "notes", []),
        )
