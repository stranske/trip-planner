"""Persisted trip-state contracts and lifecycle transition rules."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from trip_planner.contracts._validators import (
    require_non_empty,
    require_optional_non_empty,
    require_string_mapping,
    require_strings,
)
from trip_planner.contracts.trip import TRIP_MODES, TRIP_STATUSES, Trip

TRIP_SCHEMA_VERSION = "0.1.0"
ALLOWED_TRIP_STATUS_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "draft": ("active", "archived"),
    "active": ("booked", "archived"),
    "booked": ("in_trip", "archived"),
    "in_trip": ("completed", "archived"),
    "completed": ("archived",),
    "archived": (),
}


def _require_unique_strings(values: list[str], field_name: str) -> None:
    if isinstance(values, str) or not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list of strings")
    require_strings(values, field_name)
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} cannot contain duplicates")


def _payload_list(payload: dict[str, Any], field_name: str, default: list[Any]) -> list[Any]:
    value = payload.get(field_name, default)
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    return list(value)


def validate_trip_status_transition(from_status: str, to_status: str) -> None:
    if from_status not in TRIP_STATUSES:
        raise ValueError(f"from_status must be one of {TRIP_STATUSES}")
    if to_status not in TRIP_STATUSES:
        raise ValueError(f"to_status must be one of {TRIP_STATUSES}")
    allowed_transitions = ALLOWED_TRIP_STATUS_TRANSITIONS.get(from_status)
    if allowed_transitions is None:
        raise ValueError(f"from_status {from_status!r} has no configured transitions")
    if to_status not in allowed_transitions:
        raise ValueError(f"{from_status} cannot transition to {to_status}")


@dataclass(slots=True)
class PersistedTripArtifactRefs:
    objective_id: str | None = None
    option_set_ids: list[str] = field(default_factory=list)
    ranked_result_set_id: str | None = None
    scenario_search_id: str | None = None
    saved_scenario_ids: list[str] = field(default_factory=list)
    itinerary_state_id: str | None = None
    budget_state_id: str | None = None
    policy_state_id: str | None = None
    session_state_id: str | None = None
    activity_log_id: str | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in (
            "objective_id",
            "ranked_result_set_id",
            "scenario_search_id",
            "itinerary_state_id",
            "budget_state_id",
            "policy_state_id",
            "session_state_id",
            "activity_log_id",
        ):
            require_optional_non_empty(getattr(self, field_name), field_name)
        _require_unique_strings(self.option_set_ids, "option_set_ids")
        _require_unique_strings(self.saved_scenario_ids, "saved_scenario_ids")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PersistedTripArtifactRefs":
        return cls(
            objective_id=payload.get("objective_id"),
            option_set_ids=_payload_list(payload, "option_set_ids", []),
            ranked_result_set_id=payload.get("ranked_result_set_id"),
            scenario_search_id=payload.get("scenario_search_id"),
            saved_scenario_ids=_payload_list(payload, "saved_scenario_ids", []),
            itinerary_state_id=payload.get("itinerary_state_id"),
            budget_state_id=payload.get("budget_state_id"),
            policy_state_id=payload.get("policy_state_id"),
            session_state_id=payload.get("session_state_id"),
            activity_log_id=payload.get("activity_log_id"),
            notes=_payload_list(payload, "notes", []),
        )


@dataclass(slots=True)
class TripLifecycle:
    created_at: str
    updated_at: str
    booked_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    archived_at: str | None = None

    def __post_init__(self) -> None:
        require_non_empty(self.created_at, "created_at")
        require_non_empty(self.updated_at, "updated_at")
        require_optional_non_empty(self.booked_at, "booked_at")
        require_optional_non_empty(self.started_at, "started_at")
        require_optional_non_empty(self.completed_at, "completed_at")
        require_optional_non_empty(self.archived_at, "archived_at")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TripLifecycle":
        return cls(
            created_at=payload["created_at"],
            updated_at=payload["updated_at"],
            booked_at=payload.get("booked_at"),
            started_at=payload.get("started_at"),
            completed_at=payload.get("completed_at"),
            archived_at=payload.get("archived_at"),
        )


@dataclass(slots=True)
class TripStatusChange:
    to_status: str
    changed_at: str
    reason: str = ""
    actor: str = "system"
    from_status: str | None = None

    def __post_init__(self) -> None:
        if self.to_status not in TRIP_STATUSES:
            raise ValueError(f"to_status must be one of {TRIP_STATUSES}")
        require_non_empty(self.changed_at, "changed_at")
        require_non_empty(self.actor, "actor")
        if self.from_status is not None:
            validate_trip_status_transition(self.from_status, self.to_status)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TripStatusChange":
        return cls(
            to_status=payload["to_status"],
            changed_at=payload["changed_at"],
            reason=payload.get("reason", ""),
            actor=payload.get("actor", "system"),
            from_status=payload.get("from_status"),
        )


@dataclass(slots=True)
class PersistedTripRecord:
    trip: Trip
    owner_profile_id: str
    lifecycle: TripLifecycle
    artifact_refs: PersistedTripArtifactRefs = field(default_factory=PersistedTripArtifactRefs)
    status_history: list[TripStatusChange] = field(default_factory=list)
    schema_version: str = TRIP_SCHEMA_VERSION
    revision: int = 1
    external_refs: dict[str, str] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.trip, Trip):
            raise ValueError("trip must be a Trip")
        require_non_empty(self.owner_profile_id, "owner_profile_id")
        if not isinstance(self.lifecycle, TripLifecycle):
            raise ValueError("lifecycle must be a TripLifecycle")
        if not isinstance(self.artifact_refs, PersistedTripArtifactRefs):
            raise ValueError("artifact_refs must be a PersistedTripArtifactRefs")
        if any(not isinstance(item, TripStatusChange) for item in self.status_history):
            raise ValueError("status_history must contain TripStatusChange instances")
        if self.schema_version != TRIP_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {TRIP_SCHEMA_VERSION!r}")
        if self.revision <= 0:
            raise ValueError("revision must be positive")
        require_string_mapping(self.external_refs, "external_refs")
        if any(not isinstance(value, str) or not value for value in self.external_refs.values()):
            raise ValueError("external_refs must contain non-empty string values")
        _require_unique_strings(self.tags, "tags")
        require_strings(self.notes, "notes")
        if self.trip.mode not in TRIP_MODES:
            raise ValueError(f"trip.mode must be one of {TRIP_MODES}")
        if self.trip.mode == "leisure" and self.artifact_refs.policy_state_id is not None:
            raise ValueError("leisure trips cannot persist policy_state_id")
        if self.trip.status == "archived" and self.lifecycle.archived_at is None:
            raise ValueError("archived trips require lifecycle.archived_at")
        if self.trip.status != "archived" and self.lifecycle.archived_at is not None:
            raise ValueError("lifecycle.archived_at requires archived trip status")
        if self.status_history:
            if self.status_history[-1].to_status != self.trip.status:
                raise ValueError("status_history must end at the persisted trip status")
            if self.status_history[0].from_status is not None:
                raise ValueError("first status change cannot declare from_status")
            for prior, current in zip(self.status_history, self.status_history[1:]):
                if current.from_status != prior.to_status:
                    raise ValueError(
                        "status_history transitions must chain from the prior to_status"
                    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PersistedTripRecord":
        return cls(
            trip=Trip.from_dict(payload["trip"]),
            owner_profile_id=payload["owner_profile_id"],
            lifecycle=TripLifecycle.from_dict(payload["lifecycle"]),
            artifact_refs=PersistedTripArtifactRefs.from_dict(payload.get("artifact_refs", {})),
            status_history=[
                TripStatusChange.from_dict(item)
                for item in _payload_list(payload, "status_history", [])
            ],
            schema_version=payload.get("schema_version", TRIP_SCHEMA_VERSION),
            revision=payload.get("revision", 1),
            external_refs=payload.get("external_refs", {}),
            tags=_payload_list(payload, "tags", []),
            notes=_payload_list(payload, "notes", []),
        )
