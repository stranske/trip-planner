"""Shared trip container contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from ._validators import require_non_empty, require_strings

TRIP_MODES: tuple[str, ...] = ("leisure", "business")
TRIP_STATUSES: tuple[str, ...] = (
    "draft",
    "active",
    "booked",
    "in_trip",
    "completed",
    "archived",
)
TRAVELER_PARTY_KINDS: tuple[str, ...] = ("solo", "pair", "family", "friends", "team")


def _payload_list(payload: dict[str, Any], field_name: str, default: list[Any]) -> list[Any]:
    value = payload.get(field_name, default)
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    return list(value)


@dataclass(slots=True)
class TravelerPartySummary:
    kind: str = "solo"
    traveler_count: int = 1
    notes: str = ""

    def __post_init__(self) -> None:
        if self.kind not in TRAVELER_PARTY_KINDS:
            raise ValueError(f"kind must be one of {TRAVELER_PARTY_KINDS}")
        if self.traveler_count <= 0:
            raise ValueError("traveler_count must be positive")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TravelerPartySummary":
        return cls(**payload)


@dataclass(slots=True)
class TripFrameSummary:
    start_date: str | None = None
    end_date: str | None = None
    duration_days: int | None = None
    primary_regions: list[str] = field(default_factory=list)
    traveler_party: TravelerPartySummary = field(default_factory=TravelerPartySummary)

    def __post_init__(self) -> None:
        if self.start_date is not None and not self.start_date:
            raise ValueError("start_date must be non-empty when provided")
        if self.end_date is not None and not self.end_date:
            raise ValueError("end_date must be non-empty when provided")
        if self.duration_days is not None and self.duration_days <= 0:
            raise ValueError("duration_days must be positive when provided")
        require_strings(self.primary_regions, "primary_regions")
        if not isinstance(self.traveler_party, TravelerPartySummary):
            raise ValueError("traveler_party must be a TravelerPartySummary")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TripFrameSummary":
        return cls(
            start_date=payload.get("start_date"),
            end_date=payload.get("end_date"),
            duration_days=payload.get("duration_days"),
            primary_regions=_payload_list(payload, "primary_regions", []),
            traveler_party=TravelerPartySummary.from_dict(payload.get("traveler_party", {})),
        )


@dataclass(slots=True)
class ProfileRefs:
    leisure_profile_id: str | None = None
    business_profile_id: str | None = None

    def __post_init__(self) -> None:
        if self.leisure_profile_id is not None and not self.leisure_profile_id:
            raise ValueError("leisure_profile_id must be non-empty when provided")
        if self.business_profile_id is not None and not self.business_profile_id:
            raise ValueError("business_profile_id must be non-empty when provided")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProfileRefs":
        return cls(
            leisure_profile_id=payload.get("leisure_profile_id"),
            business_profile_id=payload.get("business_profile_id"),
        )


@dataclass(slots=True)
class TripArtifactRefs:
    objective_id: str | None = None
    option_set_ids: list[str] = field(default_factory=list)
    itinerary_state_id: str | None = None
    budget_state_id: str | None = None
    policy_state_id: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "objective_id",
            "itinerary_state_id",
            "budget_state_id",
            "policy_state_id",
        ):
            value = getattr(self, field_name)
            if value is not None and not value:
                raise ValueError(f"{field_name} must be non-empty when provided")
        require_strings(self.option_set_ids, "option_set_ids")
        if len(set(self.option_set_ids)) != len(self.option_set_ids):
            raise ValueError("option_set_ids cannot contain duplicates")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TripArtifactRefs":
        return cls(
            objective_id=payload.get("objective_id"),
            option_set_ids=_payload_list(payload, "option_set_ids", []),
            itinerary_state_id=payload.get("itinerary_state_id"),
            budget_state_id=payload.get("budget_state_id"),
            policy_state_id=payload.get("policy_state_id"),
        )


@dataclass(slots=True)
class Trip:
    trip_id: str
    user_id: str
    mode: str
    status: str
    trip_frame: TripFrameSummary
    profile_refs: ProfileRefs
    artifacts: TripArtifactRefs = field(default_factory=TripArtifactRefs)
    title: str = ""
    summary: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.trip_id, "trip_id")
        require_non_empty(self.user_id, "user_id")
        if self.mode not in TRIP_MODES:
            raise ValueError(f"mode must be one of {TRIP_MODES}")
        if self.status not in TRIP_STATUSES:
            raise ValueError(f"status must be one of {TRIP_STATUSES}")
        if not isinstance(self.trip_frame, TripFrameSummary):
            raise ValueError("trip_frame must be a TripFrameSummary")
        if not isinstance(self.profile_refs, ProfileRefs):
            raise ValueError("profile_refs must be a ProfileRefs")
        if not isinstance(self.artifacts, TripArtifactRefs):
            raise ValueError("artifacts must be a TripArtifactRefs")
        if self.mode == "leisure":
            if self.profile_refs.leisure_profile_id is None:
                raise ValueError("leisure trips require leisure_profile_id")
            if self.profile_refs.business_profile_id is not None:
                raise ValueError("leisure trips cannot also carry business_profile_id")
            if self.artifacts.policy_state_id is not None:
                raise ValueError("leisure trips cannot carry policy_state_id")
        if self.mode == "business":
            if self.profile_refs.business_profile_id is None:
                raise ValueError("business trips require business_profile_id")
            if self.profile_refs.leisure_profile_id is not None:
                raise ValueError("business trips cannot also carry leisure_profile_id")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Trip":
        return cls(
            trip_id=payload["trip_id"],
            user_id=payload["user_id"],
            mode=payload["mode"],
            status=payload["status"],
            trip_frame=TripFrameSummary.from_dict(payload.get("trip_frame", {})),
            profile_refs=ProfileRefs.from_dict(payload.get("profile_refs", {})),
            artifacts=TripArtifactRefs.from_dict(payload.get("artifacts", {})),
            title=payload.get("title", ""),
            summary=payload.get("summary", ""),
        )
