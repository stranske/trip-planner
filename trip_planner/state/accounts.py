"""Persisted account-state contracts for users and traveler profiles."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from trip_planner.contracts._validators import (
    require_non_empty,
    require_optional_non_empty,
    require_strings,
)
from trip_planner.contracts.trip import TRIP_MODES

ACCOUNT_SCHEMA_VERSION = "0.1.0"
ACCOUNT_STATUSES: tuple[str, ...] = ("active", "archived")
TRAVELER_PROFILE_KINDS: tuple[str, ...] = ("personal", "family", "business", "mixed")
INTERACTION_STYLES: tuple[str, ...] = ("concise", "guided", "collaborative", "autonomous")
SUMMARY_GRANULARITIES: tuple[str, ...] = ("brief", "balanced", "detailed")
NOTIFICATION_CADENCES: tuple[str, ...] = ("off", "important_only", "digest", "realtime")
NOTIFICATION_CHANNELS: tuple[str, ...] = ("email", "push", "sms")


def _require_unique_strings(values: list[str], field_name: str) -> None:
    require_strings(values, field_name)
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} cannot contain duplicates")


def _payload_list(payload: dict[str, Any], field_name: str, default: list[Any]) -> list[Any]:
    value = payload.get(field_name, default)
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    return list(value)


@dataclass(slots=True)
class RegionalDefaults:
    locale: str = "en-US"
    currency: str = "USD"
    timezone: str = "UTC"
    home_airport: str | None = None
    departure_region: str | None = None

    def __post_init__(self) -> None:
        require_non_empty(self.locale, "locale")
        require_non_empty(self.currency, "currency")
        require_non_empty(self.timezone, "timezone")
        require_optional_non_empty(self.home_airport, "home_airport")
        require_optional_non_empty(self.departure_region, "departure_region")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RegionalDefaults":
        return cls(**payload)


@dataclass(slots=True)
class NotificationPreference:
    channel: str
    cadence: str = "important_only"
    enabled: bool = True

    def __post_init__(self) -> None:
        if self.channel not in NOTIFICATION_CHANNELS:
            raise ValueError(f"channel must be one of {NOTIFICATION_CHANNELS}")
        if self.cadence not in NOTIFICATION_CADENCES:
            raise ValueError(f"cadence must be one of {NOTIFICATION_CADENCES}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NotificationPreference":
        return cls(**payload)


@dataclass(slots=True)
class AccountPreferenceRecord:
    default_traveler_profile_id: str | None = None
    default_interaction_style: str = "guided"
    default_summary_granularity: str = "balanced"
    default_trip_mode: str | None = None
    auto_save_checkpoints: bool = True
    regional_defaults: RegionalDefaults = field(default_factory=RegionalDefaults)
    notification_preferences: list[NotificationPreference] = field(default_factory=list)
    preferred_languages: list[str] = field(default_factory=list)
    planning_tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_optional_non_empty(
            self.default_traveler_profile_id,
            "default_traveler_profile_id",
        )
        if self.default_interaction_style not in INTERACTION_STYLES:
            raise ValueError(
                f"default_interaction_style must be one of {INTERACTION_STYLES}"
            )
        if self.default_summary_granularity not in SUMMARY_GRANULARITIES:
            raise ValueError(
                "default_summary_granularity must be one of "
                f"{SUMMARY_GRANULARITIES}"
            )
        if self.default_trip_mode is not None and self.default_trip_mode not in TRIP_MODES:
            raise ValueError(f"default_trip_mode must be one of {TRIP_MODES}")
        if not isinstance(self.regional_defaults, RegionalDefaults):
            raise ValueError("regional_defaults must be a RegionalDefaults")
        if any(
            not isinstance(item, NotificationPreference)
            for item in self.notification_preferences
        ):
            raise ValueError(
                "notification_preferences must contain NotificationPreference instances"
            )
        channels = [item.channel for item in self.notification_preferences]
        if len(set(channels)) != len(channels):
            raise ValueError("notification_preferences cannot repeat channels")
        _require_unique_strings(self.preferred_languages, "preferred_languages")
        _require_unique_strings(self.planning_tags, "planning_tags")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AccountPreferenceRecord":
        return cls(
            default_traveler_profile_id=payload.get("default_traveler_profile_id"),
            default_interaction_style=payload.get(
                "default_interaction_style",
                "guided",
            ),
            default_summary_granularity=payload.get(
                "default_summary_granularity",
                "balanced",
            ),
            default_trip_mode=payload.get("default_trip_mode"),
            auto_save_checkpoints=payload.get("auto_save_checkpoints", True),
            regional_defaults=RegionalDefaults.from_dict(
                payload.get("regional_defaults", {})
            ),
            notification_preferences=[
                NotificationPreference.from_dict(item)
                for item in _payload_list(payload, "notification_preferences", [])
            ],
            preferred_languages=_payload_list(payload, "preferred_languages", []),
            planning_tags=_payload_list(payload, "planning_tags", []),
        )


@dataclass(slots=True)
class TravelerProfile:
    traveler_profile_id: str
    display_name: str
    profile_kind: str = "personal"
    supported_modes: list[str] = field(default_factory=lambda: ["leisure"])
    leisure_profile_id: str | None = None
    business_profile_id: str | None = None
    default_origin_airports: list[str] = field(default_factory=list)
    regional_defaults: RegionalDefaults = field(default_factory=RegionalDefaults)
    traveler_tags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.traveler_profile_id, "traveler_profile_id")
        require_non_empty(self.display_name, "display_name")
        if self.profile_kind not in TRAVELER_PROFILE_KINDS:
            raise ValueError(f"profile_kind must be one of {TRAVELER_PROFILE_KINDS}")
        _require_unique_strings(self.supported_modes, "supported_modes")
        if any(mode not in TRIP_MODES for mode in self.supported_modes):
            raise ValueError(f"supported_modes must only use {TRIP_MODES}")
        require_optional_non_empty(self.leisure_profile_id, "leisure_profile_id")
        require_optional_non_empty(self.business_profile_id, "business_profile_id")
        if "leisure" in self.supported_modes and self.leisure_profile_id is None:
            raise ValueError("leisure supported_modes require leisure_profile_id")
        if "business" in self.supported_modes and self.business_profile_id is None:
            raise ValueError("business supported_modes require business_profile_id")
        if "leisure" not in self.supported_modes and self.leisure_profile_id is not None:
            raise ValueError("leisure_profile_id requires leisure in supported_modes")
        if "business" not in self.supported_modes and self.business_profile_id is not None:
            raise ValueError("business_profile_id requires business in supported_modes")
        _require_unique_strings(
            self.default_origin_airports,
            "default_origin_airports",
        )
        if not isinstance(self.regional_defaults, RegionalDefaults):
            raise ValueError("regional_defaults must be a RegionalDefaults")
        _require_unique_strings(self.traveler_tags, "traveler_tags")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TravelerProfile":
        supported_modes = _payload_list(payload, "supported_modes", ["leisure"])
        default_origin_airports = _payload_list(payload, "default_origin_airports", [])
        traveler_tags = _payload_list(payload, "traveler_tags", [])
        notes = _payload_list(payload, "notes", [])
        return cls(
            traveler_profile_id=payload["traveler_profile_id"],
            display_name=payload["display_name"],
            profile_kind=payload.get("profile_kind", "personal"),
            supported_modes=supported_modes,
            leisure_profile_id=payload.get("leisure_profile_id"),
            business_profile_id=payload.get("business_profile_id"),
            default_origin_airports=default_origin_airports,
            regional_defaults=RegionalDefaults.from_dict(
                payload.get("regional_defaults", {})
            ),
            traveler_tags=traveler_tags,
            notes=notes,
        )


@dataclass(slots=True)
class User:
    user_id: str
    email: str
    display_name: str
    traveler_profiles: list[TravelerProfile]
    account_preferences: AccountPreferenceRecord = field(
        default_factory=AccountPreferenceRecord
    )
    status: str = "active"
    schema_version: str = ACCOUNT_SCHEMA_VERSION
    external_refs: dict[str, str] = field(default_factory=dict)
    account_tags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.user_id, "user_id")
        require_non_empty(self.email, "email")
        require_non_empty(self.display_name, "display_name")
        if not self.traveler_profiles:
            raise ValueError("traveler_profiles must contain at least one TravelerProfile")
        if any(not isinstance(item, TravelerProfile) for item in self.traveler_profiles):
            raise ValueError("traveler_profiles must contain TravelerProfile instances")
        if not isinstance(self.account_preferences, AccountPreferenceRecord):
            raise ValueError("account_preferences must be an AccountPreferenceRecord")
        if self.status not in ACCOUNT_STATUSES:
            raise ValueError(f"status must be one of {ACCOUNT_STATUSES}")
        if self.schema_version != ACCOUNT_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {ACCOUNT_SCHEMA_VERSION!r}")
        profile_ids = [item.traveler_profile_id for item in self.traveler_profiles]
        if len(set(profile_ids)) != len(profile_ids):
            raise ValueError("traveler_profiles cannot repeat traveler_profile_id values")
        default_id = self.account_preferences.default_traveler_profile_id
        if default_id is not None and default_id not in profile_ids:
            raise ValueError(
                "default_traveler_profile_id must reference a traveler profile in the user record"
            )
        if any(not isinstance(key, str) or not key for key in self.external_refs):
            raise ValueError("external_refs must use non-empty string keys")
        if any(not isinstance(value, str) or not value for value in self.external_refs.values()):
            raise ValueError("external_refs must contain non-empty string values")
        _require_unique_strings(self.account_tags, "account_tags")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "User":
        raw_traveler_profiles = _payload_list(payload, "traveler_profiles", [])
        traveler_profiles: list[TravelerProfile] = []
        for index, item in enumerate(raw_traveler_profiles):
            if not isinstance(item, dict):
                raise ValueError(f"traveler_profiles[{index}] must be an object")
            traveler_profiles.append(TravelerProfile.from_dict(item))

        return cls(
            user_id=payload["user_id"],
            email=payload["email"],
            display_name=payload["display_name"],
            traveler_profiles=traveler_profiles,
            account_preferences=AccountPreferenceRecord.from_dict(
                payload.get("account_preferences", {})
            ),
            status=payload.get("status", "active"),
            schema_version=payload.get("schema_version", ACCOUNT_SCHEMA_VERSION),
            external_refs=dict(payload.get("external_refs", {})),
            account_tags=_payload_list(payload, "account_tags", []),
            notes=_payload_list(payload, "notes", []),
        )
